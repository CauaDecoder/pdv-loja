import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app import database
from app.contracts import DatabaseUpgradeRequired, SCHEMA_VERSION


def test_banco_novo_cria_schema_v2_com_relacionamentos_canonicos(tmp_path, monkeypatch):
    banco = tmp_path / "loja.db"
    monkeypatch.setattr(database, "DB_PATH", banco)

    database.inicializar()

    with sqlite3.connect(banco) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert {
            row[2]
            for row in conn.execute("PRAGMA foreign_key_list(vendas_cabecalho)")
        } == {"periodos_caixa"}
        assert {
            row[2]
            for row in conn.execute("PRAGMA foreign_key_list(vendas_itens)")
        } == {"produtos", "vendas_cabecalho"}
        assert {
            row[2]
            for row in conn.execute("PRAGMA foreign_key_list(pagamentos_venda)")
        } == {"destino_formas_pagamento", "vendas_cabecalho"}

    periodo_anterior = database.obter_ou_criar_periodo_aberto("19/08/2026")
    periodo_atual = database.obter_ou_criar_periodo_aberto("20/08/2026")

    assert periodo_atual["data"] == "2026-08-20"
    with database.get_conn() as conn:
        fechado_em = conn.execute(
            "SELECT fechado_em FROM periodos_caixa WHERE id = ?",
            (periodo_anterior["id"],),
        ).fetchone()["fechado_em"]
    assert fechado_em == "2026-08-20T00:00:00"


@pytest.mark.parametrize("com_dados", [False, True])
def test_inicializacao_recusa_banco_existente_sem_versao(
    tmp_path, monkeypatch, com_dados
):
    banco = tmp_path / "legado.db"
    with sqlite3.connect(banco) as conn:
        conn.execute("CREATE TABLE produtos (id INTEGER PRIMARY KEY, nome TEXT)")
        if com_dados:
            conn.execute("INSERT INTO produtos (nome) VALUES ('Legado')")
    monkeypatch.setattr(database, "DB_PATH", banco)

    with pytest.raises(DatabaseUpgradeRequired, match="resetar_banco_local"):
        database.inicializar()


def test_venda_agrupar_produto_preserva_centavos_custo_e_idempotencia(
    tmp_path, monkeypatch
):
    banco = tmp_path / "loja.db"
    monkeypatch.setattr(database, "DB_PATH", banco)
    database.inicializar()
    produto_id = database.criar_produto(
        {
            "codigo": "P1",
            "nome": "Produto",
            "preco": 10.005,
            "custo_unitario": 2.345,
            "estoque_inicial": 10,
        }
    )
    periodo = database.obter_ou_criar_periodo_aberto("19/08/2026")
    itens = [
        {
            "produto_id": produto_id,
            "codigo": "P1",
            "nome": "Produto",
            "quantidade": quantidade,
            "preco_unit": 10.005,
        }
        for quantidade in (1, 2)
    ]
    kwargs = {
        "pagamentos": [{"forma": "Pix", "valor_centavos": 3003}],
        "chave_idempotencia": "venda-1",
        "responsavel": "Ana",
    }

    primeiro = database.registrar_venda(periodo["id"], 1, itens, "Pix", **kwargs)
    repetido = database.registrar_venda(periodo["id"], 1, itens, "Pix", **kwargs)

    assert repetido == primeiro == {
        "periodo_id": periodo["id"],
        "num_venda": 1,
        "total_centavos": 3003,
        "alertas_estoque": [],
    }
    with database.get_conn() as conn:
        item = conn.execute(
            "SELECT quantidade, preco_unit_centavos, subtotal_centavos, "
            "custo_unitario_centavos FROM vendas_itens"
        ).fetchone()
        assert dict(item) == {
            "quantidade": 3,
            "preco_unit_centavos": 1001,
            "subtotal_centavos": 3003,
            "custo_unitario_centavos": 235,
        }
        assert conn.execute("SELECT estoque FROM produtos").fetchone()[0] == 7
        assert conn.execute("SELECT COUNT(*) FROM pagamentos_venda").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM vendas").fetchone()[0] == 1


@pytest.mark.parametrize(
    ("pagamentos", "mensagem"),
    [
        (
            [{
                "forma": "Dinheiro",
                "valor_centavos": 500,
                "valor_recebido_centavos": 100,
                "troco_centavos": 0,
            }],
            "recebido menos troco",
        ),
        (
            [{
                "forma": "Pix",
                "valor_centavos": 500,
                "valor_recebido_centavos": 500,
                "troco_centavos": 0,
            }],
            "só podem ser informados para Dinheiro",
        ),
    ],
)
def test_venda_rejeita_recebido_e_troco_incoerentes(
    tmp_path, monkeypatch, pagamentos, mensagem
):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "loja.db")
    database.inicializar()
    periodo = database.obter_ou_criar_periodo_aberto("19/08/2026")

    with pytest.raises(ValueError, match=mensagem):
        database.registrar_venda(
            periodo["id"],
            1,
            [{"codigo": "X", "nome": "Avulso", "quantidade": 1, "preco_unit": 5}],
            pagamentos[0]["forma"],
            pagamentos=pagamentos,
            responsavel="Ana",
            chave_idempotencia="venda-pagamento-invalido",
        )

    assert database.totais_periodo(periodo["id"]) == {
        "transacoes": 0,
        "total": 0.0,
        "correcoes": 0,
    }


def test_venda_rejeita_numero_desatualizado_e_periodo_fechado(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "loja.db")
    database.inicializar()
    periodo = database.obter_ou_criar_periodo_aberto("19/08/2026")
    item = [{"codigo": "X", "nome": "Avulso", "quantidade": 1, "preco_unit": 5}]
    pagamento = [{
        "forma": "Dinheiro",
        "valor_centavos": 500,
        "valor_recebido_centavos": 500,
        "troco_centavos": 0,
    }]
    database.registrar_venda(
        periodo["id"], 1, item, "Dinheiro", pagamentos=pagamento,
        responsavel="Ana", chave_idempotencia="venda-1",
    )

    with pytest.raises(ValueError, match="desatualizado"):
        database.registrar_venda(
            periodo["id"], 1, item, "Dinheiro", pagamentos=pagamento,
            responsavel="Ana", chave_idempotencia="venda-2",
        )

    database.encerrar_periodo(periodo["id"], "Ana")
    with pytest.raises(ValueError, match="fechado"):
        database.registrar_venda(
            periodo["id"], 2, item, "Dinheiro", pagamentos=pagamento,
            responsavel="Ana", chave_idempotencia="venda-3",
        )


def test_venda_desfaz_cabecalho_itens_estoque_e_movimento_se_pagamento_falhar(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "loja.db")
    database.inicializar()
    produto_id = database.criar_produto(
        {"codigo": "P1", "nome": "Produto", "preco": 10, "estoque_inicial": 5}
    )
    periodo = database.obter_ou_criar_periodo_aberto("19/08/2026")
    with database.get_conn() as conn:
        tabelas = (
            "vendas_cabecalho",
            "vendas_itens",
            "pagamentos_venda",
            "movimentacoes_estoque",
            "comandos_sincronizacao",
        )
        contagens_antes = {
            tabela: conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in tabelas
        }
        conn.execute(
            """CREATE TRIGGER falhar_pagamento BEFORE INSERT ON pagamentos_venda
               BEGIN SELECT RAISE(ABORT, 'falha simulada'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="falha simulada"):
        database.registrar_venda(
            periodo["id"],
            1,
            [{
                "produto_id": produto_id,
                "codigo": "P1",
                "nome": "Produto",
                "quantidade": 2,
                "preco_unit": 10,
            }],
            "Pix",
            pagamentos=[{"forma": "Pix", "valor_centavos": 2000}],
            responsavel="Ana",
            chave_idempotencia="venda-rollback",
        )

    with database.get_conn() as conn:
        assert conn.execute("SELECT estoque FROM produtos").fetchone()[0] == 5
        for tabela, contagem in contagens_antes.items():
            assert conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0] == contagem


def test_duas_vendas_concorrentes_nao_compartilham_numero(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "loja.db")
    database.inicializar()
    periodo = database.obter_ou_criar_periodo_aberto("19/08/2026")
    barreira = Barrier(2)

    def vender(chave):
        barreira.wait()
        return database.registrar_venda(
            periodo["id"],
            1,
            [{"codigo": chave, "nome": chave, "quantidade": 1, "preco_unit": 5}],
            "Pix",
            pagamentos=[{"forma": "Pix", "valor_centavos": 500}],
            responsavel="Ana",
            chave_idempotencia=chave,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = [pool.submit(vender, chave) for chave in ("venda-a", "venda-b")]
        sucessos = 0
        erros = []
        for futuro in resultados:
            try:
                futuro.result()
                sucessos += 1
            except ValueError as erro:
                erros.append(str(erro))

    assert sucessos == 1
    assert len(erros) == 1 and "desatualizado" in erros[0]
    with database.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM vendas_cabecalho").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM pagamentos_venda").fetchone()[0] == 1


def test_reconciliacao_detecta_movimento_intermediario_adulterado(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "loja.db")
    database.inicializar()
    produto_id = database.criar_produto(
        {"codigo": "P1", "nome": "Produto", "preco": 10, "estoque_inicial": 5}
    )
    database.registrar_movimentacao_estoque(
        produto_id,
        "ENTRADA",
        2,
        responsavel="Ana",
        origem="MANUAL",
    )
    with database.get_conn() as conn:
        primeiro = conn.execute(
            "SELECT id FROM movimentacoes_estoque WHERE produto_id = ? ORDER BY id LIMIT 1",
            (produto_id,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE movimentacoes_estoque SET quantidade = quantidade + 1 WHERE id = ?",
            (primeiro,),
        )

    reconciliacao = database.reconciliar_integridade_banco()

    assert reconciliacao["ok"] is False
    assert reconciliacao["estoque_divergente"] == 1


def test_produto_armazena_dinheiro_so_em_centavos(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "loja.db")
    database.inicializar()
    produto_id = database.criar_produto(
        {"codigo": "P1", "nome": "Produto", "preco": "10.005"}
    )
    with database.get_conn() as conn:
        colunas = {row[1]: row[2] for row in conn.execute("PRAGMA table_xinfo(produtos)")}
        produto = conn.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    assert colunas["preco_centavos"] == "INTEGER"
    assert produto["preco_centavos"] == 1001
    assert produto["preco"] == 10.01
    assert produto["custo_unitario_centavos"] is None
    assert produto["custo_unitario"] is None


def test_fechamento_persiste_snapshot_e_abre_proximo_periodo_atomicamente(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "loja.db")
    database.inicializar()
    periodo = database.obter_ou_criar_periodo_aberto("19/08/2026")
    database.registrar_venda(
        periodo["id"], 1,
        [{"codigo": "X", "nome": "Avulso", "quantidade": 1, "preco_unit": 5}],
        "Pix", pagamentos=[{"forma": "Pix", "valor_centavos": 500}],
        responsavel="Ana", chave_idempotencia="venda-fechamento",
    )

    resultado = database.fechar_periodo_loja(periodo["id"], "Ana")

    assert resultado["total_vendas_centavos"] == 500
    assert resultado["total_pagamentos_centavos"] == 500
    assert resultado["custos_ausentes"] == 1
    assert resultado["margem_bruta_centavos"] is None
    with database.get_conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM fechamentos_periodo WHERE periodo_id = ?",
            (periodo["id"],),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM periodos_caixa WHERE fechado_em IS NULL"
        ).fetchone()[0] == 1

    with database.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM vendas_cabecalho").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM pagamentos_venda").fetchone()[0] == 1


def test_correcao_preserva_operador_original_e_audita_novo_operador(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "loja.db")
    database.inicializar()
    periodo = database.obter_ou_criar_periodo_aberto("19/08/2026")
    database.registrar_venda(
        periodo["id"],
        1,
        [{"codigo": "X", "nome": "Avulso", "quantidade": 1, "preco_unit": 5}],
        "Pix",
        responsavel="Maria",
        chave_idempotencia="venda-autoria",
    )

    database.atualizar_venda(
        periodo["id"],
        1,
        "Pix",
        responsavel="Ana",
    )

    with database.get_conn() as conn:
        venda = conn.execute(
            "SELECT responsavel, status FROM vendas_cabecalho"
        ).fetchone()
        correcao = conn.execute(
            "SELECT responsavel, acao FROM vendas_correcoes"
        ).fetchone()
    assert dict(venda) == {"responsavel": "Maria", "status": "Corrigida"}
    assert dict(correcao) == {
        "responsavel": "Ana",
        "acao": "ALTERAR_PAGAMENTO",
    }


def test_correcao_rejeita_dinheiro_incoerente_sem_perder_pagamento_original(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "loja.db")
    database.inicializar()
    periodo = database.obter_ou_criar_periodo_aberto("19/08/2026")
    database.registrar_venda(
        periodo["id"],
        1,
        [{"codigo": "X", "nome": "Avulso", "quantidade": 1, "preco_unit": 5}],
        "Pix",
        responsavel="Maria",
        chave_idempotencia="venda-dinheiro-incoerente",
    )

    with pytest.raises(ValueError, match="recebido menos troco"):
        database.atualizar_venda(
            periodo["id"],
            1,
            "Dinheiro",
            valor_recebido=1,
            troco=99,
            responsavel="Ana",
        )

    with database.get_conn() as conn:
        pagamento = conn.execute(
            "SELECT forma, valor_centavos FROM pagamentos_venda"
        ).fetchone()
        correcoes = conn.execute("SELECT COUNT(*) FROM vendas_correcoes").fetchone()[0]
    assert dict(pagamento) == {"forma": "Pix", "valor_centavos": 500}
    assert correcoes == 0
