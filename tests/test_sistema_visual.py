"""Testes para o sistema visual compartilhado em Tkinter (Issue #5)."""

import unittest
import tkinter as tk
import tempfile
from pathlib import Path
from tkinter import ttk

from app import database
from app.ui import theme as tema
from app.ui import components


class SistemaVisualTest(unittest.TestCase):

    def test_tokens_tema_claro_e_escuro(self):
        claro = tema.TEMA_CLARO
        escuro = tema.TEMA_ESCURO

        # Verificação das chaves essenciais na Variante A
        chaves_obrigatorias = [
            "bg", "surface", "surface_2", "surface_3", "text", "text_muted",
            "shell", "shell_text", "shell_muted",
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
                tema.TEMA_ESCURO["surface"],
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

            variable = tk.BooleanVar(value=False)
            toggle = components.ToggleSwitch(root, variable=variable, text="Filtro")
            toggle.pack()
            self.assertFalse(toggle.get())
            toggle.set(True)
            self.assertTrue(variable.get())
        finally:
            root.destroy()

    def test_modal_so_aparece_depois_da_montagem(self):
        """Modal deve nascer oculto para não piscar vazio antes do conteúdo."""
        try:
            root = tk.Tk()
            root.geometry("800x600")
            root.update()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            modal = components.BaseModal(root, "Pagamento", width=500, height=400)
            self.assertEqual(modal.state(), "withdrawn")
            tk.Label(modal.body_frame, text="Conteúdo pronto").pack()
            root.update()
            self.assertEqual(modal.state(), "normal")
            modal.close()
        finally:
            root.destroy()

    def test_roda_do_mouse_funciona_sobre_filhos_de_area_rolavel(self):
        """Roda sobre card ou texto deve rolar o Canvas ancestral."""
        try:
            root = tk.Tk()
            root.geometry("400x300")
            root.update()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            canvas = tk.Canvas(root, height=100)
            canvas.pack(fill="both", expand=True)
            frame = tk.Frame(canvas)
            canvas.create_window((0, 0), window=frame, anchor="nw")
            labels = [tk.Label(frame, text=f"Linha {i}") for i in range(40)]
            for label in labels:
                label.pack()
            root.update()
            canvas.configure(scrollregion=canvas.bbox("all"))
            components.bind_mousewheel_tree(frame, canvas)
            antes = canvas.yview()[0]
            labels[10].event_generate("<MouseWheel>", delta=-120)
            root.update()
            self.assertGreater(canvas.yview()[0], antes)
        finally:
            root.destroy()

    def test_toggle_switch_respeita_interacao_e_estado_disabled(self):
        """Alternador dispara callback por interação e bloqueia mudanças desabilitado."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        chamadas = []
        try:
            variable = tk.BooleanVar(value=False)
            toggle = components.ToggleSwitch(
                root,
                variable=variable,
                text="Sem custo",
                command=lambda: chamadas.append(variable.get()),
            )
            toggle.pack()
            root.deiconify()
            root.update()
            toggle.event_generate("<Button-1>", x=5, y=5)
            root.update()
            self.assertTrue(toggle.get())
            self.assertEqual(chamadas, [True])

            toggle.configure(state="disabled")
            toggle.event_generate("<Button-1>")
            root.update()
            self.assertTrue(toggle.get())
            self.assertEqual(chamadas, [True])

            toggle.configure(state="normal")
            toggle.focus_force()
            root.update()
            self.assertEqual(
                toggle.itemcget(toggle._focus_item, "outline"),
                tema.TEMA_CLARO["focus_ring"],
            )

            toggle.event_generate("<space>")
            root.update()
            self.assertFalse(toggle.get())
            toggle.event_generate("<Return>")
            root.update()
            self.assertTrue(toggle.get())
            self.assertEqual(chamadas, [True, False, True])

            variable.set(False)
            root.update()
            self.assertFalse(toggle.get())
            self.assertEqual(chamadas, [True, False, True])

            tema.definir_tema_atual("escuro")
            components.apply_theme_to_widget_tree(toggle, tema.TEMA_CLARO)
            self.assertEqual(
                toggle.itemcget(toggle._label_item, "fill"),
                tema.TEMA_ESCURO["text"],
            )
        finally:
            root.destroy()
            tema.definir_tema_atual("claro")

    def test_campos_ttk_sao_legiveis_no_tema_escuro(self):
        """Campos de data e texto ttk não podem manter o fundo branco no tema escuro."""
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
                style.lookup("TEntry", "fieldbackground"),
                tema.TEMA_ESCURO["surface_2"],
            )
            self.assertEqual(
                style.lookup("TEntry", "foreground"),
                tema.TEMA_ESCURO["text"],
            )
        finally:
            root.destroy()
            tema.definir_tema_atual("claro")

    def test_notebook_interno_usa_estilo_sem_moldura(self):
        """Notebook interno mantém abas e remove a moldura externa."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            style = components.configure_styles(root)
            notebook = ttk.Notebook(root, style="Inner.TNotebook")
            primeira = tk.Frame(notebook)
            segunda = tk.Frame(notebook)
            notebook.add(primeira, text="Primeira")
            notebook.add(segunda, text="Segunda")
            notebook.select(segunda)
            self.assertEqual(str(style.lookup("Inner.TNotebook", "borderwidth")), "0")
            self.assertTrue(style.layout("Inner.TNotebook"))
            self.assertEqual(notebook.index(notebook.select()), 1)
            self.assertEqual(
                style.lookup("Inner.TNotebook.Tab", "foreground", ("selected",)),
                tema.obter_tema_atual()["primary"],
            )
            tema.definir_tema_atual("escuro")
            style = components.configure_styles(root, "escuro")
            self.assertEqual(
                style.lookup("Inner.TNotebook.Tab", "foreground", ("selected",)),
                tema.TEMA_ESCURO["primary"],
            )
        finally:
            root.destroy()
            tema.definir_tema_atual("claro")

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
                from app.estoque.painel import PainelEstoque

                painel = PainelEstoque(root)
                painel.pack(fill="both", expand=True)
                root.geometry("1100x700")
                root.deiconify()
                root.update()
                self.assertIsInstance(painel, PainelEstoque)
                self.assertTrue(
                    painel._search_input.winfo_ismapped(),
                    "A pesquisa deve estar disponível assim que a aba Produtos abrir",
                )
                self.assertFalse(painel._filtros_content.winfo_ismapped())
                painel._btn_toggle_filtros.invoke()
                root.update()
                self.assertTrue(painel._filtros_content.winfo_ismapped())
                self.assertEqual(painel._btn_toggle_filtros.cget("text"), "Ocultar filtros ▴")
                painel._btn_toggle_filtros.invoke()
                root.update()
                self.assertFalse(painel._filtros_content.winfo_ismapped())
                self.assertTrue(painel._search_input.winfo_ismapped())
                self.assertEqual(painel._btn_toggle_filtros.cget("text"), "Mostrar filtros ▾")
                painel.atualizar()
                painel._limpar_filtros()
                root.geometry("760x700")
                root.update()
                self.assertEqual(painel._kpi_columns, 4)
                root.geometry("1000x700")
                root.update()
                self.assertEqual(painel._kpi_columns, 8)
            finally:
                database.DB_PATH = db_path_original
                root.destroy()

    def test_caixa_local_carrega_produtos_e_preserva_area_util_da_tabela(self):
        """A aba Produtos deve carregar no modo local e manter a tabela utilizável."""
        try:
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        db_path_original = database.DB_PATH
        with tempfile.TemporaryDirectory() as temp_dir:
            database.DB_PATH = Path(temp_dir) / "loja_teste.db"
            try:
                database.inicializar()
                with database.get_conn() as conn:
                    conn.execute(
                        """
                        INSERT INTO produtos (codigo, nome, preco_centavos, estoque)
                        VALUES ('VISUAL', 'Produto visível', 1000, 5)
                        """
                    )

                from app.ui.app_window import CaixaApp

                app = CaixaApp()
                app.geometry("1100x700")
                app.update()
                app._notebook.select(app._aba_estoque)
                app._estoque_notebook.select(1)
                app.update()

                self.assertEqual(len(app._estoque_panel._produtos), 1)
                self.assertEqual(len(app._estoque_panel._tree.get_children()), 1)
                self.assertTrue(app._estoque_panel._search_input.winfo_ismapped())
                self.assertFalse(app._estoque_panel._filtros_content.winfo_ismapped())
                self.assertGreaterEqual(app._estoque_panel._tree.winfo_height(), 250)
                altura_tabela_recolhida = app._estoque_panel._tree.winfo_height()

                app._estoque_panel._btn_toggle_filtros.invoke()
                app.update()
                self.assertTrue(app._estoque_panel._filtros_content.winfo_ismapped())
                self.assertEqual(
                    app._estoque_panel._btn_toggle_filtros.cget("text"),
                    "Ocultar filtros ▴",
                )
                self.assertTrue(app._estoque_panel._lbl_resultados.winfo_ismapped())
                self.assertEqual(
                    app._estoque_panel._tree.winfo_height(),
                    altura_tabela_recolhida,
                    "Mostrar filtros não pode reduzir a área da tabela",
                )

                app._estoque_panel._btn_toggle_filtros.invoke()
                app.update()
                self.assertFalse(app._estoque_panel._filtros_content.winfo_ismapped())
                self.assertTrue(app._estoque_panel._search_input.winfo_ismapped())
                self.assertGreaterEqual(app._estoque_panel._tree.winfo_height(), 250)
            finally:
                if "app" in locals():
                    app.destroy()
                database.DB_PATH = db_path_original


if __name__ == "__main__":
    unittest.main()
