"""Testes da aba de Configurações, Tema e Backup/Restauração (Issue #12)."""

import unittest
import tkinter as tk
import tempfile
from pathlib import Path

import database
import tema
from app.ui import components
from app.ui.app_window import CaixaApp


class ConfiguracoesUITest(unittest.TestCase):

    def setUp(self):
        self._original_db_path = database.DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._temp_dir.name) / "loja_test.db"
        database.inicializar()

    def tearDown(self):
        database.DB_PATH = self._original_db_path
        self._temp_dir.cleanup()

    def test_instanciacao_aba_configuracoes(self):
        """Testa se a aba de configuracoes e criada sem erros no Tkinter."""
        try:
            root = CaixaApp()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            self.assertIsNotNone(root._aba_configuracoes)
            # Garante que tema padrao e claro
            self.assertEqual(tema.obter_nome_tema_atual(), "claro")
            self.assertEqual(root._var_tema_opcao.get(), "claro")
        finally:
            root.destroy()

    def test_alternancia_manual_de_tema(self):
        """Testa se a troca manual de tema atualiza os tokens e a UI."""
        try:
            root = CaixaApp()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            # Alterna para escuro
            root._alternar_tema("escuro")
            self.assertEqual(tema.obter_nome_tema_atual(), "escuro")
            self.assertEqual(tema.obter_tema_atual()["bg"], "#121416")
            self.assertEqual(root._var_tema_opcao.get(), "escuro")

            # Alterna de volta para claro
            root._alternar_tema("claro")
            self.assertEqual(tema.obter_nome_tema_atual(), "claro")
            self.assertEqual(tema.obter_tema_atual()["bg"], "#F6F3EC")
            self.assertEqual(root._var_tema_opcao.get(), "claro")
        finally:
            root.destroy()

    def test_ausencia_de_backup_no_rodape_da_venda(self):
        """Valida que os botoes de backup foram removidos do rodape da tela de venda."""
        try:
            root = CaixaApp()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            # Encontra todos os botoes no rodape da venda
            textos_botoes = []
            for widget in root.winfo_children():
                if isinstance(widget, tk.Frame):
                    for sub in widget.winfo_children():
                        if isinstance(sub, tk.Button):
                            textos_botoes.append(sub.cget("text"))

            self.assertNotIn("Criar backup", textos_botoes)
            self.assertNotIn("Restaurar backup", textos_botoes)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
