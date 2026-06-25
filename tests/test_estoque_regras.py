import tempfile
from pathlib import Path

import database
from estoque import calculos


DISPONIVEL = "Dispon\u00edvel"
CUSTO_MEDIO = "Custo M\u00e9dio"


def _usar_banco_temporario():
    temp = tempfile.TemporaryDirectory()
    original = database.DB_PATH
    database.DB_PATH = Path(temp.name) / "loja_teste.db"
    database.inicializar()
    return temp, original


def test_mapeamento_conta_azul_e_conferencia_sem_importar_rodape():
    temp, original = _usar_banco_temporario()
    try:
        caminho = Path(temp.name) / "estoque.csv"
        caminho.write_text(
            f"Nome do Produto;SKU;Unidade de Medida;Reservado;{DISPONIVEL};{CUSTO_MEDIO};Custo Total;Valor de Venda\n"
            "Produto A;A-1;un;2;10;1,20;12,00;2,00\n"
            "CUSTO TOTAL;;;;;;12,00;\n",
            encoding="utf-8",
        )
        previa = database.previsualizar_importacao(str(caminho))

        assert previa["colunas_mapeadas"]["estoque"] == DISPONIVEL
        assert previa["colunas_mapeadas"]["custo_unitario"] == CUSTO_MEDIO
        assert previa["colunas_mapeadas"]["preco"] == "Valor de Venda"
        assert previa["colunas_mapeadas"]["custo_total"] == "Custo Total"
        assert previa["total_linhas"] == 1
        assert previa["custo_total_planilha"] == 12
        assert previa["valor_custo_calculado"] == 12
        assert previa["valor_venda_calculado"] == 20
        assert previa["produtos_com_divergencia_banco"] == 0
        assert previa["valor_divergencia_banco"] == 0
        assert previa["produtos_ativos_fora_da_planilha"] == 0
        assert previa["valor_produtos_fora_da_planilha"] == 0

        resultado = database.importar_csv(str(caminho))
        with database.get_conn() as conn:
            produtos = conn.execute("SELECT * FROM produtos").fetchall()
        assert resultado["inseridos"] == 1
        assert len(produtos) == 1
        assert produtos[0]["custo_unitario"] == 1.2
        assert produtos[0]["preco"] == 2
        assert produtos[0]["estoque"] == 10
    finally:
        database.DB_PATH = original
        temp.cleanup()


def test_custo_total_nunca_vira_custo_unitario():
    mapa = database._mapear_colunas(["SKU", "Nome do Produto", "Custo Total", "Valor de Venda"])
    assert "custo_unitario" not in mapa
    assert mapa["custo_total"] == "Custo Total"


def test_previa_aponta_divergencias_e_produtos_fora_da_planilha():
    temp, original = _usar_banco_temporario()
    try:
        with database.get_conn() as conn:
            conn.execute(
                "INSERT INTO produtos (codigo, nome, preco, estoque, custo_unitario) VALUES ('A', 'Produto A', 2, 8, 1)"
            )
            conn.execute(
                "INSERT INTO produtos (codigo, nome, preco, estoque, custo_unitario) VALUES ('EXTRA', 'Produto Extra', 5, 3, 4)"
            )
        caminho = Path(temp.name) / "divergencias.csv"
        caminho.write_text(
            f"SKU;Nome do Produto;{DISPONIVEL};{CUSTO_MEDIO};Valor de Venda\n"
            "A;Produto A;10;1,20;2,00\n",
            encoding="utf-8",
        )

        previa = database.previsualizar_importacao(str(caminho))

        assert previa["produtos_com_divergencia_banco"] == 1
        assert previa["valor_divergencia_banco"] == -4
        assert previa["produtos_ativos_fora_da_planilha"] == 1
        assert previa["valor_produtos_fora_da_planilha"] == 12
    finally:
        database.DB_PATH = original
        temp.cleanup()


def test_inventario_inicial_preserva_existente_e_inicia_novo():
    temp, original = _usar_banco_temporario()
    try:
        with database.get_conn() as conn:
            conn.execute(
                "INSERT INTO produtos (codigo, nome, preco, estoque) VALUES ('ANTIGO', 'Antigo', 1, 7)"
            )
        caminho = Path(temp.name) / "inventario.csv"
        caminho.write_text(
            f"SKU;Nome do Produto;{DISPONIVEL};Valor de Venda\n"
            "ANTIGO;Antigo;20;1\n"
            "NOVO;Novo;5;2\n",
            encoding="utf-8",
        )
        database.importar_csv(str(caminho), database.MODO_ESTOQUE_INVENTARIO)
        with database.get_conn() as conn:
            saldos = {
                row["codigo"]: row["estoque"]
                for row in conn.execute("SELECT codigo, estoque FROM produtos")
            }
        assert saldos == {"ANTIGO": 7, "NOVO": 5}
    finally:
        database.DB_PATH = original
        temp.cleanup()


def test_valores_a_custo_e_venda_sem_fallback():
    produto = {"estoque": 10, "custo_unitario": 1.2, "preco": 2}
    assert calculos.valor_a_custo(produto) == 12
    assert calculos.valor_a_venda(produto) == 20
    assert calculos.valor_a_custo({"estoque": 10, "custo_unitario": 0, "preco": 2}) == 0


def test_venda_reduz_saldo_e_os_dois_valores_corretamente():
    temp, original = _usar_banco_temporario()
    try:
        with database.get_conn() as conn:
            produto_id = conn.execute(
                "INSERT INTO produtos (codigo, nome, preco, estoque, custo_unitario) VALUES ('A', 'Produto', 2, 10, 1.2)"
            ).lastrowid
            periodo_id = conn.execute(
                "INSERT INTO periodos_caixa (data, sequencia, aberto_em) VALUES ('01/01/2026', 1, '2026-01-01T08:00:00')"
            ).lastrowid
        database.registrar_venda(
            periodo_id,
            1,
            [{"produto_id": produto_id, "codigo": "A", "nome": "Produto", "quantidade": 1, "preco_unit": 2}],
            "Dinheiro",
        )
        produto = dict(database.obter_produto(produto_id))
        assert produto["estoque"] == 9
        assert calculos.valor_a_custo(produto) == 10.8
        assert calculos.valor_a_venda(produto) == 18
    finally:
        database.DB_PATH = original
        temp.cleanup()


def test_entrada_perda_inventario_e_status():
    temp, original = _usar_banco_temporario()
    try:
        with database.get_conn() as conn:
            produto_id = conn.execute(
                "INSERT INTO produtos (codigo, nome, preco, estoque, estoque_minimo) VALUES ('B', 'Produto B', 5, 2, 1)"
            ).lastrowid
        database.registrar_entrada_estoque(produto_id, 3)
        database.registrar_perda_estoque(produto_id, 1)
        database.ajustar_estoque_por_contagem(produto_id, 1)
        produto = dict(database.obter_produto(produto_id))
        assert produto["estoque"] == 1
        assert calculos.status_estoque(produto, 0, "") == "CRITICO"
        tipos = [row["tipo"] for row in database.obter_movimentacoes_produto(produto_id)]
        assert {"ENTRADA", "PERDA", "INVENTARIO"}.issubset(tipos)
    finally:
        database.DB_PATH = original
        temp.cleanup()
