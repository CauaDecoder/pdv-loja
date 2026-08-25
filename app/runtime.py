"""Escolhe adapters local ou HTTP sem expor essa decisão às telas."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from app import database as local_database
from app.remote import CentralClient, CentralUnavailable
from app.offline import OfflineQueue
from app.paths import DATA_DIR
from app.config import terminal_config
from app.contracts import valor_para_centavos
from app.services import relatorios_service as local_reports
from app.services import vendas_service as local_sales


class RemoteNamespace:
    def __init__(self, client: CentralClient, name: str, queue: OfflineQueue | None = None):
        self.client = client
        self.name = name
        self.queue = queue

    def __getattr__(self, operation: str):
        def invoke(*args, **kwargs):
            key = f"{self.name}:{operation}:{args!r}:{sorted(kwargs.items())!r}"
            try:
                result = self.client.rpc(self.name, operation, *args, **kwargs)
                if self.queue and operation in CACHEABLE_OPERATIONS.get(self.name, set()):
                    self.queue.cache_set(key, result)
                return result
            except CentralUnavailable:
                if self.queue and operation in CACHEABLE_OPERATIONS.get(self.name, set()):
                    return self.queue.cache_get(key)
                raise
        return invoke


class RemoteDatabase(RemoteNamespace):
    def __getattr__(self, operation: str):
        if operation == "inicializar":
            return lambda: None
        return super().__getattr__(operation)

    def registrar_venda(
        self, periodo_id, num_venda, itens, pagamento, pagamento_detalhe="",
        valor_recebido=None, troco=None, responsavel="", data=None,
        pagamentos=None, chave_idempotencia=None, terminal_id=None,
    ):
        if not (responsavel or "").strip():
            raise ValueError("Operador é obrigatório para finalizar a Venda no caixa.")
        if not chave_idempotencia:
            raise ValueError("Identificador idempotente da Venda no caixa é obrigatório.")
        total_centavos = sum(
            int(item["quantidade"])
            * int(
                item.get("preco_unit_centavos")
                if item.get("preco_unit_centavos") is not None
                else valor_para_centavos(item["preco_unit"])
            )
            for item in itens
        )
        pagamentos = pagamentos or [{
            "forma": pagamento,
            "valor_centavos": total_centavos,
            "detalhe": pagamento_detalhe,
            "valor_recebido_centavos": valor_para_centavos(valor_recebido) if valor_recebido is not None else None,
            "troco_centavos": valor_para_centavos(troco) if troco is not None else None,
        }]
        payload = {
            "itens": itens, "pagamentos": pagamentos, "responsavel": responsavel,
            "data": data, "chave_idempotencia": chave_idempotencia,
        }
        try:
            return self.client.create_sale(payload)
        except CentralUnavailable:
            if not self.queue:
                raise
            self.queue.enqueue_sale(payload)
            return {"offline": True, "chave_idempotencia": payload["chave_idempotencia"]}


CACHEABLE_OPERATIONS = {
    "database": {
        "buscar_produto", "obter_periodo", "obter_ou_criar_periodo_aberto", "proximo_num_venda",
        "vendas_do_periodo", "ultimas_vendas_periodo", "configuracoes", "listar_produtos",
        "listar_produtos_estoque", "obter_produto", "listar_movimentacoes_estoque",
        "obter_movimentacoes_produto", "dashboard_resumo_estoque", "dashboard_status_estoque",
        "dashboard_curva_abc", "dashboard_valor_por_categoria", "dashboard_top_valor_parado",
        "dashboard_top_vendidos", "dashboard_movimentacoes_periodo", "opcoes_produtos",
        "totais_periodo", "resumo_do_periodo", "listar_destinos_financeiros",
        "indicadores_produtos_estoque", "ultimo_periodo_id",
        "contexto_inicial_venda_no_caixa", "snapshot_dashboard_estoque", "snapshot_operacional_estoque",
    },
    "sales": {"listar_vendas_correcoes", "consultar_vendas_correcoes", "obter_detalhe_venda"},
    "reports": {"obter_fechamento_financeiro"},
}


@dataclass
class Runtime:
    """Agrupa adapters escolhidos explicitamente para um processo do PDV."""

    database: ModuleType | RemoteNamespace
    sales: ModuleType | RemoteNamespace
    reports: ModuleType | RemoteNamespace
    client: CentralClient | None = None
    offline_queue: OfflineQueue | None = None

    @classmethod
    def local(cls, db_path: str | Path | None = None) -> "Runtime":
        """Cria runtime local sem abrir banco ou criar arquivos."""
        if db_path is not None:
            local_database.DB_PATH = Path(db_path)
        return cls(local_database, local_sales, local_reports)

    @classmethod
    def central(cls, config_path: str | Path | None = None) -> "Runtime":
        """Cria runtime Central somente após opção explícita do processo."""
        config = terminal_config(config_path)
        url = os.getenv("CAIXA_CENTRAL_URL", config.get("url", "")).strip()
        token = os.getenv("CAIXA_TERMINAL_TOKEN", config.get("token", "")).strip()
        ca_file = os.getenv("CAIXA_CA_CERT", config.get("ca_cert", "")).strip()
        if not url:
            raise ValueError("Configuração da Central não contém URL.")
        client = CentralClient(url, token, ca_file=ca_file)
        permite_offline = os.getenv(
            "CAIXA_PERMITE_OFFLINE", str(int(config.get("permite_offline", False)))
        ) == "1"
        queue = OfflineQueue(DATA_DIR / "terminal.db") if permite_offline else None
        return cls(
            RemoteDatabase(client, "database", queue),
            RemoteNamespace(client, "sales", queue),
            RemoteNamespace(client, "reports", queue),
            client,
            queue,
        )


_runtime = Runtime.local()
client = _runtime.client
offline_queue = _runtime.offline_queue
database = _runtime.database
sales = _runtime.sales
reports = _runtime.reports


def configure_runtime(runtime: Runtime) -> None:
    """Instala runtime antes da importação das telas."""
    global _runtime, client, offline_queue, database, sales, reports
    if _runtime.client and _runtime.client is not runtime.client:
        _runtime.client.close()
    _runtime = runtime
    client = runtime.client
    offline_queue = runtime.offline_queue
    database = runtime.database
    sales = runtime.sales
    reports = runtime.reports


def remote_mode() -> bool:
    return _runtime.client is not None


def close_remote_client() -> None:
    """Close the process-owned HTTP pool when the PDV exits."""
    if _runtime.client:
        _runtime.client.close()


def pending_sales() -> int:
    return len(_runtime.offline_queue.pending()) if _runtime.offline_queue else 0


def sync_pending_sales() -> int:
    return _runtime.offline_queue.sync(_runtime.client) if _runtime.offline_queue and _runtime.client else 0


def preview_import(path: str) -> dict:
    return _runtime.client.upload("/imports/preview", path) if _runtime.client else local_database.previsualizar_importacao(path)


def execute_import(
    path: str,
    mode: str,
    *,
    responsavel: str,
    lote_id: str,
    hash_arquivo: str,
) -> dict:
    fields = {
        "mode": mode,
        "responsavel": responsavel,
        "lote_id": lote_id,
        "hash_arquivo": hash_arquivo,
    }
    if _runtime.client:
        return _runtime.client.upload("/imports/execute", path, fields)
    return local_database.importar_csv(
        path,
        modo_estoque=mode,
        responsavel=responsavel,
        lote_id=lote_id,
        hash_arquivo=hash_arquivo,
    )


def filtered_report(params: dict, destination: str | Path) -> Path:
    if _runtime.client:
        return _runtime.client.download_sales_report(params, destination)
    return local_reports.gerar_relatorio_vendas_filtrado(
        params["data_inicial"], params["data_final"], str(Path(destination).parent),
        params.get("forma"), params.get("destino_id"), params.get("incluir_canceladas", False), params.get("status"),
    )


def period_report(period_id: int, destination: str | Path) -> Path:
    if _runtime.client:
        data, _ = _runtime.client.request("GET", f"/reports/period/{period_id}.xlsx")
        Path(destination).write_bytes(data)
        return Path(destination)
    return local_reports.gerar_relatorio_periodo(period_id, str(Path(destination).parent))


def create_backup(destination: str | Path) -> Path:
    if not _runtime.client:
        from app.services import backup_service
        return backup_service.criar_backup(local_database.DB_PATH, Path(destination).parent)
    data, _ = _runtime.client.request("GET", "/maintenance/backup")
    Path(destination).write_bytes(data)
    return Path(destination)


def restore_backup(source: str | Path) -> dict:
    if _runtime.client:
        return _runtime.client.upload("/maintenance/restore", source)
    from app.services import backup_service
    previous = backup_service.restaurar_backup(Path(source), local_database.DB_PATH, local_database.DB_PATH.parent.parent / "backups")
    return {"backup_anterior": str(previous) if previous else None}
