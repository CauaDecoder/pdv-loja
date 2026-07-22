import shutil
import uuid
from pathlib import Path

import database
from app.services import relatorios_service, vendas_service


def test_correcao_completa_recompoe_estoque_e_separa_financeiro():
    base = Path.cwd() / ".scratch" / "tests"
    base.mkdir(parents=True, exist_ok=True)
    temp = base / f"integracao_redesign_{uuid.uuid4().hex}"
    temp.mkdir()
    db_original = database.DB_PATH
    database.DB_PATH = temp / "loja_teste.db"

    try:
        database.inicializar()
        with database.get_conn() as conn:
            periodo_id = conn.execute(
                """
                INSERT INTO periodos_caixa
                    (data, sequencia, aberto_em, responsavel)
                VALUES ('22/07/2026', 1, '2026-07-22T08:00:00', 'Maria')
                """
            ).lastrowid
            produto_a = conn.execute(
                """
                INSERT INTO produtos (codigo, nome, preco, estoque)
                VALUES ('A', 'Produto A', 10, 10)
                """
            ).lastrowid
            produto_b = conn.execute(
                """
                INSERT INTO produtos (codigo, nome, preco, estoque)
                VALUES ('B', 'Produto B', 5, 5)
                """
            ).lastrowid

        database.registrar_venda(
            periodo_id,
            1,
            [
                {
                    "produto_id": produto_a,
                    "codigo": "A",
                    "nome": "Produto A",
                    "quantidade": 2,
                    "preco_unit": 10,
                },
                {
                    "produto_id": produto_b,
                    "codigo": "B",
                    "nome": "Produto B",
                    "quantidade": 1,
                    "preco_unit": 5,
                },
            ],
            "Pix",
            responsavel="Maria",
            data="22/07/2026",
        )
        database.registrar_venda(
            periodo_id,
            2,
            [
                {
                    "produto_id": None,
                    "codigo": "SERV",
                    "nome": "Item sem estoque",
                    "quantidade": 1,
                    "preco_unit": 7,
                }
            ],
            "Dinheiro",
            responsavel="Maria",
            data="22/07/2026",
        )

        detalhe = vendas_service.obter_detalhe_venda(periodo_id, 1)
        linhas = {item["code"]: item["line_id"] for item in detalhe["items"]}
        vendas_service.alterar_pagamento_venda(
            periodo_id,
            1,
            "Credito",
            pagamento_detalhe="Visa | 1x",
            responsavel="Ana",
        )
        vendas_service.alterar_quantidade_item_venda(
            periodo_id,
            1,
            linhas["A"],
            1,
            responsavel="Ana",
        )
        vendas_service.remover_item_venda(
            periodo_id,
            1,
            linhas["B"],
            responsavel="Ana",
        )
        detalhe_cancelado = vendas_service.cancelar_venda(
            periodo_id,
            1,
            responsavel="Ana",
        )

        fechamento = relatorios_service.obter_fechamento_financeiro(periodo_id)
        with database.get_conn() as conn:
            estoques = {
                row["codigo"]: row["estoque"]
                for row in conn.execute(
                    "SELECT codigo, estoque FROM produtos ORDER BY codigo"
                ).fetchall()
            }

        assert [
            correcao["action"]
            for correcao in detalhe_cancelado["correction_history"]
        ] == [
            "alter_payment",
            "alter_item_quantity",
            "remove_item",
            "cancel_sale",
        ]
        assert estoques == {"A": 10, "B": 5}
        assert fechamento["financial_movement"] == {
            "transactions": 1,
            "total": 7.0,
            "corrected_transactions": 0,
            "payment_summary": {
                "Dinheiro": {"transactions": 1, "total": 7.0}
            },
        }
        assert [venda["sale_number"] for venda in fechamento["cancelled_sales"]] == [1]
    finally:
        database.DB_PATH = db_original
        shutil.rmtree(temp, ignore_errors=True)
