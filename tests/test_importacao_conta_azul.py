import tempfile
import unittest
from pathlib import Path

import database


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
        previa = database.previsualizar_importacao("products2.csv")

        self.assertTrue(previa["estoque_mapeado"])
        self.assertEqual(database._normalizar_chave(previa["coluna_estoque"]), "disponivel")
        self.assertGreater(previa["total_com_estoque_maior_zero"], 0)

    def test_preserva_estoque_quando_csv_nao_tem_coluna_de_saldo(self):
        with database.get_conn() as conn:
            conn.execute(
                "INSERT INTO produtos (codigo, nome, preco, estoque) VALUES (?, ?, ?, ?)",
                ("SKU-1", "Produto teste", 10.0, 7),
            )

        caminho = self._escrever_csv(
            "sem_estoque.csv",
            "SKU;Nome do Produto;Valor de Venda\nSKU-1;Produto teste atualizado;12,50\n",
        )

        resultado = database.importar_csv(str(caminho))

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
                "INSERT INTO produtos (codigo, nome, preco, estoque) VALUES (?, ?, ?, ?)",
                ("SKU-2", "Produto saldo", 8.0, 2),
            )

        caminho = self._escrever_csv(
            "com_disponivel.csv",
            (
                "Nome do Produto;SKU;Disponível;Valor de Venda\n"
                "Produto saldo atualizado;SKU-2;5;9,90\n"
            ),
        )

        resultado = database.importar_csv(str(caminho))

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


if __name__ == "__main__":
    unittest.main()
