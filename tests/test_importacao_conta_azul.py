import tempfile
import unittest
from pathlib import Path

from app import database


class ImportacaoContaAzulTest(unittest.TestCase):
    def setUp(self):
        self._db_path_original = database.DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._temp_dir.name) / "loja_teste.db"
        database.inicializar()

    def tearDown(self):
        database.DB_PATH = self._db_path_original
        self._temp_dir.cleanup()

    def _escrever_csv(self, nome: str, conteudo: str) -> Path:
        caminho = Path(self._temp_dir.name) / nome
        caminho.write_text(conteudo, encoding="utf-8")
        return caminho

    def test_previsualiza_products2_com_disponivel(self):
        caminho = self._escrever_csv(
            "products2.csv",
            "SKU;Nome do Produto;Disponível;Valor de Venda;Custo Médio\nSKU-10;Produto Teste;10;15,00;8,00\n",
        )
        previa = database.previsualizar_importacao(str(caminho))

        self.assertTrue(previa["estoque_mapeado"])
        self.assertEqual(database._normalizar_chave(previa["coluna_estoque"]), "disponivel")
        self.assertGreater(previa["total_com_estoque_maior_zero"], 0)

    def test_previa_alerta_valores_que_serao_arredondados_em_centavos(self):
        caminho = self._escrever_csv(
            "arredondamento.csv",
            (
                "SKU;Nome do Produto;Disponível;Valor de Venda;Custo Médio\n"
                "SKU-1;Produto;2;10,005;3,004\n"
            ),
        )

        previa = database.previsualizar_importacao(str(caminho))

        self.assertEqual(previa["valores_monetarios_arredondados"], 2)
        self.assertTrue(previa["alerta_arredondamento"])

    def test_preserva_estoque_quando_csv_nao_tem_coluna_de_saldo(self):
        with database.get_conn() as conn:
            conn.execute(
                "INSERT INTO produtos (codigo, nome, preco_centavos, estoque) VALUES (?, ?, ?, ?)",
                ("SKU-1", "Produto teste", 1000, 7),
            )

        caminho = self._escrever_csv(
            "sem_estoque.csv",
            "SKU;Nome do Produto;Valor de Venda\nSKU-1;Produto teste atualizado;12,50\n",
        )

        previa = database.previsualizar_importacao(str(caminho))
        resultado = database.importar_csv(
            str(caminho),
            responsavel="Ana",
            lote_id="lote-sem-estoque",
            hash_arquivo=previa["sha256"],
        )

        with database.get_conn() as conn:
            produto = conn.execute(
                "SELECT nome, preco, estoque FROM produtos WHERE codigo = ?",
                ("SKU-1",),
            ).fetchone()
            movimentos = conn.execute(
                "SELECT COUNT(*) FROM movimentacoes_estoque WHERE origem = 'IMPORTACAO'"
            ).fetchone()[0]

        self.assertEqual(resultado["atualizados"], 1)
        self.assertEqual(resultado["ajustados"], 0)
        self.assertEqual(produto["estoque"], 7)
        self.assertEqual(produto["nome"], "Produto teste atualizado")
        self.assertEqual(movimentos, 0)

    def test_atualiza_por_disponivel_e_registra_ajuste(self):
        with database.get_conn() as conn:
            conn.execute(
                "INSERT INTO produtos (codigo, nome, preco_centavos, estoque) VALUES (?, ?, ?, ?)",
                ("SKU-2", "Produto saldo", 800, 2),
            )

        caminho = self._escrever_csv(
            "com_disponivel.csv",
            (
                "Nome do Produto;SKU;Disponível;Valor de Venda\n"
                "Produto saldo atualizado;SKU-2;5;9,90\n"
            ),
        )

        previa = database.previsualizar_importacao(str(caminho))
        resultado = database.importar_csv(
            str(caminho),
            responsavel="Ana",
            lote_id="lote-disponivel",
            hash_arquivo=previa["sha256"],
        )

        with database.get_conn() as conn:
            produto = conn.execute(
                "SELECT preco, estoque FROM produtos WHERE codigo = ?",
                ("SKU-2",),
            ).fetchone()
            movimento = conn.execute(
                """
                SELECT tipo, quantidade, estoque_resultante
                FROM movimentacoes_estoque
                WHERE origem = 'IMPORTACAO'
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        self.assertEqual(resultado["ajustados"], 1)
        self.assertEqual(produto["estoque"], 5)
        self.assertAlmostEqual(produto["preco"], 9.9, places=2)
        self.assertEqual(movimento["tipo"], "AJUSTE")
        self.assertEqual(movimento["quantidade"], 3)
        self.assertEqual(movimento["estoque_resultante"], 5)

    def test_importacao_exige_operador_responsavel(self):
        caminho = self._escrever_csv(
            "operador.csv",
            "SKU;Nome do Produto;Disponível;Valor de Venda\nSKU-OP;Produto;1;5,00\n",
        )

        with self.assertRaisesRegex(ValueError, "Operador"):
            database.importar_csv(
                str(caminho),
                responsavel="",
            )

        with database.get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0]
        self.assertEqual(total, 0)

    def test_importacao_rejeita_arquivo_alterado_depois_da_previa(self):
        caminho = self._escrever_csv(
            "hash.csv",
            "SKU;Nome do Produto;Disponível;Valor de Venda\nSKU-H;Produto;1;5,00\n",
        )
        previa = database.previsualizar_importacao(str(caminho))
        self.assertEqual(len(previa["sha256"]), 64)

        caminho.write_text(
            "SKU;Nome do Produto;Disponível;Valor de Venda\nSKU-H;Produto alterado;9;8,00\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "mudou|alterado|hash"):
            database.importar_csv(
                str(caminho),
                responsavel="Ana",
                lote_id="lote-hash",
                hash_arquivo=previa["sha256"],
            )

        self.assertEqual(database.listar_produtos(), [])

    def test_importacao_bloqueia_sku_duplicado_sem_gravar(self):
        caminho = self._escrever_csv(
            "sku-duplicado.csv",
            "SKU;Nome do Produto;Disponível;Valor de Venda\nDUP;Primeiro;1;5,00\nDUP;Segundo;2;6,00\n",
        )
        previa = database.previsualizar_importacao(str(caminho))
        self.assertEqual(previa["produtos_duplicados"], 1)

        with self.assertRaisesRegex(ValueError, "duplicado"):
            database.importar_csv(
                str(caminho),
                responsavel="Ana",
                lote_id="lote-sku",
                hash_arquivo=previa["sha256"],
            )

        self.assertEqual(database.listar_produtos(), [])

    def test_importacao_bloqueia_codigo_barras_duplicado_sem_gravar(self):
        caminho = self._escrever_csv(
            "barras-duplicado.csv",
            "SKU;Código de Barras;Nome do Produto;Disponível;Valor de Venda\nA;789;Primeiro;1;5,00\nB;789;Segundo;2;6,00\n",
        )
        previa = database.previsualizar_importacao(str(caminho))
        self.assertEqual(previa["codigos_barras_duplicados"], 1)

        with self.assertRaisesRegex(ValueError, "duplicado"):
            database.importar_csv(
                str(caminho),
                responsavel="Ana",
                lote_id="lote-barras",
                hash_arquivo=previa["sha256"],
            )

        self.assertEqual(database.listar_produtos(), [])

    def test_importacao_bloqueia_codigo_barras_ja_cadastrado(self):
        database.criar_produto(
            {
                "codigo": "A",
                "cod_barras": "789",
                "nome": "Existente",
                "preco": 5,
                "responsavel": "Ana",
            }
        )
        caminho = self._escrever_csv(
            "barras-existente.csv",
            "SKU;Código de Barras;Nome do Produto;Disponível;Valor de Venda\nB;789;Novo;2;6,00\n",
        )
        previa = database.previsualizar_importacao(str(caminho))

        with self.assertRaisesRegex(ValueError, "duplicado"):
            database.importar_csv(
                str(caminho),
                responsavel="Ana",
                lote_id="lote-barras-existente",
                hash_arquivo=previa["sha256"],
            )

        self.assertEqual([row["codigo"] for row in database.listar_produtos()], ["A"])

    def test_importacao_preserva_ausentes_e_registra_lote_reconciliado(self):
        database.criar_produto(
            {
                "codigo": "FORA",
                "nome": "Fora da planilha",
                "preco": 10,
                "estoque_inicial": 4,
                "responsavel": "Ana",
            }
        )
        caminho = self._escrever_csv(
            "incremental.csv",
            "SKU;Nome do Produto;Disponível;Valor de Venda\nNOVO;Novo;3;5,00\n",
        )
        previa = database.previsualizar_importacao(str(caminho))
        self.assertEqual(previa["produtos_ativos_fora_da_planilha"], 1)

        resultado = database.importar_csv(
            str(caminho),
            responsavel="Ana",
            lote_id="lote-incremental",
            hash_arquivo=previa["sha256"],
        )
        fora = dict(database.buscar_produto("FORA")[0])
        novo = dict(database.buscar_produto("NOVO")[0])
        movimentos_novo = database.obter_movimentacoes_produto(novo["id"])
        reconciliacao = database.reconciliar_integridade_banco()

        self.assertEqual(resultado["lote_id"], "lote-incremental")
        self.assertEqual(resultado["sha256"], previa["sha256"])
        self.assertEqual(fora["estoque"], 4)
        self.assertEqual(movimentos_novo[0]["responsavel"], "Ana")
        self.assertTrue(reconciliacao["ok"])
        self.assertEqual(reconciliacao["estoque_divergente"], 0)

    def test_importacao_mantem_custo_ausente_como_null(self):
        caminho = self._escrever_csv(
            "sem-custo.csv",
            "SKU;Nome do Produto;Disponível;Valor de Venda\nSEM-CUSTO;Produto;2;5,00\n",
        )
        previa = database.previsualizar_importacao(str(caminho))
        database.importar_csv(
            str(caminho),
            responsavel="Ana",
            lote_id="lote-sem-custo",
            hash_arquivo=previa["sha256"],
        )

        produto = dict(database.buscar_produto("SEM-CUSTO")[0])
        self.assertIsNone(produto["custo_unitario"])
        self.assertIsNone(produto["custo_unitario_centavos"])


if __name__ == "__main__":
    unittest.main()
