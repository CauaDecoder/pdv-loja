"""Fachada de servico para fechamento financeiro e relatorios."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app import database
from app.contracts import (
    STATUS_VENDA_ATIVA,
    STATUS_VENDA_CANCELADA,
    STATUS_VENDA_CORRIGIDA,
)
from app.estoque.relatorio_estoque import gerar_posicao_estoque
from app.services.relatorio import gerar_relatorio
from app.services.relatorio import gerar_relatorio_filtrado


def _data_para_exibicao(valor: str) -> str:
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return valor


def fechar_periodo_loja(
    periodo_id: int,
    responsavel: str,
    fechado_em: str | None = None,
) -> dict[str, Any]:
    """Fecha, fotografa e abre o próximo Período da Loja atomicamente."""
    snapshot = database.fechar_periodo_loja(
        periodo_id,
        responsavel,
        fechado_em,
    )
    novo_periodo = database.obter_periodo(snapshot["proximo_periodo_id"])
    if novo_periodo is None:
        raise RuntimeError("Novo Período da Loja não encontrado após fechamento.")
    return {
        "periodo_fechado_id": int(snapshot["periodo_id"]),
        "fechado_em": snapshot["fechado_em"],
        "responsavel": snapshot["responsavel"],
        "novo_periodo": {
            "id": int(novo_periodo["id"]),
            "data": novo_periodo["data"],
            "sequencia": int(novo_periodo["sequencia"]),
            "responsavel": novo_periodo["responsavel"],
            "aberto_em": novo_periodo["aberto_em"],
        },
        "resumo": {
            "receita_centavos": int(snapshot["total_vendas_centavos"]),
            "pagamentos_centavos": int(snapshot["total_pagamentos_centavos"]),
            "divergencia_centavos": int(snapshot["divergencia_centavos"]),
            "conciliado": int(snapshot["divergencia_centavos"]) == 0,
            "custo_conhecido_centavos": int(
                snapshot["custo_conhecido_centavos"]
            ),
            "custos_ausentes": int(snapshot["custos_ausentes"]),
            "margem_completa": int(snapshot["custos_ausentes"]) == 0,
            "margem_bruta_centavos": snapshot["margem_bruta_centavos"],
            "por_forma_destino": snapshot["por_forma_destino"],
        },
    }


def obter_fechamento_financeiro(
    periodo_id: int,
    *,
    _conn=None,
) -> dict[str, Any]:
    """Concilia itens, pagamentos e Vendas canceladas do Período da Loja."""
    if _conn is None:
        with database.get_conn() as conn:
            return obter_fechamento_financeiro(periodo_id, _conn=conn)

    conn = _conn
    cabecalhos = conn.execute(
            """
            SELECT
                h.id AS venda_id,
                h.num_venda,
                h.data,
                h.hora,
                h.responsavel,
                h.status,
                COALESCE(SUM(i.subtotal_centavos), 0) AS total_centavos,
                COALESCE(SUM(i.quantidade * i.custo_unitario_centavos), 0)
                    AS custo_conhecido_centavos,
                COALESCE(SUM(CASE WHEN i.custo_unitario_centavos IS NULL
                                  THEN 1 ELSE 0 END), 0) AS custos_ausentes
            FROM vendas_cabecalho h
            LEFT JOIN vendas_itens i ON i.venda_id = h.id
            WHERE h.periodo_id = ?
            GROUP BY h.id
            ORDER BY h.num_venda
            """,
            (periodo_id,),
    ).fetchall()
    pagamentos = conn.execute(
            """
            SELECT
                h.id AS venda_id,
                p.forma,
                p.destino_id,
                d.nome AS destino,
                SUM(p.valor_centavos) AS valor_centavos
            FROM vendas_cabecalho h
            JOIN pagamentos_venda p ON p.venda_id = h.id
            JOIN destinos_financeiros d ON d.id = p.destino_id
            WHERE h.periodo_id = ?
            GROUP BY h.id, p.forma, p.destino_id, d.nome
            ORDER BY h.num_venda, p.id
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
    destinos: dict[str, dict[str, Any]] = {}
    pagamentos_por_venda: dict[int, list[Any]] = {}
    for pagamento in pagamentos:
        pagamentos_por_venda.setdefault(int(pagamento["venda_id"]), []).append(
            pagamento
        )

    receita_centavos = 0
    custo_conhecido_centavos = 0
    custos_ausentes = 0
    pagamentos_centavos = 0
    for linha in cabecalhos:
        venda_id = int(linha["venda_id"])
        total_centavos = int(linha["total_centavos"] or 0)
        total = total_centavos / 100
        pagamentos_venda = pagamentos_por_venda.get(venda_id, [])
        if linha["status"] == STATUS_VENDA_CANCELADA:
            canceladas.append(
                {
                    "sale_number": int(linha["num_venda"]),
                    "sold_at": {
                        "date": _data_para_exibicao(linha["data"]),
                        "time": linha["hora"],
                    },
                    "responsible": linha["responsavel"] or "",
                    "payment_summary": " + ".join(
                        pagamento["forma"] for pagamento in pagamentos_venda
                    )
                    or "Pagamento ausente",
                    "total": total,
                    "status": "cancelled",
                }
            )
            continue

        movimento["transactions"] += 1
        movimento["total"] += total
        receita_centavos += total_centavos
        custo_conhecido_centavos += int(linha["custo_conhecido_centavos"] or 0)
        custos_ausentes += int(linha["custos_ausentes"] or 0)
        if linha["status"] == STATUS_VENDA_CORRIGIDA:
            movimento["corrected_transactions"] += 1

        formas_contadas: set[str] = set()
        destinos_contados: set[str] = set()
        for pagamento in pagamentos_venda:
            forma = pagamento["forma"]
            valor_centavos = int(pagamento["valor_centavos"] or 0)
            pagamentos_centavos += valor_centavos
            resumo_pagamento = movimento["payment_summary"].setdefault(
                forma,
                {"transactions": 0, "total": 0.0},
            )
            if forma not in formas_contadas:
                resumo_pagamento["transactions"] += 1
                formas_contadas.add(forma)
            resumo_pagamento["total"] += valor_centavos / 100
            chave_destino = f"{forma} | {pagamento['destino']}"
            resumo_destino = destinos.setdefault(
                chave_destino,
                {
                    "method": forma,
                    "destination": pagamento["destino"],
                    "transactions": 0,
                    "total_centavos": 0,
                },
            )
            if chave_destino not in destinos_contados:
                resumo_destino["transactions"] += 1
                destinos_contados.add(chave_destino)
            resumo_destino["total_centavos"] += valor_centavos

    margem_centavos = (
        receita_centavos - custo_conhecido_centavos
        if custos_ausentes == 0
        else None
    )

    return {
        "period_id": periodo_id,
        "financial_movement": movimento,
        "destination_summary": destinos,
        "reconciliation": {
            "sales_centavos": receita_centavos,
            "payments_centavos": pagamentos_centavos,
            "difference_centavos": pagamentos_centavos - receita_centavos,
            "balanced": pagamentos_centavos == receita_centavos,
        },
        "cost_summary": {
            "known_cost_centavos": custo_conhecido_centavos,
            "missing_cost_items": custos_ausentes,
            "complete": custos_ausentes == 0,
            "gross_margin_centavos": margem_centavos,
        },
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

    linhas = _linhas_canonicas_periodo(periodo_id)
    if not linhas:
        raise ValueError("Periodo sem vendas para exportar.")

    return gerar_relatorio(
        linhas,
        periodo["data"],
        pasta_saida,
        responsavel=responsavel or periodo["responsavel"] or "",
        periodo_seq=periodo["sequencia"],
    )


def _linhas_canonicas_periodo(periodo_id: int) -> list[dict[str, Any]]:
    return _linhas_canonicas("h.periodo_id = ?", (periodo_id,))


def _linhas_canonicas(
    where_sql: str,
    params: tuple[Any, ...],
) -> list[dict[str, Any]]:
    with database.get_conn() as conn:
        colunas_itens = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(vendas_itens)").fetchall()
        }
        custo_sql = (
            "i.custo_unitario_centavos"
            if "custo_unitario_centavos" in colunas_itens
            else "NULL"
        )
        itens = conn.execute(
            """
            SELECT
                h.id AS venda_id,
                h.periodo_id,
                h.num_venda,
                h.data,
                h.hora,
                h.responsavel,
                h.status,
                i.codigo,
                i.nome,
                i.quantidade,
                i.preco_unit_centavos,
                i.subtotal_centavos,
                """
            + custo_sql
            + """ AS custo_unitario_centavos
            FROM vendas_cabecalho h
            JOIN vendas_itens i ON i.venda_id = h.id
            WHERE """
            + where_sql
            + """
            ORDER BY h.num_venda, i.id
            """,
            params,
        ).fetchall()
        pagamentos = conn.execute(
            """
            SELECT
                h.id AS venda_id,
                p.forma,
                p.destino_id,
                d.nome AS destino,
                p.valor_centavos,
                p.detalhe,
                p.valor_recebido_centavos,
                p.troco_centavos
            FROM vendas_cabecalho h
            JOIN pagamentos_venda p
              ON p.venda_id = h.id
            JOIN destinos_financeiros d ON d.id = p.destino_id
            WHERE """
            + where_sql
            + """
            ORDER BY h.num_venda, p.id
            """,
            params,
        ).fetchall()

    pagamentos_por_venda: dict[int, list[dict[str, Any]]] = {}
    for pagamento in pagamentos:
        pagamentos_por_venda.setdefault(int(pagamento["venda_id"]), []).append(
            {
                "forma": pagamento["forma"],
                "destino_id": int(pagamento["destino_id"]),
                "destino": pagamento["destino"],
                "valor_centavos": int(pagamento["valor_centavos"]),
                "detalhe": pagamento["detalhe"] or "",
                "valor_recebido_centavos": pagamento["valor_recebido_centavos"],
                "troco_centavos": pagamento["troco_centavos"],
            }
        )

    linhas: list[dict[str, Any]] = []
    for item in itens:
        parcelas = pagamentos_por_venda.get(int(item["venda_id"]), [])
        forma = parcelas[0]["forma"] if len(parcelas) == 1 else "Mais de uma forma"
        detalhes = " + ".join(
            f"{parcela['forma']} ({parcela['detalhe']})"
            if parcela["detalhe"]
            else parcela["forma"]
            for parcela in parcelas
        )
        recebidos = [
            int(parcela["valor_recebido_centavos"])
            for parcela in parcelas
            if parcela["valor_recebido_centavos"] is not None
        ]
        trocos = [
            int(parcela["troco_centavos"])
            for parcela in parcelas
            if parcela["troco_centavos"] is not None
        ]
        linhas.append(
            {
                "num_venda": int(item["num_venda"]),
                "periodo_id": int(item["periodo_id"]),
                "data": item["data"],
                "hora": item["hora"],
                "pagamento": forma,
                "pagamento_detalhe": detalhes,
                "valor_recebido": sum(recebidos) / 100 if recebidos else None,
                "troco": sum(trocos) / 100 if trocos else None,
                "responsavel": item["responsavel"] or "",
                "status": _status_publico(item["status"]),
                "codigo": item["codigo"],
                "nome": item["nome"],
                "quantidade": int(item["quantidade"]),
                "preco_unit_centavos": int(item["preco_unit_centavos"]),
                "subtotal_centavos": int(item["subtotal_centavos"]),
                "preco_unit": int(item["preco_unit_centavos"]) / 100,
                "subtotal": int(item["subtotal_centavos"]) / 100,
                "custo_unitario_centavos": item["custo_unitario_centavos"],
                "pagamentos": parcelas,
            }
        )
    return linhas


def gerar_relatorio_vendas_filtrado(
    data_inicial: str,
    data_final: str,
    pasta_saida: str = ".",
    forma: str | None = None,
    destino_id: int | None = None,
    incluir_canceladas: bool = False,
    status: str | None = None,
) -> Path:
    """Gera relatório XLSX por intervalo e destino financeiro."""
    dados = obter_relatorio_vendas_filtrado(
        data_inicial,
        data_final,
        forma,
        destino_id,
        incluir_canceladas,
        status,
    )
    if not dados["vendas"] and not dados.get("canceladas"):
        raise ValueError("Nenhuma venda encontrada no filtro informado.")
    return gerar_relatorio_filtrado(dados, pasta_saida)


def obter_relatorio_vendas_filtrado(
    data_inicial: str,
    data_final: str,
    forma: str | None = None,
    destino_id: int | None = None,
    incluir_canceladas: bool = False,
    status: str | None = None,
) -> dict[str, Any]:
    """Retorna relatório canônico por intervalo, Forma e Destino financeiro."""
    inicio_iso = _normalizar_data(data_inicial)
    fim_iso = _normalizar_data(data_final)
    if inicio_iso > fim_iso:
        raise ValueError("A data inicial deve ser anterior ou igual à data final.")
    if status not in (None, "valid", "corrected", "cancelled", "all"):
        raise ValueError("Status de venda invalido.")
    data_sql = """CASE
        WHEN instr(h.data, '/') > 0
        THEN substr(h.data, 7, 4) || '-' || substr(h.data, 4, 2) || '-' || substr(h.data, 1, 2)
        ELSE h.data
    END"""
    linhas = _linhas_canonicas(
        f"{data_sql} BETWEEN ? AND ?",
        (inicio_iso, fim_iso),
    )
    vendas_por_chave: dict[tuple[int, int], dict[str, Any]] = {}
    for linha in linhas:
        chave = (linha["periodo_id"], linha["num_venda"])
        venda = vendas_por_chave.setdefault(
            chave,
            {
                "periodo_id": linha["periodo_id"],
                "num_venda": linha["num_venda"],
                "data": linha["data"],
                "hora": linha["hora"],
                "status": linha["status"],
                "responsavel": linha["responsavel"],
                "total_centavos": 0,
                "pagamentos": linha["pagamentos"],
                "itens": [],
            },
        )
        venda["total_centavos"] += linha["subtotal_centavos"]
        venda["itens"].append(linha)

    vendas: list[dict[str, Any]] = []
    canceladas: list[dict[str, Any]] = []
    itens: list[dict[str, Any]] = []
    pagamentos_saida: list[dict[str, Any]] = []
    resumo: dict[str, dict[str, Any]] = {}
    for venda in vendas_por_chave.values():
        cancelada = venda["status"] == "cancelled"
        if status not in (None, "all") and venda["status"] != status:
            continue
        if status is None and not incluir_canceladas and cancelada:
            continue
        parcelas = [
            parcela
            for parcela in venda["pagamentos"]
            if _parcela_atende_filtro(parcela, forma, destino_id)
        ]
        if not parcelas and (forma or destino_id is not None):
            continue
        valor_filtrado_centavos = sum(
            parcela["valor_centavos"] for parcela in parcelas
        )
        custos_ausentes = sum(
            item["custo_unitario_centavos"] is None for item in venda["itens"]
        )
        custo_conhecido_centavos = sum(
            int(item["custo_unitario_centavos"]) * int(item["quantidade"])
            for item in venda["itens"]
            if item["custo_unitario_centavos"] is not None
        )
        resumo_venda = {
            "periodo_id": venda["periodo_id"],
            "num_venda": venda["num_venda"],
            "data": venda["data"],
            "hora": venda["hora"],
            "status": venda["status"],
            "responsavel": venda["responsavel"],
            "total": venda["total_centavos"] / 100,
            "total_centavos": venda["total_centavos"],
            "valor_filtrado_centavos": valor_filtrado_centavos,
            "custo_conhecido_centavos": custo_conhecido_centavos,
            "custos_ausentes": custos_ausentes,
            "margem_bruta_centavos": (
                venda["total_centavos"] - custo_conhecido_centavos
                if custos_ausentes == 0
                else None
            ),
        }
        (canceladas if cancelada else vendas).append(resumo_venda)
        for item in venda["itens"]:
            itens.append(
                {
                    "periodo_id": venda["periodo_id"],
                    "num_venda": venda["num_venda"],
                    "codigo": item["codigo"],
                    "nome": item["nome"],
                    "quantidade": item["quantidade"],
                    "preco_unit": item["preco_unit"],
                    "subtotal": item["subtotal"],
                    "custo_unitario_centavos": item["custo_unitario_centavos"],
                    "status": venda["status"],
                }
            )
        chaves_resumo_contadas: set[str] = set()
        for parcela in parcelas:
            pagamentos_saida.append(
                {
                    "periodo_id": venda["periodo_id"],
                    "num_venda": venda["num_venda"],
                    **parcela,
                }
            )
            if cancelada:
                continue
            chave_resumo = f"{parcela['forma']} | {parcela['destino']}"
            bucket = resumo.setdefault(
                chave_resumo,
                {
                    "forma": parcela["forma"],
                    "destino": parcela["destino"],
                    "transacoes": 0,
                    "total_centavos": 0,
                },
            )
            if chave_resumo not in chaves_resumo_contadas:
                bucket["transacoes"] += 1
                chaves_resumo_contadas.add(chave_resumo)
            bucket["total_centavos"] += parcela["valor_centavos"]

    return {
        "filtros": {
            "data_inicial": data_inicial,
            "data_final": data_final,
            "forma": forma,
            "destino_id": destino_id,
            "status": status or "valid",
        },
        "vendas": vendas,
        "canceladas": canceladas,
        "itens": itens,
        "pagamentos": pagamentos_saida,
        "resumo": list(resumo.values()),
        "total_centavos": sum(
            item["total_centavos"] for item in resumo.values()
        ),
    }


def _normalizar_data(valor: str) -> str:
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("Use datas no formato AAAA-MM-DD ou DD/MM/AAAA.")


def _status_publico(status: str) -> str:
    return {
        STATUS_VENDA_ATIVA: "valid",
        STATUS_VENDA_CORRIGIDA: "corrected",
        STATUS_VENDA_CANCELADA: "cancelled",
    }.get(status, status)


def _parcela_atende_filtro(
    parcela: dict[str, Any],
    forma: str | None,
    destino_id: int | None,
) -> bool:
    if forma == "Cartao" and parcela["forma"] not in ("Debito", "Credito"):
        return False
    if forma and forma != "Cartao" and parcela["forma"] != forma:
        return False
    return destino_id is None or parcela["destino_id"] == int(destino_id)


def _descricao_pagamento(linha: Any) -> str:
    detalhe = (linha["pagamento_detalhe"] or "").strip()
    return f"{linha['pagamento']} | {detalhe}" if detalhe else linha["pagamento"]


__all__ = [
    "fechar_periodo_loja",
    "gerar_posicao_estoque",
    "gerar_relatorio",
    "gerar_relatorio_periodo",
    "obter_relatorio_vendas_filtrado",
    "obter_fechamento_financeiro",
    "gerar_relatorio_vendas_filtrado",
]
