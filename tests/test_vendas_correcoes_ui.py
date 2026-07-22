"""Testes para a interface da aba Vendas e correções e modal de detalhes (Issue #15)."""

import unittest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch

from app.ui.vendas_correcoes_view import (
    VendasCorrecoesView,
    VendaDetailModal,
    ler_quantidade,
    ler_valor_monetario_opcional,
)


def _descendentes(widget):
    for filho in widget.winfo_children():
        yield filho
        yield from _descendentes(filho)


def _botao_com_texto(widget, texto):
    return next(
        filho
        for filho in _descendentes(widget)
        if isinstance(filho, tk.Button) and filho.cget("text") == texto
    )


def _detalhe_venda(**overrides):
    detalhe = {
        "identity": {"sale_number": 10, "period_id": 1},
        "status": "corrected",
        "responsible": "Maria Teste",
        "timestamps": {"date": "22/07/2026", "time": "15:00"},
        "payment": {
            "method": "Pix",
            "detail": "Chave QR",
            "received": None,
            "change": None,
        },
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
        "correction_history": [],
        "available_actions": [
            "alter_payment",
            "alter_item_quantity",
            "remove_item",
            "cancel_sale",
        ],
    }
    detalhe.update(overrides)
    return detalhe


def test_quantidade_invalida_tem_mensagem_operacional_clara():
    with unittest.TestCase().assertRaisesRegex(
        ValueError, "Informe a nova quantidade em unidades inteiras"
    ):
        ler_quantidade("1,5")


def test_valor_monetario_opcional_aceita_virgula_e_campo_vazio():
    assert ler_valor_monetario_opcional("30,50", "Valor recebido") == 30.5
    assert ler_valor_monetario_opcional("", "Troco") is None


def test_valor_monetario_rejeita_valores_nao_finitos():
    for valor in ("NaN", "Infinity", "-Infinity"):
        with unittest.TestCase().assertRaisesRegex(ValueError, "valor monetario valido"):
            ler_valor_monetario_opcional(valor, "Valor recebido")


def test_sucesso_da_correcao_atualiza_detalhe_e_lista():
    modal = object.__new__(VendaDetailModal)
    modal._detalhe = {"status": "valid"}
    modal._build_ui = Mock()
    modal._on_updated = Mock()
    origem = Mock()
    origem.winfo_exists.return_value = True
    detalhe_atualizado = {"status": "corrected"}

    with patch("app.ui.vendas_correcoes_view.messagebox.showinfo"):
        modal._executar_correcao(
            Mock(return_value=detalhe_atualizado),
            titulo_erro="Erro",
            titulo_sucesso="Sucesso",
            mensagem_sucesso="Atualizada",
            fechar_ao_concluir=origem,
        )

    assert modal._detalhe is detalhe_atualizado
    modal._build_ui.assert_called_once_with()
    modal._on_updated.assert_called_once_with()
    origem.after_idle.assert_called_once_with(origem.destroy)
    assert origem.configure.call_args_list[0].kwargs == {"cursor": "watch"}


def test_erro_da_correcao_preserva_detalhe_e_exibe_mensagem_clara():
    modal = object.__new__(VendaDetailModal)
    detalhe_original = {"status": "valid"}
    modal._detalhe = detalhe_original
    modal._build_ui = Mock()
    modal._on_updated = Mock()
    origem = Mock()
    origem.winfo_exists.return_value = True

    with patch("app.ui.vendas_correcoes_view.messagebox.showerror") as mostrar_erro:
        modal._executar_correcao(
            Mock(side_effect=ValueError("Venda cancelada nao pode receber nova correcao.")),
            titulo_erro="Ação não permitida",
            titulo_sucesso="Sucesso",
            mensagem_sucesso="Atualizada",
            fechar_ao_concluir=origem,
        )

    assert modal._detalhe is detalhe_original
    modal._build_ui.assert_not_called()
    modal._on_updated.assert_not_called()
    mostrar_erro.assert_called_once()
    assert "Venda cancelada" in mostrar_erro.call_args.args[1]


def test_servico_so_e_preparado_apos_confirmacao_explicita():
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        return

    try:
        modal = object.__new__(VendaDetailModal)
        modal._executar_correcao = Mock()
        corrigir = Mock()
        confirmacao = modal._confirmar_correcao(
            parent=root,
            titulo="Confirmar correção",
            risco="A correção ficará auditada.",
            corrigir=corrigir,
            titulo_erro="Erro",
            titulo_sucesso="Sucesso",
            mensagem_sucesso="Atualizada",
        )

        modal._executar_correcao.assert_not_called()
        corrigir.assert_not_called()

        confirmacao._handle_confirm()

        modal._executar_correcao.assert_called_once()
    finally:
        root.destroy()


class VendasCorrecoesUITest(unittest.TestCase):

    def setUp(self):
        self._listar_patch = patch(
            "app.ui.vendas_correcoes_view.vendas_service.listar_vendas_correcoes",
            return_value=[],
        )
        self._listar_vendas = self._listar_patch.start()

    def tearDown(self):
        self._listar_patch.stop()

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
            # Banco vazio deve permanecer vazio: a integracao nao usa mocks.
            self.assertEqual(view._vendas_carregadas, [])
        finally:
            root.destroy()

    def test_filtros_de_pesquisa(self):
        """Testa a selecao de filtros por status e forma de pagamento."""
        contratos = [
            {"status": "valid"},
            {"status": "cancelled"},
        ]
        self._listar_vendas.side_effect = lambda filtros: [
            venda
            for venda in contratos
            if not filtros.get("status") or venda["status"] == filtros["status"]
        ]
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
            detalhe_mock = _detalhe_venda(
                correction_history=[
                    {
                        "action": "alter_payment",
                        "created_at": "22/07/2026 15:05",
                        "responsible": "Maria Teste",
                        "before": "Dinheiro",
                        "after": "Pix",
                        "notes": "Alterado",
                    }
                ],
            )

            modal = VendaDetailModal(root, detalhe_mock)
            self.assertEqual(modal._detalhe["identity"]["sale_number"], 10)
            modal.destroy()
        finally:
            root.destroy()

    def test_quatro_acoes_estao_ligadas_aos_servicos_reais(self):
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Ambiente GUI Tkinter nao disponivel")
            return

        detalhe = _detalhe_venda(
            identity={"sale_number": 10, "period_id": 2},
            status="valid",
            responsible="Maria",
            payment={"method": "Pix", "detail": "", "received": None, "change": None},
        )

        try:
            modal = VendaDetailModal(root, detalhe)
            confirmar = patch.object(
                modal,
                "_confirmar_correcao",
                side_effect=lambda **dados: dados["corrigir"](),
            )
            pedir_responsavel = patch.object(
                modal,
                "_pedir_responsavel",
                side_effect=lambda **dados: dados["continuar"]("Ana"),
            )
            with (
                confirmar,
                pedir_responsavel,
                patch(
                    "app.ui.vendas_correcoes_view.vendas_service.alterar_pagamento_venda",
                    return_value=detalhe,
                ) as alterar_pagamento,
                patch(
                    "app.ui.vendas_correcoes_view.vendas_service.alterar_quantidade_item_venda",
                    return_value=detalhe,
                ) as alterar_quantidade,
                patch(
                    "app.ui.vendas_correcoes_view.vendas_service.remover_item_venda",
                    return_value=detalhe,
                ) as remover_item,
                patch(
                    "app.ui.vendas_correcoes_view.vendas_service.cancelar_venda",
                    return_value=detalhe,
                ) as cancelar_venda,
            ):
                modal._alterar_pagamento()
                sub_pagamento = next(
                    filho for filho in modal.winfo_children() if isinstance(filho, tk.Toplevel)
                )
                entradas = [
                    filho
                    for filho in _descendentes(sub_pagamento)
                    if isinstance(filho, tk.Entry) and not isinstance(filho, ttk.Combobox)
                ]
                entradas[-1].insert(0, "Ana")
                _botao_com_texto(sub_pagamento, "Salvar Alteração").invoke()
                alterar_pagamento.assert_called_once()
                sub_pagamento.destroy()

                modal._tree_items.selection_set("1")
                modal._alterar_quantidade()
                sub_quantidade = next(
                    filho for filho in modal.winfo_children() if isinstance(filho, tk.Toplevel)
                )
                entradas = [
                    filho
                    for filho in _descendentes(sub_quantidade)
                    if isinstance(filho, tk.Entry)
                ]
                entradas[-1].insert(0, "Ana")
                _botao_com_texto(sub_quantidade, "Salvar Quantidade").invoke()
                alterar_quantidade.assert_called_once()
                sub_quantidade.destroy()

                modal._tree_items.selection_set("1")
                modal._remover_item()
                remover_item.assert_called_once_with(
                    periodo_id=2,
                    num_venda=10,
                    line_id=1,
                    responsavel="Ana",
                )

                modal._cancelar_venda()
                cancelar_venda.assert_called_once_with(
                    periodo_id=2,
                    num_venda=10,
                    responsavel="Ana",
                    observacao="Cancelada via tela de Vendas e correções",
                )
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
