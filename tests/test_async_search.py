import inspect
import os
import threading
import time

os.environ["CAIXA_TERMINAL_CONFIG"] = "tests/nonexistent-terminal-config.json"

from app.ui.app_window import CaixaApp


class _Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _SearchHarness:
    _on_busca = CaixaApp._on_busca
    _on_enter_busca = CaixaApp._on_enter_busca
    _start_product_search = CaixaApp._start_product_search
    _complete_product_search = CaixaApp._complete_product_search
    _add_best_product_match = CaixaApp._add_best_product_match

    def __init__(self, search):
        self._var_busca = _Value("old")
        self._search = search
        self._search_generation = 0
        self._search_debounce_id = None
        self._search_inflight = {}
        self._search_result_term = ""
        self._search_enter_generation = None
        self._resultados_busca = []
        self._closed = False
        self.callbacks = []
        self.visible = []
        self.added = []

    def after(self, _delay, callback, *args):
        self.callbacks.append((callback, args))
        return str(len(self.callbacks))

    def after_cancel(self, _callback_id):
        self.callbacks.clear()

    def _submit_background(self, work, done):
        thread = threading.Thread(target=lambda: done(work(), None), daemon=True)
        thread.start()

    def _render_product_results(self, results):
        self.visible = list(results)
        self._resultados_busca = list(results)

    def _esconder_sugestoes(self):
        self.visible = []
        self._resultados_busca = []

    def _adicionar_produto(self, product):
        self.added.append(product)


def test_sale_screen_keeps_product_search_in_left_panel():
    """Busca usa um único gerenciador de geometria dentro do painel esquerdo."""
    build_ui = inspect.getsource(CaixaApp._build_ui)
    build_left = inspect.getsource(CaixaApp._build_left)
    render = inspect.getsource(CaixaApp._render_product_results)
    hide = inspect.getsource(CaixaApp._esconder_sugestoes)

    assert not hasattr(CaixaApp, "_build_variant_b_header")
    assert not hasattr(CaixaApp, "_build_variant_b_command")
    assert "_build_variant_b_command" not in build_ui
    assert "SearchInput(" in build_left
    assert "tk.Frame(search_card" in build_left
    assert "self._frame_sugestoes.pack(" in render
    assert "self._frame_sugestoes.pack_forget()" in hide


def test_sale_screen_restores_pre_variant_b_hierarchy():
    """Tela principal mantém a composição anterior aos agentes de redesign."""
    build_left = inspect.getsource(CaixaApp._build_left)
    build_right = inspect.getsource(CaixaApp._build_right)
    mixed_payment = inspect.getsource(CaixaApp._coletar_pagamento_misto)

    assert "cart_header =" not in build_left
    assert "UNITÁRIO" not in build_left
    assert "_right_fixed_summary" not in build_right
    assert "panel_totais = tk.Frame(self._card_pagamento" in build_right
    assert 'info["parcela"].pack_forget()' in mixed_payment
    assert 'if vars_pgto[forma].get()' in mixed_payment


def test_search_callback_returns_immediately_with_slow_adapter():
    def slow_search(term):
        time.sleep(0.15)
        return [{"id": 1, "codigo": term, "cod_barras": "", "nome": term, "preco": 1}]

    harness = _SearchHarness(slow_search)
    started = time.perf_counter()
    harness._on_busca()
    elapsed = time.perf_counter() - started

    assert elapsed < 0.05
    assert len(harness.callbacks) == 1


def test_old_search_response_cannot_replace_current_term():
    gates = {"old": threading.Event(), "new": threading.Event()}

    def controlled_search(term):
        gates[term].wait(1)
        return [{"id": 1, "codigo": term, "cod_barras": "", "nome": term, "preco": 1}]

    harness = _SearchHarness(controlled_search)
    harness._start_product_search("old", 1, False)
    harness._search_generation = 2
    harness._var_busca.value = "new"
    harness._start_product_search("new", 2, False)
    gates["new"].set()
    time.sleep(0.03)
    gates["old"].set()
    time.sleep(0.03)

    assert [item["codigo"] for item in harness.visible] == ["new"]


def test_remote_tab_loads_only_on_first_selection():
    calls = []

    class Notebook:
        def select(self):
            return "stock"

    class Harness:
        _on_main_tab_changed = CaixaApp._on_main_tab_changed
        _notebook = Notebook()
        _lazy_tab_builders = {"stock": lambda: calls.append("loaded")}

        def after_idle(self, callback, *args):
            callback(*args)

        def _build_selected_tab(self, _tab, builder):
            builder()

    harness = Harness()
    harness._on_main_tab_changed()
    harness._on_main_tab_changed()

    assert calls == ["loaded"]


def test_enter_reuses_completed_term_without_second_request():
    calls = []

    def search(term):
        calls.append(term)
        return [{"id": 1, "codigo": "A1", "cod_barras": "789", "nome": "Produto", "preco": 1}]

    harness = _SearchHarness(search)
    harness._var_busca.value = "A1"
    harness._search_generation = 1
    harness._start_product_search("A1", 1, False)
    time.sleep(0.03)

    assert harness._on_enter_busca() == "break"
    assert calls == ["A1"]
    assert [item["codigo"] for item in harness.added] == ["A1"]
