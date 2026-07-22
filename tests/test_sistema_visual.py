"""Testes para o sistema visual compartilhado em Tkinter (Issue #5)."""

import unittest
import tkinter as tk
import tempfile
from pathlib import Path
from tkinter import ttk

import database
import tema
from app.ui import components


class SistemaVisualTest(unittest.TestCase):

    def test_tokens_tema_claro_e_escuro(self):
        claro = tema.TEMA_CLARO
        escuro = tema.TEMA_ESCURO

        # Verificação das chaves essenciais na Variante A
        chaves_obrigatorias = [
            "bg", "surface", "surface_2", "surface_3", "text", "text_muted",
            "border", "border_soft", "primary", "primary_soft", "gold", "gold_soft",
            "danger", "danger_soft", "warning", "warning_soft", "info", "info_soft",
            "focus_ring"
        ]

        for chave in chaves_obrigatorias:
            self.assertIn(chave, claro, f"Chave {chave} ausente em TEMA_CLARO")
            self.assertIn(chave, escuro, f"Chave {chave} ausente em TEMA_ESCURO")

    def test_definir_e_obter_tema_atual(self):
        tema.definir_tema_atual("escuro")
        self.assertEqual(tema.obter_nome_tema_atual(), "escuro")
        self.assertEqual(tema.obter_tema_atual()["bg"], "#121416")

        tema.definir_tema_atual("claro")
        self.assertEqual(tema.obter_nome_tema_atual(), "claro")
        self.assertEqual(tema.obter_tema_atual()["bg"], "#F3F5F4")

    def test_tema_claro_usa_base_neutra_e_tabela_sem_grade(self):
        """O tema claro evita o bege dominante e as tabelas usam bordas discretas."""
        self.assertEqual(tema.TEMA_CLARO["bg"], "#F3F5F4")
        self.assertEqual(tema.TEMA_CLARO["surface"], "#FFFFFF")

        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            style = components.configure_styles(root, "claro")
            self.assertEqual(str(style.lookup("Treeview", "borderwidth")), "0")
            self.assertEqual(style.lookup("Treeview", "bordercolor"), tema.TEMA_CLARO["surface"])
            self.assertEqual(str(style.lookup("Treeview.Heading", "borderwidth")), "0")
        finally:
            root.destroy()

    def test_controles_de_selecao_readonly_sao_legiveis_no_tema_escuro(self):
        """Comboboxes readonly devem aplicar fundo e texto próprios do tema escuro."""
        tema.definir_tema_atual("escuro")
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            tema.definir_tema_atual("claro")
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            style = components.configure_styles(root, "escuro")
            self.assertEqual(
                style.lookup("TCombobox", "fieldbackground", ("readonly",)),
                tema.TEMA_ESCURO["surface_3"],
            )
            self.assertEqual(
                style.lookup("TCombobox", "foreground", ("readonly",)),
                tema.TEMA_ESCURO["text"],
            )
        finally:
            root.destroy()
            tema.definir_tema_atual("claro")

    def test_instanciacao_componentes_visuais(self):
        """Testa se os componentes visuais sao criados sem erro em um Tcl virtual."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            components.configure_styles(root)

            btn = components.action_button(root, text="Test Button", variant="primary")
            self.assertIsInstance(btn, tk.Button)

            entry = components.StyledEntry(root)
            self.assertIsInstance(entry, tk.Entry)

            card = components.Card(root)
            self.assertIsInstance(card, components.Card)

            badge = components.StatusBadge(root, "OK")
            self.assertIsInstance(badge, components.StatusBadge)

            search = components.SearchInput(root, textvariable=tk.StringVar(), placeholder="Buscar...")
            self.assertIsInstance(search, components.SearchInput)

            header = components.PageHeader(root, title="Titulo Teste", subtitle="Subtitulo Teste")
            self.assertIsInstance(header, components.PageHeader)

            empty = components.EmptyState(root, title="Vazio", subtitle="Sem dados")
            self.assertIsInstance(empty, components.EmptyState)

            tree = components.DataTable(root, columns=("col1", "col2"), headings={"col1": "C1", "col2": "C2"})
            self.assertIsInstance(tree, ttk.Treeview)
        finally:
            root.destroy()

    def test_painel_estoque_instanciacao(self):
        """Testa se o PainelEstoque instacia e atualiza sem erros no Tkinter."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        db_path_original = database.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "loja_teste.db"
            try:
                database.inicializar()
                components.configure_styles(root)
                from estoque.painel import PainelEstoque

                painel = PainelEstoque(root)
                self.assertIsInstance(painel, PainelEstoque)
                painel.atualizar()
                painel._limpar_filtros()
            finally:
                database.DB_PATH = db_path_original
                root.destroy()


if __name__ == "__main__":
    unittest.main()
