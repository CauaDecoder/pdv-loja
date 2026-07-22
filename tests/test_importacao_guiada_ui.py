"""Testes para a interface da Importação Guiada em 4 etapas (Issue #14)."""

import unittest
import tkinter as tk
import tempfile
from pathlib import Path

import database
from app.ui.importacao_view import ImportacaoGuidedView


class ImportacaoGuidedUITest(unittest.TestCase):

    def setUp(self):
        self._db_path_original = database.DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._temp_dir.name) / "loja_teste.db"
        database.inicializar()

    def tearDown(self):
        database.DB_PATH = self._db_path_original
        self._temp_dir.cleanup()

    def _escrever_csv_teste(self, nome: str = "produtos_teste.csv") -> Path:
        caminho = Path(self._temp_dir.name) / nome
        conteudo = "SKU;Nome do Produto;Disponível;Valor de Venda;Custo Médio\nSKU-100;Produto Teste Guiado;15;25,00;10,00\n"
        caminho.write_text(conteudo, encoding="utf-8")
        return caminho

    def test_instanciacao_e_etapa_inicial(self):
        """Testa se o componente inicia na etapa 1 (Arquivo)."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            view = ImportacaoGuidedView(root)
            self.assertEqual(view._etapa_atual, 1)
            self.assertIsNone(view._caminho_arquivo)
            self.assertIsNone(view._previa_dados)
        finally:
            root.destroy()

    def test_navegacao_entre_etapas_guiadas(self):
        """Testa o avanco de etapa 1 ate a conferencia (etapa 3)."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            csv_path = self._escrever_csv_teste()
            view = ImportacaoGuidedView(root)

            # Define arquivo e avança para Etapa 2
            view._caminho_arquivo = str(csv_path)
            view._avancar_para_etapa_2()
            self.assertEqual(view._etapa_atual, 2)

            # Seleciona modo e avança para Etapa 3 (Conferência)
            view._selecionar_modo("Atualizar estoque pelo Disponivel")
            view._avancar_para_etapa_3()
            self.assertEqual(view._etapa_atual, 3)
            self.assertIsNotNone(view._previa_dados)
            self.assertEqual(view._previa_dados["total_linhas"], 1)
            self.assertEqual(view._previa_dados["produtos_inseridos_previstos"], 1)

            # Avança para Etapa 4 (Confirmação)
            view._ir_para_etapa(4)
            self.assertEqual(view._etapa_atual, 4)

            # Executa importação
            view._executar_importacao()
            self.assertIsNotNone(view._resultado_importacao)
            self.assertEqual(view._resultado_importacao["inseridos"], 1)

            # Reseta o fluxo
            view._resetar_fluxo()
            self.assertEqual(view._etapa_atual, 1)
            self.assertIsNone(view._caminho_arquivo)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
