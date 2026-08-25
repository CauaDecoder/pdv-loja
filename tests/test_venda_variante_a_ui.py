"""Testes para a Tela de Venda Variante A (Issue #16)."""

import unittest
import tkinter as tk
import tempfile
import time
from pathlib import Path

from app import database
from app.ui.app_window import CaixaApp


class VendaVarianteAUITest(unittest.TestCase):

    def _aguardar(self, app, condicao, timeout=2.0):
        limite = time.monotonic() + timeout
        while not condicao() and time.monotonic() < limite:
            app.update()
            time.sleep(0.01)

    def setUp(self):
        self._db_path_original = database.DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._temp_dir.name) / "loja_teste.db"
        database.inicializar()

        # Cadastra produtos de teste (um com estoque normal e outro com estoque baixo)
        with database.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO produtos
                    (codigo, cod_barras, nome, preco_centavos, estoque)
                VALUES ('P1', '789000001', 'Produto Normal', 1500, 20)
                """
            )
            conn.execute(
                """
                INSERT INTO produtos
                    (codigo, cod_barras, nome, preco_centavos, estoque)
                VALUES ('P2', '789000002', 'Produto Estoque Baixo', 2500, 3)
                """
            )

    def tearDown(self):
        database.DB_PATH = self._db_path_original
        self._temp_dir.cleanup()

    def test_busca_produto_e_adicao_direta(self):
        """Testa a adicao direta de produto unico ao carrinho por codigo."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            # Simula busca por codigo exato 'P1'
            app._var_busca.set("P1")
            app._on_enter_busca()
            self._aguardar(app, lambda: bool(app._carrinho))

            self.assertEqual(len(app._carrinho), 1)
            self.assertEqual(app._carrinho[0]["codigo"], "P1")
            self.assertEqual(app._carrinho[0]["quantidade"], 1)
        finally:
            app.destroy()

    def test_alerta_estoque_baixo(self):
        """Testa a exibicao de alerta de estoque baixo para produtos com <= 5 unidades."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            # Adiciona produto com estoque = 3
            prod_baixo = database.buscar_produto("P2")[0]
            app._adicionar_produto(dict(prod_baixo))

            self.assertEqual(len(app._carrinho), 1)
            self.assertEqual(app._carrinho[0]["estoque"], 3)
            badges = [widget.cget("text") for widget in app._status_pills.winfo_children()]
            self.assertIn("1 alerta de estoque baixo", badges)
        finally:
            app.destroy()

    def test_carrinho_reutiliza_linha_ao_alterar_quantidade(self):
        """Alterar quantidade mantém a linha visual existente do produto."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            produto = dict(database.buscar_produto("P1")[0])
            app._adicionar_produto(produto)
            row = app._cart_rows[produto["id"]].row
            app._adicionar_produto(produto)

            self.assertIs(app._cart_rows[produto["id"]].row, row)
            self.assertEqual(
                app._cart_rows[produto["id"]].quantidade.cget("text"),
                "2 un.",
            )
        finally:
            app.destroy()

    def test_layout_alterna_altura_compacta_sem_atributos_obsoletos(self):
        """Redimensionar a Tela de venda não depende de widgets removidos."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            app.deiconify()
            app.geometry("1366x728")
            app.update()
            app._ajustar_layout_responsivo()
            self.assertTrue(app._compacto_altura)

            app.geometry("1366x800")
            app.update()
            app._ajustar_layout_responsivo()
            self.assertFalse(app._compacto_altura)
        finally:
            app.destroy()

    def test_todas_as_abas_renderizam_em_resolucoes_operacionais(self):
        """Abas principais e de estoque renderizam nas duas resoluções alvo."""
        try:
            app = CaixaApp()
            app.deiconify()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            for geometria in ("1366x768", "900x650", "760x560"):
                app.geometry(geometria)
                app.update()
                if geometria == "760x560":
                    self.assertGreaterEqual(app._left_panel.winfo_width(), 450)
                    self.assertGreaterEqual(app._right_panel.winfo_width(), 270)
                for tab_id in app._notebook.tabs():
                    app._notebook.select(tab_id)
                    app.update()
                    self.assertEqual(app._notebook.select(), tab_id)
                app._notebook.select(app._aba_estoque)
                for tab_id in app._estoque_notebook.tabs():
                    app._estoque_notebook.select(tab_id)
                    app.update()
                    self.assertEqual(app._estoque_notebook.select(), tab_id)
        finally:
            app.destroy()

    def test_carrinho_renderiza_dez_itens_sem_recriar_linhas(self):
        """Carrinho com dez produtos atualiza quantidades preservando suas linhas."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            app._carrinho = [
                {
                    "produto_id": indice,
                    "codigo": f"P{indice}",
                    "nome": f"Produto {indice}",
                    "quantidade": 1,
                    "preco_unit": 10.0,
                    "estoque": 20,
                }
                for indice in range(1, 11)
            ]
            app._renderizar_carrinho()
            linhas = {produto_id: widgets.row for produto_id, widgets in app._cart_rows.items()}

            for item in app._carrinho:
                item["quantidade"] = 2
            app._renderizar_carrinho()

            self.assertEqual(len(app._cart_rows), 10)
            for produto_id, row in linhas.items():
                self.assertIs(app._cart_rows[produto_id].row, row)
        finally:
            app.destroy()

    def test_estado_botao_finalizar_venda(self):
        """Testa se o botao Finalizar Venda so habilita quando carrinho e pagamento estao prontos."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            # Carrinho vazio: desabilitado
            self.assertEqual(app._btn_finalizar.cget("state"), "disabled")

            # Com produto mas sem pagamento: desabilitado
            prod = database.buscar_produto("P1")[0]
            app._adicionar_produto(dict(prod))
            self.assertEqual(app._btn_finalizar.cget("state"), "disabled")

            # Seleciona pagamento Pix: habilita
            app._selecionar_pgto("Pix")
            self.assertEqual(app._btn_finalizar.cget("state"), "normal")
        finally:
            app.destroy()

    def test_fluxo_comum_expoe_atalhos_para_pagamento_e_finalizacao(self):
        """O operador chega ao pagamento e finaliza sem depender do mouse."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            app._var_busca.set("P1")
            app._on_enter_busca()
            self._aguardar(app, lambda: bool(app._carrinho))
            app._var_responsavel.set("Operadora Teste")

            self.assertTrue(app.bind_all("<F4>"))
            self.assertTrue(app.bind_all("<F8>"))

            app._focar_pagamento()
            self.assertEqual(app._btns_pgto["Debito"].cget("takefocus"), 1)

            app._btns_pgto["Pix"].invoke()
            self.assertEqual(app._pagamento, "Pix")

            venda_atual = app._num_venda
            app._finalizar_venda_por_atalho()

            self.assertEqual(app._num_venda, venda_atual + 1)
            self.assertEqual(app._carrinho, [])
        finally:
            app.destroy()

    def test_debito_abre_modal_e_seleciona_pagamento(self):
        """Débito deve concluir a seleção usando o modal real de cartão."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        def confirmar_modal(tentativas=20):
            modais = [
                filho
                for filho in app.winfo_children()
                if isinstance(filho, tk.Toplevel)
            ]
            if not modais and tentativas:
                app.after(20, lambda: confirmar_modal(tentativas - 1))
                return
            self.assertTrue(modais, "O modal de cartão não foi aberto")
            modal = modais[0]
            botoes = []
            pendentes = [modal]
            while pendentes:
                widget = pendentes.pop()
                pendentes.extend(widget.winfo_children())
                if isinstance(widget, tk.Button):
                    botoes.append(widget)
            confirmar = next(
                botao for botao in botoes if botao.cget("text") == "Confirmar"
            )
            confirmar.invoke()

        try:
            app.after(20, confirmar_modal)
            app._selecionar_pgto("Debito")

            self.assertEqual(app._pagamento, "Debito")
            self.assertTrue(app._pagamento_detalhe)
            self.assertEqual(app._btn_finalizar.cget("state"), "disabled")
        finally:
            app.destroy()

    def test_abas_usam_uma_unica_margem_de_pagina(self):
        """Notebooks não devem somar molduras às margens internas das telas."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            self.assertEqual(int(app._notebook.pack_info()["padx"]), 0)
            self.assertEqual(int(app._estoque_notebook.pack_info()["padx"]), 0)
            rotulos = [
                widget.cget("text")
                for widget in app._estoque_movimentacoes._tipo_box.master.winfo_children()
                if isinstance(widget, tk.Label)
            ]
            self.assertIn("Tipo", rotulos)
        finally:
            app.destroy()

    def test_pagamento_misto_lista_todas_as_formas_disponiveis(self):
        """O modal misto deve expor controles para cada forma combinável."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        formas_encontradas = []
        app._adicionar_produto(dict(database.buscar_produto("P1")[0]))

        def inspecionar_modal(tentativas=20):
            modais = [
                filho for filho in app.winfo_children()
                if isinstance(filho, tk.Toplevel)
            ]
            if not modais and tentativas:
                app.after(20, lambda: inspecionar_modal(tentativas - 1))
                return
            if modais:
                controles = {}
                botoes = []
                pendentes = [modais[0]]
                while pendentes:
                    widget = pendentes.pop()
                    pendentes.extend(widget.winfo_children())
                    if isinstance(widget, tk.Checkbutton):
                        formas_encontradas.append(widget.cget("text"))
                        controles[widget.cget("text")] = widget
                    if isinstance(widget, tk.Button):
                        botoes.append(widget)
                controles["Débito"].invoke()
                controles["Pix"].invoke()
                confirmar = next(
                    botao for botao in botoes
                    if botao.cget("text") == "Confirmar"
                )
                confirmar.invoke()

        try:
            app.after(20, inspecionar_modal)
            app._selecionar_pgto("Mais de uma forma")
            self.assertCountEqual(
                formas_encontradas,
                ["Dinheiro", "Débito", "Crédito", "Pix"],
            )
            self.assertEqual(app._pagamento, "Mais de uma forma")
            self.assertEqual(app._pagamento_detalhe, "Debito (Visa) + Pix")
        finally:
            app.destroy()

    def test_textos_operacionais_preservam_acentos(self):
        """Textos literais da tela não podem substituir acentos por interrogações."""
        try:
            app = CaixaApp()
            app.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            self.assertIn("Débito", app._btns_pgto["Debito"].cget("text"))
            self.assertIn("Crédito", app._btns_pgto["Credito"].cget("text"))
            for botao in app._btns_pgto.values():
                self.assertNotIn("?", botao.cget("text"))
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
