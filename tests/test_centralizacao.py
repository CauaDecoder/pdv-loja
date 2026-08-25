import tempfile
from pathlib import Path

import pytest

from app import database
from app.offline import OfflineQueue
from app.remote import CentralUnavailable


@pytest.fixture
def isolated_db():
    original = database.DB_PATH
    with tempfile.TemporaryDirectory() as directory:
        database.DB_PATH = Path(directory) / "central.db"
        database.inicializar()
        yield
    database.DB_PATH = original


def test_venda_mista_registra_parcelas_e_filtra_por_forma(isolated_db):
    periodo = database.obter_ou_criar_periodo_aberto("2026-08-12")
    destinos = {row["nome"]: row["id"] for row in database.listar_destinos_financeiros()}
    database.registrar_venda(
        periodo["id"], 1,
        [{"codigo": "A", "nome": "A", "quantidade": 1, "preco_unit": 100, "produto_id": None}],
        "Mais de uma forma",
        pagamentos=[
            {
                "forma": "Dinheiro",
                "valor_centavos": 3000,
                "destino_id": destinos["Caixa fisico"],
                "valor_recebido_centavos": 3000,
                "troco_centavos": 0,
            },
            {"forma": "Pix", "valor_centavos": 7000, "destino_id": destinos["Conta Pix"]},
        ],
        responsavel="Ana",
        chave_idempotencia="mista-1",
        data="2026-08-12",
    )
    relatorio = database.relatorio_vendas_filtrado("2026-08-12", "2026-08-12", "Dinheiro")
    assert relatorio["total_centavos"] == 3000
    assert len(relatorio["pagamentos"]) == 1


def test_relatorio_nao_multiplica_pagamento_por_quantidade_de_itens(isolated_db):
    periodo = database.obter_ou_criar_periodo_aberto("2026-08-12")
    database.registrar_venda(
        periodo["id"], 1,
        [
            {"codigo": "A", "nome": "A", "quantidade": 1, "preco_unit": 30, "produto_id": None},
            {"codigo": "B", "nome": "B", "quantidade": 1, "preco_unit": 70, "produto_id": None},
        ],
        "Pix",
        pagamentos=[{"forma": "Pix", "valor_centavos": 10000}],
        responsavel="Ana",
        chave_idempotencia="relatorio-1",
        data="2026-08-12",
    )
    relatorio = database.relatorio_vendas_filtrado("2026-08-12", "2026-08-12", "Pix")
    assert relatorio["total_centavos"] == 10000
    assert relatorio["vendas"][0]["total"] == 100
    assert len(relatorio["itens"]) == 2


def test_chave_idempotencia_nao_duplica_venda(isolated_db):
    periodo = database.obter_ou_criar_periodo_aberto("2026-08-12")
    dados = [{"codigo": "A", "nome": "A", "quantidade": 1, "preco_unit": 10, "produto_id": None}]
    kwargs = {
        "pagamentos": [{"forma": "Pix", "valor_centavos": 1000}],
        "chave_idempotencia": "x",
        "responsavel": "Ana",
    }
    database.registrar_venda(periodo["id"], 1, dados, "Pix", **kwargs)
    database.registrar_venda(periodo["id"], 1, dados, "Pix", **kwargs)
    assert len(database.vendas_do_periodo(periodo["id"])) == 1
    with database.get_conn() as conn:
        cabecalhos = conn.execute("SELECT uuid FROM vendas_cabecalho").fetchall()
        itens = conn.execute("SELECT preco_unit_centavos, subtotal_centavos FROM vendas_itens").fetchall()
        assert [row["uuid"] for row in cabecalhos] == ["x"]
        assert dict(itens[0]) == {"preco_unit_centavos": 1000, "subtotal_centavos": 1000}


def test_fila_offline_preserva_ordem_e_remove_somente_enviado(tmp_path):
    fila = OfflineQueue(tmp_path / "terminal.db")
    fila.enqueue_sale({"itens": [], "pagamentos": [], "chave_idempotencia": "a"})
    fila.enqueue_sale({"itens": [], "pagamentos": [], "chave_idempotencia": "b"})

    class Cliente:
        def __init__(self):
            self.chaves = []

        def create_sale(self, payload):
            self.chaves.append(payload["chave_idempotencia"])
            if len(self.chaves) == 2:
                raise CentralUnavailable("offline")

    cliente = Cliente()
    assert fila.sync(cliente) == 1
    assert [item["chave_idempotencia"] for item in fila.pending()] == ["b"]
