"""Fachada de servico para Venda no caixa e Vendas e correcoes."""

from __future__ import annotations

import sqlite3
from typing import Any

from database import get_conn, registrar_venda

STATUS_VALIDOS = {"valid", "corrected", "cancelled"}
ACOES_CORRECAO = [
    "alter_payment",
    "alter_item_quantity",
    "remove_item",
    "cancel_sale",
]


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
        "before": linha["antes"] or "",
        "after": linha["depois"] or "",
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
    "STATUS_VALIDOS",
    "listar_vendas_correcoes",
    "obter_detalhe_venda",
    "registrar_venda",
]
