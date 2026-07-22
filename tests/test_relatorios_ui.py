"""Testes para a interface da aba Relatórios e Fechamento (Issue #18)."""

import unittest
import tkinter as tk
import tempfile
from pathlib import Path

import database
from app.services import vendas_service
from app.ui.relatorios_view import RelatoriosView


class RelatoriosUITest(unittest.TestCase):

    def setUp(self):
        self._db_path_original = database.DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self._temp_dir.name) / "loja_teste.db"
        database.inicializar()

        # Prepara um periodo e grava vendas: 1 valida, 1 corrigida e 1 cancelada
        with database.get_conn() as conn:
            periodo_id = conn.execute(
                """
                INSERT INTO periodos_caixa (data, sequencia, aberto_em, responsavel)
                VALUES ('2026-07-22', 1, '2026-07-22T08:00:00', 'Maria Operadora')
                """
            ).lastrowid
            prod_id = conn.execute(
                """
                INSERT INTO produtos (codigo, nome, preco, estoque)
                VALUES ('P1', 'Produto Teste', 50.0, 10)
                """
            ).lastrowid
            self.periodo_id = periodo_id

        # Venda 1: Valida (Pix R$ 50)
        database.registrar_venda(
            self.periodo_id,
            1,
            [{"produto_id": prod_id, "codigo": "P1", "nome": "Produto Teste", "quantidade": 1, "preco_unit": 50.0}],
            "Pix",
            responsavel="Maria Operadora",
            data="2026-07-22",
        )

        # Venda 2: Cancelada (Dinheiro R$ 50)
        database.registrar_venda(
            self.periodo_id,
            2,
            [{"produto_id": prod_id, "codigo": "P1", "nome": "Produto Teste", "quantidade": 1, "preco_unit": 50.0}],
            "Dinheiro",
            responsavel="Maria Operadora",
            data="2026-07-22",
        )
        vendas_service.cancelar_venda(self.periodo_id, 2, responsavel="Maria Operadora", observacao="Teste cancelamento")

    def tearDown(self):
        database.DB_PATH = self._db_path_original
        self._temp_dir.cleanup()

    def test_instanciacao_e_fechamento_liquido(self):
        """Testa se o relatorio calcula corretamente o financeiro liquido e separa canceladas."""
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        try:
            view = RelatoriosView(root, periodo_id_provider=lambda: self.periodo_id)
            view.atualizar()

            mov = view._dados_fechamento["financial_movement"]
            canceladas = view._dados_fechamento["cancelled_sales"]

            # Apenas 1 venda valida (Pix R$ 50.0)
            self.assertEqual(mov["transactions"], 1)
            self.assertEqual(mov["total"], 50.0)
            self.assertIn("Pix", mov["payment_summary"])
            self.assertNotIn("Dinheiro", mov["payment_summary"])

            # 1 venda cancelada em separado
            self.assertEqual(len(canceladas), 1)
            self.assertEqual(canceladas[0]["sale_number"], 2)
            self.assertEqual(canceladas[0]["status"], "cancelled")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
