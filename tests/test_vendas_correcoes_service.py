import shutil
import sqlite3
import uuid
from pathlib import Path

import pytest
from app import database
from app.services import vendas_service


@pytest.fixture(autouse=True)
def _uuid_idempotente_em_vendas(monkeypatch):
    registrar = database.registrar_venda

    def registrar_com_uuid(*args, **kwargs):
        kwargs.setdefault("chave_idempotencia", str(uuid.uuid4()))
        kwargs.setdefault("responsavel", "Operador")
        return registrar(*args, **kwargs)

    monkeypatch.setattr(database, "registrar_venda", registrar_com_uuid)


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
    return int(database.obter_ou_criar_periodo_aberto(data)["id"])


def _criar_produto(codigo: str, nome: str, preco: float, estoque: int = 10) -> int:
    with database.get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO produtos (codigo, nome, preco_centavos, estoque)
            VALUES (?, ?, ?, ?)
            """,
            (codigo, nome, round(preco * 100), estoque),
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


def test_lista_vendas_correcoes_filtra_intervalo_entre_meses_com_data_real():
    temp, original = _usar_banco_temporario()
    try:
        produto_id = _criar_produto("A", "Produto A", 10, estoque=20)
        periodo_julho = _criar_periodo("31/07/2026")
        item = [
            {
                "produto_id": produto_id,
                "codigo": "A",
                "nome": "Produto A",
                "quantidade": 1,
                "preco_unit": 10,
            }
        ]
        database.registrar_venda(
            periodo_julho, 1, item, "Pix", data="31/07/2026"
        )
        fechamento = database.fechar_periodo_loja(
            periodo_julho, "Operador", "2026-08-01T08:00:00"
        )
        periodo_agosto = fechamento["proximo_periodo_id"]
        database.registrar_venda(
            periodo_agosto, 1, item, "Pix", data="01/08/2026"
        )

        vendas = vendas_service.listar_vendas_correcoes(
            {"data_inicio": "01/08/2026", "data_fim": "31/08/2026"}
        )

        assert [venda["sold_at"]["date"] for venda in vendas] == ["01/08/2026"]
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
                UPDATE vendas_cabecalho
                SET status = 'Corrigida'
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
        assert detalhe["payment"]["method"] == "Credito"
        assert detalhe["payment"]["detail"] == "Visa 2x"
        assert detalhe["payment"]["received"] is None
        assert detalhe["payment"]["change"] is None
        assert len(detalhe["payment"]["installments"]) == 1
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
            valor_recebido=12,
            troco=0,
            responsavel="Maria",
            data="01/01/2026",
        )
        with database.get_conn() as conn:
            conn.execute(
                """
                UPDATE vendas_cabecalho
                SET status = 'Cancelada'
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


def test_registrar_correcao_persiste_status_e_auditoria_estruturada():
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
                    "quantidade": 1,
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

        detalhe = vendas_service.registrar_correcao_venda(
            periodo_id,
            1,
            acao="alter_payment",
            responsavel="Ana",
            antes={"method": "Pix"},
            depois={"detail": "Visa 2x", "method": "Credito"},
            observacao="Pagamento conferido no comprovante",
            criado_em="2026-01-01T09:00:00",
        )

        with database.get_conn() as conn:
            statuses = conn.execute(
                """
                SELECT DISTINCT status
                FROM vendas
                WHERE periodo_id = ? AND num_venda = 1
                """,
                (periodo_id,),
            ).fetchall()

        assert [row["status"] for row in statuses] == ["Corrigida"]
        assert detalhe["status"] == "corrected"
        assert detalhe["correction_history"] == [
            {
                "id": detalhe["correction_history"][0]["id"],
                "action": "alter_payment",
                "responsible": "Ana",
                "created_at": "2026-01-01T09:00:00",
                "before": {"method": "Pix"},
                "after": {"detail": "Visa 2x", "method": "Credito"},
                "note": "Pagamento conferido no comprovante",
            }
        ]
    finally:
        _limpar_banco_temporario(temp, original)


def test_registrar_cancelamento_marca_status_sem_apagar_venda():
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
            valor_recebido=12,
            troco=0,
            responsavel="Maria",
            data="01/01/2026",
        )

        detalhe = vendas_service.registrar_correcao_venda(
            periodo_id,
            1,
            acao="cancel_sale",
            responsavel="Ana",
            antes={"status": "valid"},
            depois={"status": "cancelled"},
            novo_status="cancelled",
        )

        assert detalhe["status"] == "cancelled"
        assert detalhe["items"][0]["name"] == "Produto A"
        assert detalhe["available_actions"] == []
    finally:
        _limpar_banco_temporario(temp, original)


def test_falha_na_auditoria_desfaz_atualizacao_de_status():
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
            "Pix",
            data="01/01/2026",
        )
        with database.get_conn() as conn:
            conn.execute(
                """
                CREATE TRIGGER impedir_auditoria
                BEFORE INSERT ON vendas_correcoes
                BEGIN
                    SELECT RAISE(ABORT, 'falha simulada');
                END
                """
            )

        try:
            vendas_service.registrar_correcao_venda(
                periodo_id,
                1,
                acao="alter_payment",
                responsavel="Ana",
                antes="Pix",
                depois="Credito",
            )
            raise AssertionError("A falha simulada deveria interromper a correcao.")
        except sqlite3.IntegrityError:
            pass

        with database.get_conn() as conn:
            statuses = conn.execute(
                """
                SELECT DISTINCT status
                FROM vendas
                WHERE periodo_id = ? AND num_venda = 1
                """,
                (periodo_id,),
            ).fetchall()
            total_historico = conn.execute(
                "SELECT COUNT(*) FROM vendas_correcoes"
            ).fetchone()[0]

        assert [row["status"] for row in statuses] == ["Ativa"]
        assert total_historico == 0
    finally:
        _limpar_banco_temporario(temp, original)


def test_inicializacao_v2_repetida_preserva_venda_e_schema_canonico():
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
            "Pix",
            data="01/01/2026",
        )
        database.inicializar()

        with database.get_conn() as conn:
            venda = conn.execute(
                """
                SELECT nome, status
                FROM vendas
                WHERE periodo_id = ? AND num_venda = 1
                """,
                (periodo_id,),
            ).fetchone()
            colunas_historico = {
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(vendas_correcoes)"
                ).fetchall()
            }

        assert dict(venda) == {"nome": "Produto A", "status": "Ativa"}
        assert {
            "periodo_id",
            "num_venda",
            "acao",
            "responsavel",
            "criado_em",
            "antes",
            "depois",
            "observacao",
        } <= colunas_historico
    finally:
        _limpar_banco_temporario(temp, original)


def test_cancelar_venda_preserva_historico_devolve_estoque_e_exclui_financeiro():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_a = _criar_produto("A", "Produto A", 12, estoque=10)
        produto_b = _criar_produto("B", "Produto B", 5, estoque=7)
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

        detalhe = vendas_service.cancelar_venda(
            periodo_id,
            1,
            responsavel="Ana",
            observacao="Venda registrada em duplicidade",
        )

        with database.get_conn() as conn:
            estoques = {
                row["codigo"]: row["estoque"]
                for row in conn.execute(
                    "SELECT codigo, estoque FROM produtos ORDER BY codigo"
                ).fetchall()
            }
            linhas_venda = conn.execute(
                "SELECT status FROM vendas WHERE periodo_id = ? AND num_venda = 1",
                (periodo_id,),
            ).fetchall()
        cancelamentos = [
            dict(row)
            for row in database.listar_movimentacoes_estoque(tipo="CANCELAMENTO")
        ]

        assert detalhe["status"] == "cancelled"
        assert detalhe["totals"] == {"items": 2, "units": 3, "total": 29}
        assert detalhe["available_actions"] == []
        assert detalhe["correction_history"][-1]["action"] == "cancel_sale"
        assert detalhe["correction_history"][-1]["responsible"] == "Ana"
        antes = detalhe["correction_history"][-1]["before"]
        assert antes["status"] == "valid"
        assert antes["payment"]["method"] == "Pix"
        assert detalhe["correction_history"][-1]["after"] == {
            "status": "cancelled",
            "stock_returned": [
                {"product_id": produto_a, "quantity": 2},
                {"product_id": produto_b, "quantity": 1},
            ],
        }
        assert detalhe["correction_history"][-1]["note"] == "Venda registrada em duplicidade"
        assert estoques == {"A": 10, "B": 7}
        assert [row["status"] for row in linhas_venda] == ["Cancelada", "Cancelada"]
        assert {
            (row["produto_id"], row["quantidade"], row["referencia"], row["origem"])
            for row in cancelamentos
        } == {
            (produto_a, 2, f"CANCELAMENTO:{periodo_id}:1:{produto_a}", "CORRECAO_POS_VENDA"),
            (produto_b, 1, f"CANCELAMENTO:{periodo_id}:1:{produto_b}", "CORRECAO_POS_VENDA"),
        }
        assert database.totais_periodo(periodo_id) == {
            "transacoes": 0,
            "total": 0.0,
            "correcoes": 1,
        }
        assert database.resumo_do_periodo(periodo_id) == {}
    finally:
        _limpar_banco_temporario(temp, original)


def test_venda_cancelada_bloqueia_novo_cancelamento_e_outras_correcoes():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 12, estoque=10)
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
            "Pix",
            data="01/01/2026",
        )
        vendas_service.cancelar_venda(periodo_id, 1, responsavel="Ana")

        for correcao in (
            lambda: vendas_service.cancelar_venda(periodo_id, 1, responsavel="Ana"),
            lambda: vendas_service.registrar_correcao_venda(
                periodo_id,
                1,
                acao="alter_payment",
                responsavel="Ana",
                antes="Pix",
                depois="Credito",
            ),
        ):
            try:
                correcao()
                raise AssertionError("Venda cancelada deveria rejeitar nova correcao.")
            except ValueError as exc:
                assert str(exc) == "Venda cancelada nao pode receber nova correcao."

        with database.get_conn() as conn:
            estoque = conn.execute(
                "SELECT estoque FROM produtos WHERE id = ?", (produto_id,)
            ).fetchone()["estoque"]
            total_historico = conn.execute(
                "SELECT COUNT(*) FROM vendas_correcoes"
            ).fetchone()[0]
        assert estoque == 10
        assert total_historico == 1
    finally:
        _limpar_banco_temporario(temp, original)


def test_falha_na_auditoria_desfaz_cancelamento_e_devolucao_de_estoque():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 12, estoque=10)
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
            "Pix",
            data="01/01/2026",
        )
        with database.get_conn() as conn:
            conn.execute(
                """
                CREATE TRIGGER impedir_auditoria_cancelamento
                BEFORE INSERT ON vendas_correcoes
                BEGIN
                    SELECT RAISE(ABORT, 'falha simulada');
                END
                """
            )

        try:
            vendas_service.cancelar_venda(periodo_id, 1, responsavel="Ana")
            raise AssertionError("A falha simulada deveria interromper o cancelamento.")
        except sqlite3.IntegrityError:
            pass

        with database.get_conn() as conn:
            venda = conn.execute(
                "SELECT DISTINCT status FROM vendas WHERE periodo_id = ? AND num_venda = 1",
                (periodo_id,),
            ).fetchone()
            estoque = conn.execute(
                "SELECT estoque FROM produtos WHERE id = ?", (produto_id,)
            ).fetchone()["estoque"]
            cancelamentos = conn.execute(
                "SELECT COUNT(*) FROM movimentacoes_estoque WHERE tipo = 'CANCELAMENTO'"
            ).fetchone()[0]

        assert venda["status"] == "Ativa"
        assert estoque == 8
        assert cancelamentos == 0
    finally:
        _limpar_banco_temporario(temp, original)


def test_cancelar_venda_legada_sem_produto_vinculado_preserva_compatibilidade():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        database.registrar_venda(
            periodo_id,
            1,
            [
                {
                    "codigo": "LEGADO",
                    "nome": "Produto legado",
                    "quantidade": 1,
                    "preco_unit": 12,
                }
            ],
            "Pix",
            data="01/01/2026",
        )

        detalhe = vendas_service.cancelar_venda(
            periodo_id, 1, responsavel="Ana"
        )

        assert detalhe["status"] == "cancelled"
        assert detalhe["items"][0]["product_id"] is None
        assert detalhe["correction_history"][-1]["after"] == {
            "status": "cancelled",
            "stock_returned": [],
        }
        assert database.listar_movimentacoes_estoque(tipo="CANCELAMENTO") == []
        assert database.totais_periodo(periodo_id) == {
            "transacoes": 0,
            "total": 0.0,
            "correcoes": 1,
        }
    finally:
        _limpar_banco_temporario(temp, original)


def test_alterar_pagamento_preserva_responsavel_original_e_registra_auditoria():
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
            "Pix",
            responsavel="Maria",
            data="01/01/2026",
        )

        detalhe = vendas_service.alterar_pagamento_venda(
            periodo_id,
            1,
            "Credito",
            pagamento_detalhe="Visa | 2x",
            responsavel="Ana",
            observacao="Forma registrada incorretamente",
        )

        assert detalhe["status"] == "corrected"
        assert detalhe["responsible"] == "Maria"
        assert detalhe["payment"]["method"] == "Credito"
        assert detalhe["payment"]["detail"] == "Visa | 2x"
        assert detalhe["payment"]["received"] is None
        assert detalhe["payment"]["change"] is None
        assert len(detalhe["payment"]["installments"]) == 1
        assert len(detalhe["correction_history"]) == 1
        correcao = detalhe["correction_history"][0]
        assert correcao["action"] == "alter_payment"
        assert correcao["responsible"] == "Ana"
        assert correcao["created_at"]
        assert correcao["before"]["method"] == "Pix"
        assert correcao["before"]["detail"] == ""
        assert correcao["before"]["received"] is None
        assert correcao["before"]["change"] is None
        assert len(correcao["before"]["installments"]) == 1
        assert correcao["after"] == detalhe["payment"]
        assert correcao["note"] == "Forma registrada incorretamente"
    finally:
        _limpar_banco_temporario(temp, original)


def test_alterar_pagamento_atualiza_todas_as_linhas_e_totais_por_forma():
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

        vendas_service.alterar_pagamento_venda(
            periodo_id,
            1,
            "Dinheiro",
            pagamento_detalhe="Recebido R$ 30,00; troco R$ 1,00",
            valor_recebido=30,
            troco=1,
            responsavel="Ana",
        )

        linhas = database.vendas_do_periodo(periodo_id)
        assert {linha["pagamento"] for linha in linhas} == {"Dinheiro"}
        assert {linha["status"] for linha in linhas} == {"Corrigida"}
        assert database.resumo_do_periodo(periodo_id) == {
            "Dinheiro": {
                "pagamento": "Dinheiro",
                "transacoes": 1,
                "total": 29.0,
            }
        }
    finally:
        _limpar_banco_temporario(temp, original)


def test_alterar_pagamento_para_venda_mista_persiste_parcelas_e_auditoria():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 20)
        with database.get_conn() as conn:
            destinos = {
                row["nome"]: int(row["id"])
                for row in conn.execute(
                    "SELECT id, nome FROM destinos_financeiros"
                ).fetchall()
            }
        database.registrar_venda(
            periodo_id,
            1,
            [
                {
                    "produto_id": produto_id,
                    "codigo": "A",
                    "nome": "Produto A",
                    "quantidade": 1,
                    "preco_unit": 20,
                }
            ],
            "Pix",
            responsavel="Maria",
            data="01/01/2026",
        )

        detalhe = vendas_service.alterar_pagamento_venda(
            periodo_id,
            1,
            "Mais de uma forma",
            pagamentos=[
                {
                    "forma": "Pix",
                    "destino_id": destinos["Conta Pix"],
                    "valor_centavos": 1200,
                },
                {
                    "forma": "Dinheiro",
                    "destino_id": destinos["Caixa fisico"],
                    "valor_centavos": 800,
                    "valor_recebido_centavos": 1000,
                    "troco_centavos": 200,
                },
            ],
            responsavel="Ana",
            observacao="Pagamento dividido após conferência",
        )

        assert detalhe["payment"] == {
            "method": "Mais de uma forma",
            "detail": "Pix + Dinheiro",
            "received": 10.0,
            "change": 2.0,
            "installments": [
                {
                    "method": "Pix",
                    "destination_id": destinos["Conta Pix"],
                    "destination": "Conta Pix",
                    "value_centavos": 1200,
                    "detail": "",
                    "received_centavos": None,
                    "change_centavos": None,
                },
                {
                    "method": "Dinheiro",
                    "destination_id": destinos["Caixa fisico"],
                    "destination": "Caixa fisico",
                    "value_centavos": 800,
                    "detail": "",
                    "received_centavos": 1000,
                    "change_centavos": 200,
                },
            ],
        }
        assert detalhe["correction_history"][-1]["after"] == detalhe["payment"]
    finally:
        _limpar_banco_temporario(temp, original)


def test_alterar_item_de_venda_mista_recebe_novas_parcelas_na_mesma_transacao():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 10, estoque=10)
        with database.get_conn() as conn:
            destinos = {
                row["nome"]: int(row["id"])
                for row in conn.execute(
                    "SELECT id, nome FROM destinos_financeiros"
                ).fetchall()
            }
        database.registrar_venda(
            periodo_id,
            1,
            [{
                "produto_id": produto_id,
                "codigo": "A",
                "nome": "Produto A",
                "quantidade": 2,
                "preco_unit": 10,
            }],
            "Mais de uma forma",
            pagamentos=[
                {
                    "forma": "Pix",
                    "destino_id": destinos["Conta Pix"],
                    "valor_centavos": 1200,
                },
                {
                    "forma": "Dinheiro",
                    "destino_id": destinos["Caixa fisico"],
                    "valor_centavos": 800,
                    "valor_recebido_centavos": 1000,
                    "troco_centavos": 200,
                },
            ],
            responsavel="Maria",
        )
        detalhe_antes = vendas_service.obter_detalhe_venda(periodo_id, 1)
        line_id = detalhe_antes["items"][0]["line_id"]

        detalhe = vendas_service.alterar_quantidade_item_venda(
            periodo_id,
            1,
            line_id,
            1,
            pagamentos=[
                {
                    "forma": "Pix",
                    "destino_id": destinos["Conta Pix"],
                    "valor_centavos": 600,
                },
                {
                    "forma": "Dinheiro",
                    "destino_id": destinos["Caixa fisico"],
                    "valor_centavos": 400,
                    "valor_recebido_centavos": 500,
                    "troco_centavos": 100,
                },
            ],
            responsavel="Ana",
        )

        assert detalhe["totals"]["total"] == 10
        assert [p["value_centavos"] for p in detalhe["payment"]["installments"]] == [600, 400]
        assert detalhe["correction_history"][-1]["before"]["payment"]["method"] == "Mais de uma forma"
        assert detalhe["correction_history"][-1]["after"]["payment"] == detalhe["payment"]
        with database.get_conn() as conn:
            assert conn.execute(
                "SELECT estoque FROM produtos WHERE id = ?", (produto_id,)
            ).fetchone()[0] == 9
    finally:
        _limpar_banco_temporario(temp, original)


def test_alterar_pagamento_rejeita_recebido_e_troco_inconciliaveis():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 10)
        database.registrar_venda(
            periodo_id,
            1,
            [
                {
                    "produto_id": produto_id,
                    "codigo": "A",
                    "nome": "Produto A",
                    "quantidade": 1,
                    "preco_unit": 10,
                }
            ],
            "Pix",
            responsavel="Maria",
        )

        try:
            vendas_service.alterar_pagamento_venda(
                periodo_id,
                1,
                "Dinheiro",
                valor_recebido=10,
                troco=1,
                responsavel="Ana",
            )
            assert False, "Pagamento em dinheiro inconsistente deveria ser rejeitado."
        except ValueError as exc:
            assert str(exc) == (
                "Valor recebido menos troco deve ser igual ao valor em Dinheiro."
            )

        detalhe = vendas_service.obter_detalhe_venda(periodo_id, 1)
        assert detalhe["payment"]["method"] == "Pix"
        assert detalhe["correction_history"] == []
    finally:
        _limpar_banco_temporario(temp, original)


def test_alterar_pagamento_rejeita_destino_incompativel_com_forma():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 10)
        with database.get_conn() as conn:
            conta_pix = int(
                conn.execute(
                    "SELECT id FROM destinos_financeiros WHERE nome = 'Conta Pix'"
                ).fetchone()[0]
            )
        database.registrar_venda(
            periodo_id,
            1,
            [
                {
                    "produto_id": produto_id,
                    "codigo": "A",
                    "nome": "Produto A",
                    "quantidade": 1,
                    "preco_unit": 10,
                }
            ],
            "Pix",
            responsavel="Maria",
        )

        try:
            vendas_service.alterar_pagamento_venda(
                periodo_id,
                1,
                "Dinheiro",
                destino_id=conta_pix,
                valor_recebido=10,
                troco=0,
                responsavel="Ana",
            )
            assert False, "Destino incompatível deveria ser rejeitado."
        except ValueError as exc:
            assert str(exc) == (
                "Destino financeiro ativo e compatível com Dinheiro não encontrado."
            )
    finally:
        _limpar_banco_temporario(temp, original)


def test_alterar_pagamento_rejeita_venda_inexistente_ou_cancelada():
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
            "Pix",
            responsavel="Maria",
            data="01/01/2026",
        )
        with database.get_conn() as conn:
            conn.execute(
                "UPDATE vendas_cabecalho SET status = 'Cancelada' "
                "WHERE periodo_id = ? AND num_venda = 1",
                (periodo_id,),
            )

        try:
            vendas_service.alterar_pagamento_venda(
                periodo_id, 99, "Credito", responsavel="Ana"
            )
            assert False, "Venda inexistente deveria ser rejeitada"
        except ValueError as exc:
            assert str(exc) == "Venda nao encontrada."

        try:
            vendas_service.alterar_pagamento_venda(
                periodo_id, 1, "Credito", responsavel="Ana"
            )
            assert False, "Venda cancelada deveria ser rejeitada"
        except ValueError as exc:
            assert str(exc) == "Venda cancelada nao pode receber nova correcao."

        assert vendas_service.obter_detalhe_venda(periodo_id, 1)["correction_history"] == []
    finally:
        _limpar_banco_temporario(temp, original)


def test_alterar_quantidade_item_ajusta_estoque_somente_pela_diferenca():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 12, estoque=10)
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
            "Pix",
            responsavel="Maria",
            data="01/01/2026",
        )
        line_id = vendas_service.obter_detalhe_venda(periodo_id, 1)["items"][0][
            "line_id"
        ]

        detalhe = vendas_service.alterar_quantidade_item_venda(
            periodo_id,
            1,
            line_id,
            5,
            responsavel="Ana",
            observacao="Leitor registrou quantidade menor",
        )
        detalhe = vendas_service.alterar_quantidade_item_venda(
            periodo_id, 1, line_id, 1, responsavel="Ana"
        )

        with database.get_conn() as conn:
            estoque = conn.execute(
                "SELECT estoque FROM produtos WHERE id = ?", (produto_id,)
            ).fetchone()["estoque"]
        ajustes = [
            dict(row) for row in database.listar_movimentacoes_estoque(tipo="AJUSTE")
        ]

        assert detalhe["status"] == "corrected"
        assert detalhe["items"][0]["quantity"] == 1
        assert detalhe["items"][0]["subtotal"] == 12
        assert detalhe["totals"] == {"items": 1, "units": 1, "total": 12}
        assert estoque == 9
        assert [row["quantidade"] for row in reversed(ajustes)] == [-3, 4]
        assert {row["origem"] for row in ajustes} == {"CORRECAO_POS_VENDA"}
        assert detalhe["correction_history"][0]["action"] == "alter_item_quantity"
        assert detalhe["correction_history"][0]["responsible"] == "Ana"
        assert detalhe["correction_history"][0]["before"]["quantity"] == 2
        assert detalhe["correction_history"][0]["after"]["quantity"] == 5
        assert detalhe["correction_history"][0]["note"] == (
            "Leitor registrou quantidade menor"
        )
    finally:
        _limpar_banco_temporario(temp, original)


def test_remover_item_restaura_estoque_e_preserva_auditoria():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_a = _criar_produto("A", "Produto A", 12, estoque=10)
        produto_b = _criar_produto("B", "Produto B", 5, estoque=7)
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
            data="01/01/2026",
        )
        detalhe_inicial = vendas_service.obter_detalhe_venda(periodo_id, 1)
        line_id = next(
            item["line_id"]
            for item in detalhe_inicial["items"]
            if item["product_id"] == produto_a
        )

        detalhe = vendas_service.remover_item_venda(
            periodo_id,
            1,
            line_id,
            responsavel="Ana",
            observacao="Produto incluido por engano",
        )

        with database.get_conn() as conn:
            estoques = {
                row["codigo"]: row["estoque"]
                for row in conn.execute(
                    "SELECT codigo, estoque FROM produtos ORDER BY codigo"
                ).fetchall()
            }
        ajustes = [
            dict(row) for row in database.listar_movimentacoes_estoque(tipo="AJUSTE")
        ]

        assert detalhe["status"] == "corrected"
        assert [item["code"] for item in detalhe["items"]] == ["B"]
        assert detalhe["totals"] == {"items": 1, "units": 1, "total": 5}
        assert estoques == {"A": 10, "B": 6}
        assert ajustes[0]["produto_id"] == produto_a
        assert ajustes[0]["quantidade"] == 2
        assert ajustes[0]["origem"] == "CORRECAO_POS_VENDA"
        assert detalhe["correction_history"][-1]["action"] == "remove_item"
        assert detalhe["correction_history"][-1]["before"]["line_id"] == line_id
        assert detalhe["correction_history"][-1]["before"]["quantity"] == 2
        assert detalhe["correction_history"][-1]["after"] == {
            "line_id": line_id,
            "removed": True,
        }
        assert detalhe["correction_history"][-1]["responsible"] == "Ana"
        assert detalhe["correction_history"][-1]["created_at"]
    finally:
        _limpar_banco_temporario(temp, original)


def test_correcao_item_rejeita_quantidade_invalida_venda_inexistente_e_cancelada():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 12, estoque=10)
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
            "Pix",
            data="01/01/2026",
        )
        line_id = vendas_service.obter_detalhe_venda(periodo_id, 1)["items"][0][
            "line_id"
        ]

        operacoes_invalidas = (
            (
                lambda: vendas_service.alterar_quantidade_item_venda(
                    periodo_id, 1, line_id, -1, responsavel="Ana"
                ),
                "Quantidade do item deve ser um numero inteiro positivo.",
            ),
            (
                lambda: vendas_service.alterar_quantidade_item_venda(
                    periodo_id, 99, line_id, 1, responsavel="Ana"
                ),
                "Venda nao encontrada.",
            ),
            (
                lambda: vendas_service.remover_item_venda(
                    periodo_id, 1, line_id, responsavel="Ana"
                ),
                "A venda deve manter ao menos um item; use Cancelar venda.",
            ),
        )
        for operacao, mensagem in operacoes_invalidas:
            try:
                operacao()
                raise AssertionError("Correcao invalida deveria ser rejeitada.")
            except ValueError as exc:
                assert str(exc) == mensagem

        vendas_service.cancelar_venda(periodo_id, 1, responsavel="Ana")
        try:
            vendas_service.alterar_quantidade_item_venda(
                periodo_id, 1, line_id, 1, responsavel="Ana"
            )
            raise AssertionError("Venda cancelada deveria rejeitar correcao de item.")
        except ValueError as exc:
            assert str(exc) == "Venda cancelada nao pode receber nova correcao."
    finally:
        _limpar_banco_temporario(temp, original)


def test_falha_na_auditoria_desfaz_correcao_de_item_e_ajuste_de_estoque():
    temp, original = _usar_banco_temporario()
    try:
        periodo_id = _criar_periodo()
        produto_id = _criar_produto("A", "Produto A", 12, estoque=10)
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
            "Pix",
            data="01/01/2026",
        )
        line_id = vendas_service.obter_detalhe_venda(periodo_id, 1)["items"][0][
            "line_id"
        ]
        with database.get_conn() as conn:
            conn.execute(
                """
                CREATE TRIGGER impedir_auditoria_item
                BEFORE INSERT ON vendas_correcoes
                BEGIN
                    SELECT RAISE(ABORT, 'falha simulada');
                END
                """
            )

        try:
            vendas_service.alterar_quantidade_item_venda(
                periodo_id, 1, line_id, 5, responsavel="Ana"
            )
            raise AssertionError("A falha simulada deveria interromper a correcao.")
        except sqlite3.IntegrityError:
            pass

        with database.get_conn() as conn:
            venda = conn.execute(
                "SELECT quantidade, subtotal, status FROM vendas WHERE id = ?",
                (line_id,),
            ).fetchone()
            estoque = conn.execute(
                "SELECT estoque FROM produtos WHERE id = ?", (produto_id,)
            ).fetchone()["estoque"]
            ajustes = conn.execute(
                """
                SELECT COUNT(*) FROM movimentacoes_estoque
                WHERE origem = 'CORRECAO_POS_VENDA'
                """
            ).fetchone()[0]

        assert dict(venda) == {"quantidade": 2, "subtotal": 24, "status": "Ativa"}
        assert estoque == 8
        assert ajustes == 0
    finally:
        _limpar_banco_temporario(temp, original)
