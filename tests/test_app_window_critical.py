from __future__ import annotations

import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch

from app.ui.app_window import CaixaApp


def test_finalizacao_bloqueia_operador_vazio_antes_de_chamar_dominio():
    app = CaixaApp.__new__(CaixaApp)
    app._carrinho = [{"produto_id": 1}]
    app._pagamento = "Pix"
    app._var_responsavel = Mock()
    app._var_responsavel.get.return_value = "   "
    app._entry_responsavel = Mock()

    with patch("app.ui.app_window.messagebox.showerror") as showerror, patch(
        "app.ui.app_window.db.registrar_venda"
    ) as registrar:
        app._finalizar_venda()

    registrar.assert_not_called()
    showerror.assert_called_once()
    app._entry_responsavel.focus_set.assert_called_once()


def test_pagamento_da_ui_usa_arredondamento_comercial_em_centavos():
    app = CaixaApp.__new__(CaixaApp)
    app._pagamento = "Pix"
    app._pagamento_detalhe = ""
    app._valor_recebido = None
    app._troco = None
    app._total_carrinho = Mock(return_value=0.025)
    app._var_destino_financeiro = Mock()
    app._var_destino_financeiro.get.return_value = "Conta Pix"
    app._destinos_disponiveis = {"Conta Pix": 2}

    assert app._pagamentos_da_venda() == [{
        "forma": "Pix",
        "valor_centavos": 3,
        "detalhe": "",
        "valor_recebido_centavos": None,
        "troco_centavos": None,
        "destino_id": 2,
    }]


def test_kpis_iniciais_usam_totais_reais_do_periodo():
    app = CaixaApp.__new__(CaixaApp)
    app._lbl_vendas_dia = Mock()
    app._lbl_total_dia = Mock()
    app._kpi_hoje = Mock()
    app._kpi_vendas = Mock()
    app._kpi_correcoes = Mock()

    app._aplicar_totais_periodo({"transacoes": 0, "total": 0.0, "correcoes": 0})

    app._kpi_hoje.value_label.config.assert_called_once_with(text="R$ 0,00")
    app._kpi_vendas.value_label.config.assert_called_once_with(text="0")
    app._kpi_correcoes.value_label.config.assert_called_once_with(text="0")


def test_relogio_fecha_periodo_e_abre_outro_na_virada_da_data():
    app = CaixaApp.__new__(CaixaApp)
    app._lbl_relogio = Mock()
    app._data_hoje = "01/01/2000"
    app._carrinho = []
    app._abrir_periodo_para_data = Mock()
    app.after = Mock(return_value="clock-id")

    with patch("app.ui.app_window.datetime") as relogio:
        relogio.now.return_value = datetime(2000, 1, 2, 0, 0)
        app._atualizar_relogio()

    app._abrir_periodo_para_data.assert_called_once_with("02/01/2000")
    app.after.assert_called_once_with(30000, app._atualizar_relogio)
    assert app._clock_after_id == "clock-id"


def test_fechamento_salva_snapshot_antes_de_exportar_relatorio(tmp_path):
    app = CaixaApp.__new__(CaixaApp)
    app._periodo_id = 7
    app._periodo_seq = 1
    app._carrinho = []
    app._var_responsavel = Mock()
    app._var_responsavel.get.return_value = "Ana"
    app._entry_responsavel = Mock()
    app._abrir_periodo_para_data = Mock()
    app._mostrar_feedback_venda = Mock()
    eventos = []

    def fechar(periodo_id, responsavel):
        eventos.append("fechar")
        assert (periodo_id, responsavel) == (7, "Ana")
        return {
            "proximo_periodo_id": 8,
            "total_vendas_centavos": 1000,
        }

    def exportar(periodo_id, destino):
        eventos.append("exportar")
        assert periodo_id == 7
        return tmp_path / destino.name

    with patch("app.ui.app_window.sync_pending_sales"), patch(
        "app.ui.app_window.pending_sales", return_value=0
    ), patch(
        "app.ui.app_window.db.obter_periodo",
        side_effect=[{"id": 7, "data": "2026-08-19"}, {"id": 8, "data": "2026-08-19"}],
    ), patch(
        "app.ui.app_window.db.fechar_periodo_loja", side_effect=fechar
    ), patch(
        "app.ui.app_window.period_report", side_effect=exportar
    ), patch("app.ui.app_window.messagebox.showinfo"):
        app._encerrar_dia()

    assert eventos == ["fechar", "exportar"]
    assert app._periodo_id == 8
    app._abrir_periodo_para_data.assert_called_once_with("2026-08-19")


def test_resumo_de_pagamento_misto_expoe_as_formas_na_lateral():
    app = CaixaApp.__new__(CaixaApp)
    app._pagamento = "Mais de uma forma"
    app._pagamento_detalhe = "Pix + Dinheiro (Recebido R$ 5,00; troco R$ 0,00)"
    app._valor_recebido = 5.0
    app._troco = 0.0
    app._lbl_pgto_resumo = Mock()

    app._atualizar_resumo_pagamento_lateral()

    app._lbl_pgto_resumo.config.assert_called_once_with(
        text="Pix + Dinheiro (Recebido R$ 5,00; troco R$ 0,00)"
    )
    app._lbl_pgto_resumo.pack.assert_called_once()


def test_destinos_sqlite_sao_normalizados_antes_de_montar_pagamento():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    destino = conn.execute(
        "SELECT 2 AS id, 'Conta Pix' AS nome, 'Pix' AS formas, 'Pix' AS formas_padrao"
    ).fetchone()
    app = CaixaApp.__new__(CaixaApp)
    app._initial_destinations = [destino]

    try:
        assert app._listar_destinos_financeiros() == [{
            "id": 2,
            "nome": "Conta Pix",
            "formas": "Pix",
            "formas_padrao": "Pix",
        }]
    finally:
        conn.close()


def test_abrir_aba_vendas_recarrega_lista_atualizada():
    app = CaixaApp.__new__(CaixaApp)
    app._aba_vendas_correcoes = Mock()
    app._notebook = Mock()
    app._lazy_tab_builders = {}
    app._notebook.select.return_value = str(app._aba_vendas_correcoes)
    app._atualizar_historico = Mock()

    app._on_main_tab_changed()

    app._atualizar_historico.assert_called_once_with()


def test_aba_vendas_local_nao_recebe_loader_remoto():
    app = CaixaApp.__new__(CaixaApp)
    app._aba_vendas_correcoes = Mock()
    app._apos_atualizacao_venda = Mock()

    with patch("app.ui.app_window.remote_mode", return_value=False), patch(
        "app.ui.app_window.VendasCorrecoesView"
    ) as view_class:
        app._build_vendas_correcoes_tab()

    assert view_class.call_args.kwargs["autoload"] is True
    assert view_class.call_args.kwargs["loader"] is None
