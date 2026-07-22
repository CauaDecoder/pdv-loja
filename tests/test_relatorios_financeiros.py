import shutil
import uuid
from pathlib import Path

from openpyxl import load_workbook

import database
from app.services import relatorios_service, vendas_service


def _usar_banco_temporario():
    base = Path.cwd() / ".scratch" / "tests"
    base.mkdir(parents=True, exist_ok=True)
    temp = base / f"relatorios_{uuid.uuid4().hex}"
    temp.mkdir()
    original = database.DB_PATH
    database.DB_PATH = temp / "loja_teste.db"
    database.inicializar()
    return temp, original


def _preparar_periodo_com_correcoes() -> tuple[int, Path, Path]:
    temp, original = _usar_banco_temporario()
    with database.get_conn() as conn:
        periodo_id = conn.execute(
            """
            INSERT INTO periodos_caixa
                (data, sequencia, aberto_em, responsavel)
            VALUES ('01/01/2026', 1, '2026-01-01T08:00:00', 'Operador')
            """
        ).lastrowid
        produtos = {}
        for codigo, nome, preco in (
            ("A", "Produto financeiro", 10),
            ("B", "Produto removido", 5),
            ("C", "Produto cancelado", 7),
        ):
            produtos[codigo] = conn.execute(
                """
                INSERT INTO produtos (codigo, nome, preco, estoque)
                VALUES (?, ?, ?, 30)
                """,
                (codigo, nome, preco),
            ).lastrowid

    database.registrar_venda(
        periodo_id,
        1,
        [
            {
                "produto_id": produtos["A"],
                "codigo": "A",
                "nome": "Produto financeiro",
                "quantidade": 2,
                "preco_unit": 10,
            }
        ],
        "Pix",
        responsavel="Maria",
        data="01/01/2026",
    )
    database.registrar_venda(
        periodo_id,
        2,
        [
            {
                "produto_id": produtos["A"],
                "codigo": "A",
                "nome": "Produto financeiro",
                "quantidade": 2,
                "preco_unit": 10,
            },
            {
                "produto_id": produtos["B"],
                "codigo": "B",
                "nome": "Produto removido",
                "quantidade": 1,
                "preco_unit": 5,
            },
        ],
        "Credito",
        responsavel="Maria",
        data="01/01/2026",
    )
    database.registrar_venda(
        periodo_id,
        3,
        [
            {
                "produto_id": produtos["C"],
                "codigo": "C",
                "nome": "Produto cancelado",
                "quantidade": 1,
                "preco_unit": 7,
            }
        ],
        "Pix",
        responsavel="Maria",
        data="01/01/2026",
    )

    detalhe = vendas_service.obter_detalhe_venda(periodo_id, 2)
    linhas = {item["code"]: item["line_id"] for item in detalhe["items"]}
    vendas_service.alterar_pagamento_venda(
        periodo_id,
        2,
        "Dinheiro",
        valor_recebido=10,
        troco=0,
        responsavel="Ana",
    )
    vendas_service.alterar_quantidade_item_venda(
        periodo_id,
        2,
        linhas["A"],
        1,
        responsavel="Ana",
    )
    vendas_service.remover_item_venda(
        periodo_id,
        2,
        linhas["B"],
        responsavel="Ana",
    )
    vendas_service.cancelar_venda(periodo_id, 3, responsavel="Ana")
    return periodo_id, temp, original


def test_fechamento_financeiro_usa_valores_corrigidos_e_separa_canceladas():
    periodo_id, temp, original = _preparar_periodo_com_correcoes()
    try:
        fechamento = relatorios_service.obter_fechamento_financeiro(periodo_id)

        assert fechamento["period_id"] == periodo_id
        assert fechamento["financial_movement"] == {
            "transactions": 2,
            "total": 30.0,
            "corrected_transactions": 1,
            "payment_summary": {
                "Pix": {"transactions": 1, "total": 20.0},
                "Dinheiro": {"transactions": 1, "total": 10.0},
            },
        }
        assert len(fechamento["cancelled_sales"]) == 1
        cancelada = fechamento["cancelled_sales"][0]
        assert cancelada == {
            "sale_number": 3,
            "sold_at": {
                "date": "01/01/2026",
                "time": cancelada["sold_at"]["time"],
            },
            "responsible": "Maria",
            "payment_summary": "Pix",
            "total": 7.0,
            "status": "cancelled",
        }
        assert cancelada["sold_at"]["time"]
    finally:
        database.DB_PATH = original
        shutil.rmtree(temp, ignore_errors=True)


def test_xlsx_exclui_canceladas_do_financeiro_e_mantem_rastreabilidade():
    periodo_id, temp, original = _preparar_periodo_com_correcoes()
    try:
        caminho = relatorios_service.gerar_relatorio_periodo(
            periodo_id,
            str(temp),
        )
        workbook = load_workbook(caminho, data_only=True)

        assert workbook.sheetnames == [
            "Vendas do Dia",
            "Resumo por Pagamento",
            "Vendas Canceladas",
        ]

        valores_financeiros = {
            cell.value
            for row in workbook["Vendas do Dia"].iter_rows()
            for cell in row
        }
        valores_cancelados = {
            cell.value
            for row in workbook["Vendas Canceladas"].iter_rows()
            for cell in row
        }
        resumo = workbook["Resumo por Pagamento"]
        totais_por_pagamento = {
            resumo.cell(row=row, column=2).value: resumo.cell(row=row, column=4).value
            for row in range(6, 11)
        }

        assert "Produto cancelado" not in valores_financeiros
        assert "Produto cancelado" in valores_cancelados
        assert totais_por_pagamento["Pix"] == 20
        assert totais_por_pagamento["Dinheiro"] == 10
        assert resumo.cell(row=11, column=4).value == 30
    finally:
        database.DB_PATH = original
        shutil.rmtree(temp, ignore_errors=True)
