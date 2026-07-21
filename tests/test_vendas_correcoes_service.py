import shutil
import uuid
from pathlib import Path

import database
from app.services import vendas_service


def _usar_banco_temporario():
    base = Path.cwd() / ".scratch" / "tests"
    base.mkdir(parents=True, exist_ok=True)
    temp = base / f"vendas_{uuid.uuid4().hex}"
    temp.mkdir()
    original = database.DB_PATH
    database.DB_PATH = temp / "loja_teste.db"
    database.inicializar()
    return temp, original


def _limpar_banco_temporario(temp: Path, original: Path):
    database.DB_PATH = original
    shutil.rmtree(temp, ignore_errors=True)


def _criar_periodo(data="01/01/2026") -> int:
    with database.get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO periodos_caixa (data, sequencia, aberto_em, responsavel)
            VALUES (?, 1, '2026-01-01T08:00:00', 'Operador')
            """,
            (data,),
        ).lastrowid


def _criar_produto(codigo: str, nome: str, preco: float, estoque: int = 10) -> int:
    with database.get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO produtos (codigo, nome, preco, estoque)
            VALUES (?, ?, ?, ?)
            """,
            (codigo, nome, preco, estoque),
        ).lastrowid


def test_lista_vendas_correcoes_no_contrato_da_ui():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_a = _criar_produto("A", "Produto A", 12)
        produto_b = _criar_produto("B", "Produto B", 5)
        database.registrar_venda(
            periodo_id,
            1,
            [
                {
                    "produto_id": produto_a,
                    "codigo": "A",
                    "nome": "Produto A",
                    "quantidade": 2,
                    "preco_unit": 12,
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
            data="01/01/2026",
        )

        vendas = vendas_service.listar_vendas_correcoes()

        assert len(vendas) == 1
        venda = vendas[0]
        assert venda["sale_number"] == 1
        assert venda["period_id"] == periodo_id
        assert venda["sold_at"]["date"] == "01/01/2026"
        assert venda["responsible"] == "Maria"
        assert venda["payment_summary"] == "Pix"
        assert venda["total"] == 29
        assert venda["status"] == "valid"
        assert venda["item_summary"] == {
            "items": 2,
            "units": 3,
            "label": "2 itens, 3 unidades",
        }
        assert venda["available_actions"] == vendas_service.ACOES_CORRECAO
    finally:
        _limpar_banco_temporario(temp, original)


def test_detalhe_venda_expoe_itens_pagamento_status_e_historico():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 12)
        database.registrar_venda(
            periodo_id,
            1,
            [
                {
                    "produto_id": produto_id,
                    "codigo": "A",
                    "nome": "Produto A",
                    "quantidade": 2,
                    "preco_unit": 12,
                }
            ],
            "Credito",
            pagamento_detalhe="Visa 2x",
            responsavel="Joao",
            data="01/01/2026",
        )
        with database.get_conn() as conn:
            conn.execute(
                """
                UPDATE vendas
                SET status = 'corrected'
                WHERE periodo_id = ? AND num_venda = ?
                """,
                (periodo_id, 1),
            )
            conn.execute(
                """
                INSERT INTO vendas_correcoes
                (periodo_id, num_venda, acao, responsavel, criado_em, antes, depois, observacao)
                VALUES (?, 1, 'alter_payment', 'Ana', '2026-01-01T09:00:00',
                        'Pix', 'Credito | Visa 2x', 'Pagamento corrigido')
                """,
                (periodo_id,),
            )

        detalhe = vendas_service.obter_detalhe_venda(periodo_id, 1)

        assert detalhe is not None
        assert detalhe["identity"] == {"sale_number": 1, "period_id": periodo_id}
        assert detalhe["status"] == "corrected"
        assert detalhe["responsible"] == "Joao"
        assert detalhe["payment"] == {
            "method": "Credito",
            "detail": "Visa 2x",
            "received": None,
            "change": None,
        }
        assert detalhe["items"] == [
            {
                "line_id": detalhe["items"][0]["line_id"],
                "product_id": produto_id,
                "code": "A",
                "name": "Produto A",
                "quantity": 2,
                "unit_price": 12,
                "subtotal": 24,
            }
        ]
        assert detalhe["totals"] == {"items": 1, "units": 2, "total": 24}
        assert detalhe["correction_history"] == [
            {
                "id": detalhe["correction_history"][0]["id"],
                "action": "alter_payment",
                "responsible": "Ana",
                "created_at": "2026-01-01T09:00:00",
                "before": "Pix",
                "after": "Credito | Visa 2x",
                "note": "Pagamento corrigido",
            }
        ]
        assert detalhe["available_actions"] == vendas_service.ACOES_CORRECAO
    finally:
        _limpar_banco_temporario(temp, original)


def test_venda_cancelada_tem_status_explicito_e_sem_acoes_disponiveis():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 12)
        database.registrar_venda(
            periodo_id,
            1,
            [
                {
                    "produto_id": produto_id,
                    "codigo": "A",
                    "nome": "Produto A",
                    "quantidade": 1,
                    "preco_unit": 12,
                }
            ],
            "Dinheiro",
            responsavel="Maria",
            data="01/01/2026",
        )
        with database.get_conn() as conn:
            conn.execute(
                """
                UPDATE vendas
                SET status = 'cancelled'
                WHERE periodo_id = ? AND num_venda = ?
                """,
                (periodo_id, 1),
            )

        vendas = vendas_service.listar_vendas_correcoes({"status": "cancelled"})
        detalhe = vendas_service.obter_detalhe_venda(periodo_id, 1)

        assert vendas[0]["status"] == "cancelled"
        assert vendas[0]["available_actions"] == []
        assert detalhe is not None
        assert detalhe["status"] == "cancelled"
        assert detalhe["available_actions"] == []
    finally:
        _limpar_banco_temporario(temp, original)
