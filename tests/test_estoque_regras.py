import tempfile
from datetime import datetime
from pathlib import Path

from app import database
from app.estoque import calculos
from app.services import estoque_service, vendas_service


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

        resultado = database.importar_csv(
            str(caminho),
            responsavel="Ana",
            lote_id="lote-conta-azul",
            hash_arquivo=previa["sha256"],
        )
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
                "INSERT INTO produtos (codigo, nome, preco_centavos, estoque, custo_unitario_centavos) VALUES ('A', 'Produto A', 200, 8, 100)"
            )
            conn.execute(
                "INSERT INTO produtos (codigo, nome, preco_centavos, estoque, custo_unitario_centavos) VALUES ('EXTRA', 'Produto Extra', 500, 3, 400)"
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


def test_inventario_inicial_exige_banco_vazio():
    temp, original = _usar_banco_temporario()
    try:
        with database.get_conn() as conn:
            conn.execute(
                "INSERT INTO produtos (codigo, nome, preco_centavos, estoque) VALUES ('ANTIGO', 'Antigo', 100, 7)"
            )
        caminho = Path(temp.name) / "inventario.csv"
        caminho.write_text(
            f"SKU;Nome do Produto;{DISPONIVEL};Valor de Venda\n"
            "ANTIGO;Antigo;20;1\n"
            "NOVO;Novo;5;2\n",
            encoding="utf-8",
        )
        try:
            previa = database.previsualizar_importacao(str(caminho))
            database.importar_csv(
                str(caminho),
                database.MODO_ESTOQUE_INVENTARIO,
                responsavel="Ana",
                lote_id="lote-inventario-preenchido",
                hash_arquivo=previa["sha256"],
            )
            raise AssertionError("Inventario inicial com banco preenchido deveria falhar.")
        except ValueError as exc:
            assert "vazio" in str(exc).lower()
        with database.get_conn() as conn:
            saldos = {
                row["codigo"]: row["estoque"]
                for row in conn.execute("SELECT codigo, estoque FROM produtos")
            }
        assert saldos == {"ANTIGO": 7}
    finally:
        database.DB_PATH = original
        temp.cleanup()


def test_valores_a_custo_e_venda_sem_fallback():
    produto = {"estoque": 10, "custo_unitario": 1.2, "preco": 2}
    assert calculos.valor_a_custo(produto) == 12
    assert calculos.valor_a_venda(produto) == 20
    assert calculos.valor_a_custo({"estoque": 10, "custo_unitario": 0, "preco": 2}) == 0


def test_valores_de_estoque_preferem_centavos_e_tratam_custo_ausente():
    produto = {
        "estoque": 3,
        "custo_unitario": 1.005,
        "custo_unitario_centavos": 100,
        "preco": 2.345,
        "preco_centavos": 235,
    }

    assert calculos.valor_a_custo(produto) == 3.0
    assert calculos.valor_a_venda(produto) == 7.05
    assert calculos.valor_a_custo({"estoque": 3, "custo_unitario": None}) == 0


def test_filtros_estoque_combinam_busca_status_e_pendencias():
    produtos = [
        {
            "nome": "Vela branca",
            "codigo": "VELA-1",
            "cod_barras": "789",
            "status": "MORTO",
            "curva_abc": "C",
            "categoria": "Velas",
            "fornecedor": "Fornecedor A",
            "ativo": 1,
            "custo_unitario": None,
            "estoque_minimo": 0,
        },
        {
            "nome": "Terco",
            "codigo": "TERCO-1",
            "status": "OK",
            "ativo": 1,
            "custo_unitario": 5,
            "estoque_minimo": 2,
        },
    ]

    filtrados = calculos.filtrar_produtos(
        produtos,
        calculos.FiltrosEstoque(
            termo="789",
            sem_custo=True,
            sem_minimo=True,
            sem_movimento=True,
        ),
    )

    assert filtrados == [produtos[0]]


def test_filtro_sem_custo_nao_confunde_zero_com_ausencia():
    produtos = [
        {"nome": "Sem custo", "ativo": 1, "custo_unitario": None},
        {"nome": "Custo zero", "ativo": 1, "custo_unitario": 0},
    ]

    filtrados = calculos.filtrar_produtos(
        produtos,
        calculos.FiltrosEstoque(sem_custo=True),
    )

    assert filtrados == [produtos[0]]


def test_produto_inativo_fica_fora_dos_totais_operacionais():
    produtos = [
        {
            "nome": "Ativo",
            "ativo": 1,
            "estoque": 2,
            "custo_unitario": 3,
            "preco": 5,
            "status": "OK",
            "valor_estoque": 6,
            "valor_a_custo": 6,
            "valor_a_venda": 10,
        },
        {
            "nome": "Inativo",
            "ativo": 0,
            "estoque": 4,
            "custo_unitario": 20,
            "preco": 30,
            "status": "INATIVO",
            "valor_estoque": 80,
            "valor_a_custo": 80,
            "valor_a_venda": 120,
        },
    ]

    assert calculos.status_estoque(produtos[1], 0, "") == "INATIVO"
    assert calculos.resumo_estoque(produtos) == {
        "ativos": 1,
        "criticos": 0,
        "alertas": 0,
        "mortos": 0,
        "valor_total": 6,
        "valor_total_custo": 6,
        "valor_total_venda": 10,
    }


def test_venda_reduz_saldo_e_os_dois_valores_corretamente():
    temp, original = _usar_banco_temporario()
    try:
        with database.get_conn() as conn:
            produto_id = conn.execute(
                "INSERT INTO produtos (codigo, nome, preco_centavos, estoque, custo_unitario_centavos) VALUES ('A', 'Produto', 200, 10, 120)"
            ).lastrowid
            periodo_id = conn.execute(
                "INSERT INTO periodos_caixa (data, sequencia, aberto_em) VALUES ('2026-01-01', 1, '2026-01-01T08:00:00')"
            ).lastrowid
        database.registrar_venda(
            periodo_id,
            1,
            [{"produto_id": produto_id, "codigo": "A", "nome": "Produto", "quantidade": 1, "preco_unit": 2}],
                "Dinheiro",
                valor_recebido=2,
                troco=0,
                responsavel="Ana",
            chave_idempotencia="teste-estoque-venda-1",
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
                "INSERT INTO produtos (codigo, nome, preco_centavos, estoque, estoque_minimo) VALUES ('B', 'Produto B', 500, 2, 1)"
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


def test_demanda_e_mais_vendidos_usam_quantidade_corrigida_e_excluem_cancelada():
    temp, original = _usar_banco_temporario()
    try:
        hoje = datetime.now().strftime("%d/%m/%Y")
        produto_id = database.criar_produto(
            {
                "codigo": "A",
                "nome": "Produto",
                "preco": 10,
                "estoque_inicial": 20,
                "responsavel": "Ana",
            }
        )
        periodo = database.obter_ou_criar_periodo_aberto(hoje)
        item = {
            "produto_id": produto_id,
            "codigo": "A",
            "nome": "Produto",
            "preco_unit": 10,
        }
        database.registrar_venda(
            periodo["id"],
            1,
            [{**item, "quantidade": 5}],
            "Pix",
            responsavel="Ana",
            chave_idempotencia="demanda-1",
        )
        detalhe = vendas_service.obter_detalhe_venda(periodo["id"], 1)
        vendas_service.alterar_quantidade_item_venda(
            periodo["id"],
            1,
            detalhe["items"][0]["line_id"],
            2,
            responsavel="Ana",
        )
        database.registrar_venda(
            periodo["id"],
            2,
            [{**item, "quantidade": 3}],
            "Pix",
            responsavel="Ana",
            chave_idempotencia="demanda-2",
        )
        vendas_service.cancelar_venda(periodo["id"], 2, responsavel="Ana")

        with database.get_conn() as conn:
            demanda = calculos.demanda_media_diaria(conn, produto_id, 30)
        vendidos = database.dashboard_top_vendidos(30, 10)

        assert demanda == 2 / 30
        assert vendidos == [
            {"codigo": "A", "nome": "Produto", "quantidade": 2}
        ]
    finally:
        database.DB_PATH = original
        temp.cleanup()


def test_curva_abc_por_receita_usa_vendas_efetivas():
    temp, original = _usar_banco_temporario()
    try:
        hoje = datetime.now().strftime("%d/%m/%Y")
        produto_a = database.criar_produto(
            {
                "codigo": "A",
                "nome": "Ativo",
                "preco": 10,
                "custo_unitario": 1,
                "estoque_inicial": 20,
                "responsavel": "Ana",
            }
        )
        produto_b = database.criar_produto(
            {
                "codigo": "B",
                "nome": "Cancelado",
                "preco": 10,
                "custo_unitario": 100,
                "estoque_inicial": 20,
                "responsavel": "Ana",
            }
        )
        periodo = database.obter_ou_criar_periodo_aberto(hoje)
        for numero, produto_id, codigo in (
            (1, produto_a, "A"),
            (2, produto_b, "B"),
        ):
            database.registrar_venda(
                periodo["id"],
                numero,
                [{
                    "produto_id": produto_id,
                    "codigo": codigo,
                    "nome": codigo,
                    "quantidade": 2,
                    "preco_unit": 10,
                }],
                "Pix",
                responsavel="Ana",
                chave_idempotencia=f"abc-{numero}",
            )
        vendas_service.cancelar_venda(periodo["id"], 2, responsavel="Ana")
        database.atualizar_configuracoes({"abc_metodo": "receita_vendas"})

        database.recalcular_curva_abc()
        curvas = {
            row["codigo"]: row["curva_abc"] for row in database.listar_produtos()
        }

        assert curvas == {"A": "A", "B": "C"}
    finally:
        database.DB_PATH = original
        temp.cleanup()


def test_movimentacao_manual_exige_operador_e_audita_saldo_negativo():
    temp, original = _usar_banco_temporario()
    try:
        produto_id = database.criar_produto(
            {
                "codigo": "NEG",
                "nome": "Saldo negativo",
                "preco": 5,
                "estoque_inicial": 1,
                "responsavel": "Ana",
            }
        )

        try:
            estoque_service.registrar_perda_estoque(
                produto_id,
                2,
                responsavel="",
            )
            raise AssertionError("Movimentacao sem Operador deveria ser rejeitada.")
        except ValueError as exc:
            assert "Operador" in str(exc)

        saldo = estoque_service.registrar_perda_estoque(
            produto_id,
            2,
            responsavel="Ana",
            observacao="Avaria confirmada",
        )
        movimentos = database.obter_movimentacoes_produto(produto_id)

        assert saldo == -1
        assert movimentos[0]["responsavel"] == "Ana"
        assert movimentos[0]["observacao"] == "Avaria confirmada"
    finally:
        database.DB_PATH = original
        temp.cleanup()
