"""Interface HTTP central do PDV.

O processo que hospeda este módulo é o único que abre o SQLite central.
"""

from __future__ import annotations

import hashlib
import secrets
import shutil
import tempfile
import threading
from datetime import datetime
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field, field_validator

from app import database
from app.services import backup_service, relatorios_service, vendas_service
from app.paths import BACKUPS_DIR

@asynccontextmanager
async def lifespan(_: FastAPI):
    database.inicializar()
    yield


app = FastAPI(title="Caixa Basilica Central", version="1.0", lifespan=lifespan)
_write_lock = threading.RLock()

RPC_OPERATIONS = {
    "database": {
        "buscar_produto", "obter_periodo", "obter_ou_criar_periodo_aberto",
        "atualizar_responsavel_periodo", "encerrar_periodo", "fechar_periodo_loja", "proximo_num_venda",
        "vendas_do_periodo", "ultimas_vendas_periodo",
        "atualizar_venda", "configuracoes", "atualizar_configuracoes",
        "criar_produto", "atualizar_produto", "inativar_produto", "reativar_produto",
        "listar_produtos", "listar_produtos_estoque", "obter_produto",
        "atualizar_parametros_produto", "registrar_entrada_estoque",
        "registrar_movimentacao_estoque", "ajustar_estoque_por_contagem",
        "registrar_perda_estoque", "listar_movimentacoes_estoque",
        "obter_movimentacoes_produto", "dashboard_resumo_estoque",
        "dashboard_status_estoque", "dashboard_curva_abc", "dashboard_valor_por_categoria",
        "dashboard_top_valor_parado", "dashboard_top_vendidos",
        "dashboard_movimentacoes_periodo", "opcoes_produtos", "totais_periodo",
        "resumo_do_periodo", "listar_destinos_financeiros", "criar_destino_financeiro",
        "inativar_destino_financeiro", "atualizar_destino_financeiro", "definir_destino_padrao", "relatorio_vendas_filtrado",
        "indicadores_produtos_estoque", "recalcular_curva_abc", "ultimo_periodo_id",
        "contexto_inicial_venda_no_caixa", "snapshot_dashboard_estoque", "snapshot_operacional_estoque",
        "reconciliar_integridade_banco",
    },
    "sales": {
        "listar_vendas_correcoes", "consultar_vendas_correcoes", "obter_detalhe_venda", "alterar_pagamento_venda",
        "alterar_data_venda",
        "alterar_quantidade_item_venda", "remover_item_venda", "cancelar_venda",
    },
    "reports": {"obter_fechamento_financeiro"},
}
RPC_MODULES = {"database": database, "sales": vendas_service, "reports": relatorios_service}


class ItemVenda(BaseModel):
    produto_id: int | None = None
    codigo: str
    nome: str
    quantidade: int = Field(gt=0)
    preco_unit: Decimal = Field(ge=0)


class Pagamento(BaseModel):
    forma: str
    valor_centavos: int = Field(gt=0)
    destino_id: int | None = None
    detalhe: str = ""
    valor_recebido_centavos: int | None = None
    troco_centavos: int | None = None


class VendaRequest(BaseModel):
    itens: list[ItemVenda]
    pagamentos: list[Pagamento]
    responsavel: str
    terminal_id: int | None = None
    chave_idempotencia: str
    data: str | None = None

    @field_validator("responsavel")
    @classmethod
    def validar_responsavel(cls, value: str) -> str:
        operador = value.strip()
        if not operador:
            raise ValueError("Operador é obrigatório.")
        return operador


class RelatorioQuery(BaseModel):
    data_inicial: str
    data_final: str
    forma: str | None = None
    destino_id: int | None = None
    incluir_canceladas: bool = False


class DestinoRequest(BaseModel):
    nome: str
    formas: list[str]
    padroes: list[str] = Field(default_factory=list)


def _terminal(authorization: str | None = Header(default=None)) -> int | None:
    """Valida credencial técnica quando terminais foram cadastrados."""
    with database.get_conn() as conn:
        cadastrados = conn.execute("SELECT COUNT(*) FROM terminais WHERE ativo = 1").fetchone()[0]
    if not authorization:
        if cadastrados:
            raise HTTPException(401, "Credencial de Terminal obrigatória.")
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Credencial de Terminal inválida.")
    digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
    with database.get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM terminais WHERE credencial_hash = ? AND ativo = 1", (digest,)
        ).fetchone()
    if not row:
        raise HTTPException(401, "Terminal não autorizado.")
    return int(row["id"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/destinations")
def destinations(_: int | None = Depends(_terminal)) -> list[dict[str, Any]]:
    return [dict(row) for row in database.listar_destinos_financeiros()]


@app.post("/rpc/{namespace}/{operation}")
def rpc(namespace: str, operation: str, payload: dict, _: int | None = Depends(_terminal)):
    if operation not in RPC_OPERATIONS.get(namespace, set()):
        raise HTTPException(404, "Operação não disponível.")
    try:
        with _write_lock:
            result = getattr(RPC_MODULES[namespace], operation)(*payload.get("args", []), **payload.get("kwargs", {}))
        if hasattr(result, "keys") and not isinstance(result, dict):
            result = dict(result)
        elif isinstance(result, list):
            result = [dict(item) if hasattr(item, "keys") and not isinstance(item, dict) else item for item in result]
        return jsonable_encoder(result)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/destinations")
def create_destination(payload: DestinoRequest, _: int | None = Depends(_terminal)) -> dict[str, int]:
    return {"id": database.criar_destino_financeiro(payload.nome, payload.formas, payload.padroes)}


@app.delete("/destinations/{destination_id}", status_code=204)
def disable_destination(destination_id: int, _: int | None = Depends(_terminal)) -> Response:
    database.inativar_destino_financeiro(destination_id)
    return Response(status_code=204)


@app.post("/sales")
def create_sale(payload: VendaRequest, terminal_id: int | None = Depends(_terminal)) -> dict:
    try:
        data = payload.data or datetime.now().strftime("%d/%m/%Y")
        with _write_lock:
            periodo = database.obter_ou_criar_periodo_aberto(data)
            result = database.registrar_venda(
                periodo["id"],
                database.proximo_num_venda(periodo["id"]),
                [item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in payload.itens],
                payload.pagamentos[0].forma if len(payload.pagamentos) == 1 else "Mais de uma forma",
                responsavel=payload.responsavel,
                data=data,
                pagamentos=[payment.model_dump() if hasattr(payment, "model_dump") else payment.dict() for payment in payload.pagamentos],
                chave_idempotencia=payload.chave_idempotencia,
                terminal_id=terminal_id or payload.terminal_id,
            )
        return result
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get("/reports/sales.xlsx")
def sales_report(
    data_inicial: str,
    data_final: str,
    forma: str | None = None,
    destino_id: int | None = None,
    incluir_canceladas: bool = False,
    status: str | None = None,
    _: int | None = Depends(_terminal),
) -> Response:
    from app.services.relatorio import gerar_relatorio_filtrado

    dados = relatorios_service.obter_relatorio_vendas_filtrado(
        data_inicial,
        data_final,
        forma,
        destino_id,
        incluir_canceladas,
        status,
    )
    if not dados["vendas"] and not dados["canceladas"]:
        raise HTTPException(404, "Nenhuma venda encontrada no filtro informado.")
    directory = Path(tempfile.mkdtemp())
    caminho = gerar_relatorio_filtrado(dados, directory)
    return FileResponse(caminho, filename=caminho.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", background=BackgroundTask(shutil.rmtree, directory, True))


@app.get("/reports/period/{period_id}.xlsx")
def period_report(period_id: int, _: int | None = Depends(_terminal)) -> Response:
    directory = Path(tempfile.mkdtemp())
    path = relatorios_service.gerar_relatorio_periodo(period_id, str(directory))
    return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", background=BackgroundTask(shutil.rmtree, directory, True))


@app.get("/maintenance/backup")
def download_backup(_: int | None = Depends(_terminal)) -> Response:
    path = backup_service.criar_backup(database.DB_PATH, BACKUPS_DIR)
    return FileResponse(path, filename=path.name, media_type="application/vnd.sqlite3")


@app.post("/maintenance/restore")
def restore_backup(file: UploadFile, _: int | None = Depends(_terminal)) -> dict:
    with tempfile.TemporaryDirectory() as directory, _write_lock:
        backup = _save_upload(file, directory)
        previous = backup_service.restaurar_backup(backup, database.DB_PATH, BACKUPS_DIR)
    return {"backup_anterior": str(previous) if previous else None}


def _save_upload(file: UploadFile, directory: str) -> Path:
    suffix = Path(file.filename or "import.xlsx").suffix
    target = Path(directory) / f"import{suffix}"
    target.write_bytes(file.file.read())
    return target


@app.post("/imports/preview")
def preview_import(file: UploadFile, _: int | None = Depends(_terminal)) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        return database.previsualizar_importacao(str(_save_upload(file, directory)))


@app.post("/imports/execute")
def execute_import(
    file: UploadFile,
    mode: str = Form(...),
    responsavel: str = Form(...),
    lote_id: str = Form(...),
    hash_arquivo: str = Form(...),
    _: int | None = Depends(_terminal),
) -> dict:
    with tempfile.TemporaryDirectory() as directory, _write_lock:
        return database.importar_csv(
            str(_save_upload(file, directory)),
            modo_estoque=mode,
            responsavel=responsavel,
            lote_id=lote_id,
            hash_arquivo=hash_arquivo,
        )


def criar_terminal(nome: str, permite_offline: bool = False) -> tuple[int, str]:
    """Cria Terminal técnico e retorna id e credencial uma única vez."""
    token = secrets.token_urlsafe(32)
    with database.get_conn() as conn:
        row = conn.execute(
            "INSERT INTO terminais (nome, credencial_hash, permite_offline, criado_em) VALUES (?, ?, ?, ?) RETURNING id",
            (nome, hashlib.sha256(token.encode()).hexdigest(), int(permite_offline), datetime.now().isoformat(timespec="seconds")),
        ).fetchone()
    return int(row["id"]), token
