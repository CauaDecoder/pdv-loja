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
            self.assertEqual(tema.obter_tema_atual()["bg"], "#F3F5F4")
            self.assertEqual(root._var_tema_opcao.get(), "claro")
        finally:
            root.destroy()

    def test_tema_escuro_e_propagado_a_todas_as_telas_principais(self):
        """A troca de tema deve alcançar o conteúdo já montado de cada aba."""
        try:
            root = CaixaApp()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            with database.get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO produtos (codigo, nome, preco, estoque)
                    VALUES ('TEMA', 'Produto Tema', 10, 5)
                    """
                )
            fundos_claros = {
                tema.TEMA_CLARO["bg"],
                tema.TEMA_CLARO["surface"],
                tema.TEMA_CLARO["surface_2"],
                tema.TEMA_CLARO["surface_3"],
            }

            root._alternar_tema("escuro")

            produto = dict(database.buscar_produto("TEMA")[0])
            root._adicionar_produto(produto)
            root._renderizar_carrinho()

            for aba in (
                root._aba_venda,
                root._aba_vendas_correcoes,
                root._aba_estoque,
                root._aba_importacao,
                root._aba_relatorios,
                root._aba_configuracoes,
            ):
                widgets = [aba]
                while widgets:
                    widget = widgets.pop()
                    widgets.extend(widget.winfo_children())
                    try:
                        fundo = widget.cget("background")
                    except tk.TclError:
                        continue
                    self.assertNotIn(
                        fundo,
                        fundos_claros,
                        f"{widget} permaneceu com fundo do tema claro",
                    )
        finally:
            root.destroy()

    def test_botoes_de_selecao_permanecem_legiveis_no_tema_escuro(self):
        """Radio e check buttons não podem conservar seleção branca no tema escuro."""
        try:
            root = CaixaApp()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            root._alternar_tema("escuro")
            pendentes = [root]
            seletores = []
            while pendentes:
                widget = pendentes.pop()
                pendentes.extend(widget.winfo_children())
                if isinstance(widget, (tk.Radiobutton, tk.Checkbutton)):
                    seletores.append(widget)

            self.assertTrue(seletores)
            for seletor in seletores:
                self.assertNotEqual(seletor.cget("selectcolor").lower(), "#ffffff")
                self.assertEqual(seletor.cget("foreground"), tema.TEMA_ESCURO["text"])
        finally:
            root.destroy()
            tema.definir_tema_atual("claro")

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
