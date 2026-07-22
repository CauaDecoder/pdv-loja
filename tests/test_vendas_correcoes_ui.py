"""Testes para a interface da aba Vendas e correções e modal de detalhes (Issue #15)."""

import unittest
import tkinter as tk
import tempfile
from pathlib import Path

import database
from app.ui.vendas_correcoes_view import VendasCorrecoesView, VendaDetailModal


class VendasCorrecoesUITest(unittest.TestCase):

    def setUp(self):
        self._db_path_original = database.DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._temp_dir.name) / "loja_teste.db"
        database.inicializar()

    def tearDown(self):
        database.DB_PATH = self._db_path_original
        self._temp_dir.cleanup()

    def test_instanciacao_e_carregamento_da_view(self):
        """Testa se a view de Vendas e correcoes e instanciada sem erros."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            view = VendasCorrecoesView(root)
            self.assertIsNotNone(view._tree)
            # Deve carregar os dados (reais ou mocks de demonstracao)
            self.assertGreater(len(view._vendas_carregadas), 0)
        finally:
            root.destroy()

    def test_filtros_de_pesquisa(self):
        """Testa a selecao de filtros por status e forma de pagamento."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            view = VendasCorrecoesView(root)

            # Filtra por status 'valid'
            view._var_status.set("Válida")
            view.atualizar()
            for v in view._vendas_carregadas:
                self.assertEqual(v["status"], "valid")

            # Filtra por status 'cancelled'
            view._var_status.set("Cancelada")
            view.atualizar()
            for v in view._vendas_carregadas:
                self.assertEqual(v["status"], "cancelled")

            # Limpa filtros
            view._limpar_filtros()
            self.assertEqual(view._var_status.get(), "Todos")
        finally:
            root.destroy()

    def test_instanciacao_modal_detalhe_venda(self):
        """Testa se o modal de detalhe renderiza com historico e contrato."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            detalhe_mock = {
                "identity": {"sale_number": 10, "period_id": 1},
                "status": "corrected",
                "responsible": "Maria Teste",
                "timestamps": {"date": "22/07/2026", "time": "15:00"},
                "payment": {"method": "Pix", "detail": "Chave QR", "received": None, "change": None},
                "items": [
                    {
                        "line_id": 1,
                        "product_id": 1,
                        "code": "123",
                        "name": "Item Teste",
                        "quantity": 2,
                        "unit_price": 10.0,
                        "subtotal": 20.0,
                    }
                ],
                "totals": {"items": 1, "units": 2, "total": 20.0},
                "correction_history": [
                    {
                        "action": "alter_payment",
                        "created_at": "22/07/2026 15:05",
                        "responsible": "Maria Teste",
                        "before": "Dinheiro",
                        "after": "Pix",
                        "notes": "Alterado",
                    }
                ],
                "available_actions": ["alter_payment", "alter_item_quantity", "remove_item", "cancel_sale"],
            }

            modal = VendaDetailModal(root, detalhe_mock)
            self.assertEqual(modal._detalhe["identity"]["sale_number"], 10)
            modal.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
