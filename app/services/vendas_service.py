"""Fachada de servico para Venda no caixa e Vendas e correcoes."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from database import get_conn, registrar_venda

STATUS_VALIDOS = {"valid", "corrected", "cancelled"}
ACOES_CORRECAO = [
    "alter_payment",
    "alter_item_quantity",
    "remove_item",
    "cancel_sale",
]
FORMAS_PAGAMENTO = {
    "Debito",
    "Credito",
    "Pix",
    "Dinheiro",
    "Mais de uma forma",
}


def alterar_pagamento_venda(
    periodo_id: int,
    num_venda: int,
    pagamento: str,
    *,
    responsavel: str,
    pagamento_detalhe: str = "",
    valor_recebido: float | None = None,
    troco: float | None = None,
    observacao: str = "",
) -> dict[str, Any]:
    """Corrige o pagamento de uma venda finalizada e preserva a auditoria."""
    pagamento = (pagamento or "").strip()
    pagamento_detalhe = (pagamento_detalhe or "").strip()

    if pagamento not in FORMAS_PAGAMENTO:
        raise ValueError("Forma de pagamento invalida.")
    valor_recebido = _normalizar_valor_pagamento(valor_recebido, "Valor recebido")
    troco = _normalizar_valor_pagamento(troco, "Troco")

    with get_conn() as conn:
        linhas = conn.execute(
            """
            SELECT *
            FROM vendas
            WHERE periodo_id = ? AND num_venda = ?
            ORDER BY id
            """,
            (periodo_id, num_venda),
        ).fetchall()
        if not linhas:
            raise ValueError("Venda nao encontrada.")

        antes = _pagamento_para_contrato(linhas[0])

    depois = {
        "method": pagamento,
        "detail": pagamento_detalhe,
        "received": valor_recebido,
        "change": troco,
    }
    if antes == depois:
        raise ValueError("O novo pagamento deve ser diferente do atual.")

    with _transacao_correcao(
        periodo_id=periodo_id,
        num_venda=num_venda,
        acao="alter_payment",
        responsavel=responsavel,
        antes=antes,
        depois=depois,
        novo_status="corrected",
        observacao=observacao,
    ) as conn:
        conn.execute(
            """
            UPDATE vendas
            SET pagamento = ?,
                pagamento_detalhe = ?,
                valor_recebido = ?,
                troco = ?
            WHERE periodo_id = ? AND num_venda = ?
            """,
            (
                pagamento,
                pagamento_detalhe,
                valor_recebido,
                troco,
                periodo_id,
                num_venda,
            ),
        )

    detalhe = obter_detalhe_venda(periodo_id, num_venda)
    if detalhe is None:  # Protecao contra alteracao externa entre as transacoes.
        raise RuntimeError("Venda corrigida nao encontrada para consulta.")
    return detalhe


def listar_vendas_correcoes(
    filtros: dict[str, Any] | None = None,
    limite: int = 100,
) -> list[dict[str, Any]]:
    """Lista vendas finalizadas no contrato consumido por Vendas e correcoes."""
    filtros = filtros or {}
    where, params = _montar_filtros(filtros)
    sql = """
        SELECT
            v.periodo_id,
            v.num_venda,
            MAX(v.data) AS data,
            MIN(v.hora) AS hora,
            v.pagamento,
            v.pagamento_detalhe,
            v.valor_recebido,
            v.troco,
            v.responsavel,
            v.status,
            COUNT(*) AS itens_diferentes,
            COALESCE(SUM(v.quantidade), 0) AS unidades,
            COALESCE(SUM(v.subtotal), 0) AS total
        FROM vendas v
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += """
        GROUP BY v.periodo_id, v.num_venda
        ORDER BY MAX(v.data) DESC, MIN(v.hora) DESC, v.num_venda DESC
        LIMIT :limite
    """
    params["limite"] = max(1, int(limite))
    with get_conn() as conn:
        linhas = conn.execute(sql, params).fetchall()
    return [_linha_lista_para_contrato(linha) for linha in linhas]


def obter_detalhe_venda(periodo_id: int, num_venda: int) -> dict[str, Any] | None:
    """Abre o detalhe de uma venda finalizada no contrato de integracao."""
    with get_conn() as conn:
        linhas = conn.execute(
            """
            SELECT *
            FROM vendas
            WHERE periodo_id = ? AND num_venda = ?
            ORDER BY id
            """,
            (periodo_id, num_venda),
        ).fetchall()
        if not linhas:
            return None

        historico = conn.execute(
            """
            SELECT *
            FROM vendas_correcoes
            WHERE periodo_id = ? AND num_venda = ?
            ORDER BY criado_em, id
            """,
            (periodo_id, num_venda),
        ).fetchall()

    return _linhas_detalhe_para_contrato(linhas, historico)


def registrar_correcao_venda(
    periodo_id: int,
    num_venda: int,
    acao: str,
    responsavel: str,
    antes: Any,
    depois: Any,
    novo_status: str = "corrected",
    observacao: str = "",
    criado_em: str | None = None,
) -> dict[str, Any]:
    """Persiste status e auditoria sem executar a mutacao de negocio da correcao.

    Os tickets de cancelamento, pagamento e itens usam ``_transacao_correcao``
    para incluir suas mutacoes na mesma transacao. Esta operacao cobre somente a
    base persistente definida para a issue de historico.
    """
    with _transacao_correcao(
        periodo_id=periodo_id,
        num_venda=num_venda,
        acao=acao,
        responsavel=responsavel,
        antes=antes,
        depois=depois,
        novo_status=novo_status,
        observacao=observacao,
        criado_em=criado_em,
    ):
        pass

    detalhe = obter_detalhe_venda(periodo_id, num_venda)
    if detalhe is None:  # Protege o contrato caso o banco seja alterado externamente.
        raise ValueError("Venda nao encontrada.")
    return detalhe


@contextmanager
def _transacao_correcao(
    periodo_id: int,
    num_venda: int,
    acao: str,
    responsavel: str,
    antes: Any,
    depois: Any,
    novo_status: str,
    observacao: str = "",
    criado_em: str | None = None,
) -> Iterator[sqlite3.Connection]:
    """Mantem mutacao futura, status e auditoria em uma unica transacao."""
    acao, responsavel, novo_status = _validar_dados_correcao(
        acao, responsavel, novo_status
    )
    criado_em = criado_em or datetime.now().isoformat(timespec="seconds")

    with get_conn() as conn:
        linhas = conn.execute(
            """
            SELECT DISTINCT status
            FROM vendas
            WHERE periodo_id = ? AND num_venda = ?
            """,
            (periodo_id, num_venda),
        ).fetchall()
        if not linhas:
            raise ValueError("Venda nao encontrada.")
        if len(linhas) != 1:
            raise ValueError("Venda com status inconsistente.")
        status_atual = _normalizar_status(linhas[0]["status"])
        if status_atual == "cancelled":
            raise ValueError("Venda cancelada nao pode receber nova correcao.")

        yield conn

        conn.execute(
            """
            UPDATE vendas
            SET status = ?
            WHERE periodo_id = ? AND num_venda = ?
            """,
            (novo_status, periodo_id, num_venda),
        )
        conn.execute(
            """
            INSERT INTO vendas_correcoes
            (periodo_id, num_venda, acao, responsavel, criado_em,
             antes, depois, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                periodo_id,
                num_venda,
                acao,
                responsavel,
                criado_em,
                _serializar_auditoria(antes),
                _serializar_auditoria(depois),
                observacao.strip(),
            ),
        )


def _validar_dados_correcao(
    acao: str,
    responsavel: str,
    novo_status: str,
) -> tuple[str, str, str]:
    acao = (acao or "").strip()
    responsavel = (responsavel or "").strip()
    novo_status = (novo_status or "").strip()
    if acao not in ACOES_CORRECAO:
        raise ValueError("Acao de correcao invalida.")
    if not responsavel:
        raise ValueError("Responsavel pela correcao e obrigatorio.")
    if novo_status not in {"corrected", "cancelled"}:
        raise ValueError("Status de correcao invalido.")
    if (acao == "cancel_sale") != (novo_status == "cancelled"):
        raise ValueError("Acao e status da correcao sao incompativeis.")
    return acao, responsavel, novo_status


def _serializar_auditoria(valor: Any) -> str:
    if isinstance(valor, str):
        return valor
    return json.dumps(
        valor,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _desserializar_auditoria(valor: str | None) -> Any:
    texto = valor or ""
    if not texto.startswith(("{", "[")):
        return texto
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return texto


def _montar_filtros(filtros: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    where: list[str] = []
    params: dict[str, Any] = {}

    periodo_id = filtros.get("periodo_id")
    if periodo_id not in (None, ""):
        where.append("v.periodo_id = :periodo_id")
        params["periodo_id"] = int(periodo_id)

    num_venda = filtros.get("num_venda") or filtros.get("sale_number")
    if num_venda not in (None, ""):
        where.append("v.num_venda = :num_venda")
        params["num_venda"] = int(num_venda)

    data_inicio = (filtros.get("data_inicio") or "").strip()
    if data_inicio:
        where.append("v.data >= :data_inicio")
        params["data_inicio"] = data_inicio

    data_fim = (filtros.get("data_fim") or "").strip()
    if data_fim:
        where.append("v.data <= :data_fim")
        params["data_fim"] = data_fim

    pagamento = (filtros.get("pagamento") or "").strip()
    if pagamento:
        where.append("v.pagamento = :pagamento")
        params["pagamento"] = pagamento

    responsavel = (filtros.get("responsavel") or "").strip()
    if responsavel:
        where.append("v.responsavel LIKE :responsavel")
        params["responsavel"] = f"%{responsavel}%"

    produto = (filtros.get("produto") or "").strip()
    if produto:
        where.append("(v.nome LIKE :produto OR v.codigo LIKE :produto)")
        params["produto"] = f"%{produto}%"

    status = (filtros.get("status") or "").strip()
    if status:
        if status not in STATUS_VALIDOS:
            raise ValueError("Status de venda invalido.")
        where.append("v.status = :status")
        params["status"] = status

    return where, params


def _linha_lista_para_contrato(linha: sqlite3.Row) -> dict[str, Any]:
    status = _normalizar_status(linha["status"])
    total = float(linha["total"] or 0)
    unidades = int(linha["unidades"] or 0)
    itens_diferentes = int(linha["itens_diferentes"] or 0)
    return {
        "sale_number": int(linha["num_venda"]),
        "period_id": linha["periodo_id"],
        "sold_at": {
            "date": linha["data"],
            "time": linha["hora"],
        },
        "responsible": linha["responsavel"] or "",
        "payment_summary": _resumo_pagamento(linha),
        "payment": _pagamento_para_contrato(linha),
        "total": total,
        "status": status,
        "item_summary": {
            "items": itens_diferentes,
            "units": unidades,
            "label": _resumo_itens(itens_diferentes, unidades),
        },
        "available_actions": _acoes_disponiveis(status),
    }


def _linhas_detalhe_para_contrato(
    linhas: list[sqlite3.Row],
    historico: list[sqlite3.Row],
) -> dict[str, Any]:
    primeira = linhas[0]
    status = _normalizar_status(primeira["status"])
    total = sum(float(linha["subtotal"] or 0) for linha in linhas)
    unidades = sum(int(linha["quantidade"] or 0) for linha in linhas)
    return {
        "identity": {
            "sale_number": int(primeira["num_venda"]),
            "period_id": primeira["periodo_id"],
        },
        "status": status,
        "responsible": primeira["responsavel"] or "",
        "timestamps": {
            "date": primeira["data"],
            "time": primeira["hora"],
        },
        "payment": _pagamento_para_contrato(primeira),
        "items": [_item_para_contrato(linha) for linha in linhas],
        "totals": {
            "items": len(linhas),
            "units": unidades,
            "total": total,
        },
        "correction_history": [_correcao_para_contrato(row) for row in historico],
        "available_actions": _acoes_disponiveis(status),
    }


def _pagamento_para_contrato(linha: sqlite3.Row) -> dict[str, Any]:
    return {
        "method": linha["pagamento"],
        "detail": linha["pagamento_detalhe"] or "",
        "received": linha["valor_recebido"],
        "change": linha["troco"],
    }


def _normalizar_valor_pagamento(valor: float | None, campo: str) -> float | None:
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{campo} invalido.") from exc
    if numero < 0:
        raise ValueError(f"{campo} nao pode ser negativo.")
    return numero


def _item_para_contrato(linha: sqlite3.Row) -> dict[str, Any]:
    return {
        "line_id": int(linha["id"]),
        "product_id": linha["produto_id"],
        "code": linha["codigo"],
        "name": linha["nome"],
        "quantity": int(linha["quantidade"]),
        "unit_price": float(linha["preco_unit"]),
        "subtotal": float(linha["subtotal"]),
    }


def _correcao_para_contrato(linha: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(linha["id"]),
        "action": linha["acao"],
        "responsible": linha["responsavel"] or "",
        "created_at": linha["criado_em"],
        "before": _desserializar_auditoria(linha["antes"]),
        "after": _desserializar_auditoria(linha["depois"]),
        "note": linha["observacao"] or "",
    }


def _normalizar_status(status: str | None) -> str:
    status = (status or "valid").strip()
    if status not in STATUS_VALIDOS:
        return "valid"
    return status


def _acoes_disponiveis(status: str) -> list[str]:
    if status == "cancelled":
        return []
    return list(ACOES_CORRECAO)


def _resumo_pagamento(linha: sqlite3.Row) -> str:
    detalhe = (linha["pagamento_detalhe"] or "").strip()
    if detalhe:
        return f"{linha['pagamento']} | {detalhe}"
    return linha["pagamento"]


def _resumo_itens(itens: int, unidades: int) -> str:
    sufixo_itens = "item" if itens == 1 else "itens"
    sufixo_unidades = "unidade" if unidades == 1 else "unidades"
    return f"{itens} {sufixo_itens}, {unidades} {sufixo_unidades}"


__all__ = [
    "ACOES_CORRECAO",
    "FORMAS_PAGAMENTO",
    "STATUS_VALIDOS",
    "alterar_pagamento_venda",
    "listar_vendas_correcoes",
    "obter_detalhe_venda",
    "registrar_correcao_venda",
    "registrar_venda",
]
