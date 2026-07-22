"""Fachada de servico para fechamento financeiro e relatorios."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import database
from estoque.relatorio_estoque import gerar_posicao_estoque
from relatorio import gerar_relatorio


def obter_fechamento_financeiro(periodo_id: int) -> dict[str, Any]:
    """Separa a movimentacao financeira liquida das Vendas canceladas."""
    with database.get_conn() as conn:
        linhas = conn.execute(
            """
            SELECT
                num_venda,
                MAX(data) AS data,
                MIN(hora) AS hora,
                pagamento,
                pagamento_detalhe,
                responsavel,
                status,
                COALESCE(SUM(subtotal), 0) AS total
            FROM vendas
            WHERE periodo_id = ?
            GROUP BY num_venda, pagamento, pagamento_detalhe, responsavel, status
            ORDER BY num_venda
            """,
            (periodo_id,),
        ).fetchall()

    movimento = {
        "transactions": 0,
        "total": 0.0,
        "corrected_transactions": 0,
        "payment_summary": {},
    }
    canceladas: list[dict[str, Any]] = []

    for linha in linhas:
        total = float(linha["total"] or 0)
        if linha["status"] == "cancelled":
            canceladas.append(
                {
                    "sale_number": int(linha["num_venda"]),
                    "sold_at": {
                        "date": linha["data"],
                        "time": linha["hora"],
                    },
                    "responsible": linha["responsavel"] or "",
                    "payment_summary": _descricao_pagamento(linha),
                    "total": total,
                    "status": "cancelled",
                }
            )
            continue

        movimento["transactions"] += 1
        movimento["total"] += total
        if linha["status"] == "corrected":
            movimento["corrected_transactions"] += 1

        pagamento = linha["pagamento"]
        resumo_pagamento = movimento["payment_summary"].setdefault(
            pagamento,
            {"transactions": 0, "total": 0.0},
        )
        resumo_pagamento["transactions"] += 1
        resumo_pagamento["total"] += total

    return {
        "period_id": periodo_id,
        "financial_movement": movimento,
        "cancelled_sales": canceladas,
    }


def gerar_relatorio_periodo(
    periodo_id: int,
    pasta_saida: str = ".",
    *,
    responsavel: str = "",
) -> Path:
    """Gera o XLSX do periodo usando os dados atuais das vendas e correcoes."""
    periodo = database.obter_periodo(periodo_id)
    if periodo is None:
        raise ValueError("Periodo nao encontrado.")

    linhas = [dict(row) for row in database.vendas_do_periodo(periodo_id)]
    if not linhas:
        raise ValueError("Periodo sem vendas para exportar.")

    return gerar_relatorio(
        linhas,
        periodo["data"],
        pasta_saida,
        responsavel=responsavel or periodo["responsavel"] or "",
        periodo_seq=periodo["sequencia"],
    )


def _descricao_pagamento(linha: Any) -> str:
    detalhe = (linha["pagamento_detalhe"] or "").strip()
    return f"{linha['pagamento']} | {detalhe}" if detalhe else linha["pagamento"]


__all__ = [
    "gerar_posicao_estoque",
    "gerar_relatorio",
    "gerar_relatorio_periodo",
    "obter_fechamento_financeiro",
]
