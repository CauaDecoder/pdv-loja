"""
Aplicacao principal do caixa da Loja da Basilica.

Este modulo concentra a interface grafica em Tkinter e orquestra o fluxo
principal do sistema:

1. Inicializa a base local de dados e o estado do caixa.
2. Monta as abas da interface de vendas, historico e estoque.
3. Controla o carrinho, os pagamentos e o fechamento das vendas.
4. Abre e encerra periodos, exporta relatorios e importa produtos.

Dependencias de negocio:
- `app/database.py`: persistencia, consultas e registro das vendas.
- `relatorio.py`: geracao do arquivo final do periodo.
- `app/estoque/painel.py`: painel visual de manutencao do estoque.

Execucao: `python main.py`
Requisitos: Python 3.10+, openpyxl
"""

import tkinter as tk
import queue
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app.contracts import valor_para_centavos
from app.runtime import close_remote_client, create_backup, database as db, pending_sales, period_report, remote_mode, reports as reports_runtime, restore_backup, sales as sales_runtime, sync_pending_sales
from app.payments import (
    CARD_BRANDS,
    CARD_INSTALLMENTS,
    MIXED_PAYMENT_METHODS,
    PAYMENT_LABELS,
    PaymentDetails,
    parse_currency,
    summarize_payment,
)
from app.services import importacao_service
from app.ui.importacao_view import ImportacaoGuidedView
from app.ui.relatorios_view import RelatoriosView
from app.ui.vendas_correcoes_view import VendasCorrecoesView
from app.estoque.dashboard import DashboardEstoque
from app.estoque.painel import PainelEstoque
from app.paths import BACKUPS_DIR, REPORTS_DIR
from app.ui import theme
from app.ui.components import (
    BaseModal,
    Card,
    DataTable,
    EmptyState,
    KpiCard,
    LabeledField,
    PageHeader,
    SearchInput,
    SectionHeader,
    StatusBadge,
    StyledEntry,
    action_button,
    apply_theme_to_widget_tree,
    bind_escape_to_close,
    bind_mousewheel_tree,
    configure_styles,
)
from app.ui.theme import (
    FONTES,
    definir_tema_atual,
    moeda,
    obter_nome_tema_atual,
)
PLACEHOLDER_BUSCA = "Escaneie o código ou busque pelo nome"


class StartupError(RuntimeError):
    """Erro operacional já apresentado ao usuário durante a abertura."""


@dataclass(slots=True)
class CartRowWidgets:
    """Mantém referências dos widgets mutáveis de uma linha do carrinho."""

    row: tk.Frame
    nome: tk.Label
    codigo: tk.Label
    alerta: StatusBadge
    quantidade: tk.Label
    subtotal: tk.Label


class MovimentacoesEstoque(tk.Frame):
    """Historico geral das movimentacoes de estoque."""

    def __init__(self, parent):
        super().__init__(parent, bg=theme.FUNDO)
        self._var_inicio = tk.StringVar()
        self._var_fim = tk.StringVar()
        self._var_tipo = tk.StringVar(value="Todos")
        self._var_termo = tk.StringVar()
        self._build_ui()
        self.atualizar()

    def _build_ui(self):
        PageHeader(self, "Movimentações de estoque", "Histórico de entradas, saídas e ajustes", "Atualizar", self.atualizar).pack(
            fill="x", padx=18, pady=(16, 10)
        )

        filtros = Card(self, padding=12)
        filtros.pack(fill="x", padx=18, pady=(0, 10))
        linha = tk.Frame(filtros, bg=theme.BRANCO)
        linha.pack(fill="x")
        for texto, var, largura in (
            ("Início", self._var_inicio, 12),
            ("Fim", self._var_fim, 12),
            ("Produto / código", self._var_termo, 24),
        ):
            bloco = tk.Frame(linha, bg=theme.BRANCO)
            bloco.pack(side="left", padx=(0, 10))
            tk.Label(bloco, text=texto, bg=theme.BRANCO, fg=theme.MUTED, font=FONTES["label_sm"]).pack(anchor="w")
            StyledEntry(bloco, textvariable=var, width=largura).pack(fill="x", ipady=7, pady=(3, 0))
        bloco_tipo = tk.Frame(linha, bg=theme.BRANCO)
        bloco_tipo.pack(side="left", padx=(0, 10))
        tk.Label(
            bloco_tipo,
            text="Tipo",
            bg=theme.BRANCO,
            fg=theme.MUTED,
            font=FONTES["label_sm"],
        ).pack(anchor="w")
        self._tipo_box = ttk.Combobox(
            bloco_tipo,
            textvariable=self._var_tipo,
            values=["Todos", "ENTRADA", "VENDA", "PERDA", "AJUSTE", "INVENTARIO"],
            state="readonly",
            width=16,
        )
        self._tipo_box.pack(fill="x", ipady=2, pady=(3, 0))

        box = Card(self, padding=0)
        box.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        colunas = ("data", "tipo", "codigo", "produto", "qtd", "saldo", "origem", "ref", "resp")
        titulos = {"data": "Data / hora", "tipo": "Tipo", "codigo": "Cód.", "produto": "Produto", "qtd": "Qtd", "saldo": "Saldo", "origem": "Origem", "ref": "Referência", "resp": "Responsável"}
        larguras = {"data": 120, "tipo": 90, "codigo": 70, "produto": 250, "qtd": 70, "saldo": 70, "origem": 120, "ref": 160, "resp": 140}
        self._tree = DataTable(box, colunas, titulos, larguras, height=14)
        self._tree.column("produto", anchor="w")
        self._tree.column("origem", anchor="w")
        self._tree.column("ref", anchor="w")
        self._tree.column("resp", anchor="w")
        self._tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(box, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

    def atualizar(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        tipo = "" if self._var_tipo.get() == "Todos" else self._var_tipo.get()
        for mov in db.listar_movimentacoes_estoque(
            limite=500,
            data_inicio=self._var_inicio.get().strip(),
            data_fim=self._var_fim.get().strip(),
            tipo=tipo,
            termo=self._var_termo.get().strip(),
        ):
            self._tree.insert(
                "",
                "end",
                values=(
                    f"{mov['data']} {mov['hora']}",
                    mov["tipo"],
                    mov["codigo"],
                    mov["nome"],
                    mov["quantidade"],
                    mov["estoque_resultante"],
                    mov["origem"] or "",
                    mov["referencia"] or "",
                    mov["responsavel"] or "",
                ),
            )


class ConfiguracoesEstoque(tk.Frame):
    """Tela simples para parametros de estoque e curva ABC."""

    CAMPOS = (
        ("abc_metodo", "Metodo ABC"),
        ("abc_limite_a", "Limite A"),
        ("abc_limite_b", "Limite B"),
        ("demanda_janela_dias", "Janela de demanda"),
        ("fator_seguranca", "Fator de seguranca"),
        ("estoque_morto_dias", "Dias para estoque morto"),
    )

    def __init__(self, parent):
        super().__init__(parent, bg=theme.FUNDO)
        self._vars: dict[str, tk.StringVar] = {}
        self._build_ui()
        self.atualizar()

    def _build_ui(self):
        frame = Card(self, padding=18)
        frame.pack(fill="both", expand=True, padx=18, pady=16)
        PageHeader(frame, "Configurações de estoque", "Parâmetros de curva ABC e reposição automática").pack(fill="x")
        form = tk.Frame(frame, bg=theme.BRANCO)
        form.pack(fill="x", pady=(16, 0))
        descricoes = {
            "abc_metodo": "Critério de classificação dos produtos.",
            "abc_limite_a": "Percentual acumulado para classe A.",
            "abc_limite_b": "Percentual acumulado para classe B.",
            "demanda_janela_dias": "Dias usados para cálculo de giro.",
            "fator_seguranca": "Multiplicador do ponto de pedido.",
            "estoque_morto_dias": "Produtos sem movimentação por este período entram como sem giro.",
        }
        for chave, rotulo in self.CAMPOS:
            var = tk.StringVar()
            linha = LabeledField(
                form,
                label=rotulo,
                description=descricoes.get(chave, ""),
                widget_factory=lambda parent, _var=var: tk.Entry(
                    parent,
                    textvariable=_var,
                    bg=theme.FUNDO2,
                    fg=theme.TEXTO,
                    relief="flat",
                    width=18,
                ),
            )
            linha.pack(fill="x", pady=(0, 10))
            linha.widget.pack(side="right", ipady=7, padx=(10, 0))
            self._vars[chave] = var
        tk.Button(frame, text="✓ Salvar configurações", bg=theme.VERDE_ESC, fg=theme.BRANCO, relief="flat", font=("Segoe UI", 10, "bold"), command=self._salvar).pack(anchor="e", pady=(6, 0))

    def atualizar(self):
        config = db.configuracoes()
        for chave, var in self._vars.items():
            var.set(config.get(chave, ""))

    def _salvar(self):
        db.atualizar_configuracoes({chave: var.get() for chave, var in self._vars.items()})
        messagebox.showinfo("Configuracoes salvas", "Parametros de estoque atualizados.")


class CaixaApp(tk.Tk):
    """Janela principal da aplicacao de caixa."""

    def __init__(self):
        """Configura a janela, inicializa o estado e monta a interface."""
        super().__init__()
        self.title("Caixa - Loja da Basilica")
        self.geometry("1366x768")
        self.minsize(760, 560)
        self.configure(bg=theme.TEMA_ATUAL["fundo"])

        try:
            db.inicializar()
        except Exception as error:
            self.withdraw()
            messagebox.showerror(
                "PDV não iniciado",
                "O banco local não pôde ser aberto com segurança. Nenhum dado foi alterado.\n\n"
                f"Detalhe: {error}\n\n"
                "Feche outras instâncias. Se o banco ainda não estiver no schema v2, execute o reset "
                "orientado antes da primeira operação.",
                parent=self,
            )
            tk.Tk.destroy(self)
            raise StartupError(str(error)) from error
        configure_styles(self, obter_nome_tema_atual())

        self._data_hoje = datetime.now().strftime("%d/%m/%Y")
        self._periodo_id = 0
        self._periodo_seq = 1
        self._num_venda = 1
        self._sale_uuid = str(uuid.uuid4())
        self._carrinho: list[dict] = []
        self._pagamento: str | None = None
        self._pagamento_detalhe = ""
        self._valor_recebido: float | None = None
        self._troco: float | None = None
        self._pagamentos_estruturados: list[dict] = []
        self._destinos_disponiveis: dict[str, int] = {}
        self._vendas_dia = 0
        self._total_dia = 0.0
        self._correcoes_periodo = 0
        self._resultados_busca: list = []
        self._feedback_apos_venda: str | None = None
        self._feedback_after_id: str | None = None
        self._focus_after_id: str | None = None
        self._manter_foco_after_id: str | None = None
        self._clock_after_id: str | None = None
        self._atualizando_responsavel = False
        self._layout_compacto = False
        self._closed = False
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="caixa-remote")
        self._background_results: queue.Queue = queue.Queue()
        self._background_after_id: str | None = None
        self._search_debounce_id: str | None = None
        self._search_generation = 0
        self._search_inflight: dict[int, str] = {}
        self._search_result_term = ""
        self._search_enter_generation: int | None = None
        self._sync_after_id: str | None = None

        self._frame_sugestoes: tk.Frame | None = None
        self._lst_sugestoes: tk.Listbox | None = None
        self._historico_tree: ttk.Treeview | None = None
        self._right_canvas: tk.Canvas | None = None
        self._right_window: int | None = None
        self._compacto_altura = False

        self._build_ui()
        self._background_after_id = self.after(20, self._drain_background)
        self._notebook.bind("<<NotebookTabChanged>>", self._on_main_tab_changed, add="+")
        if remote_mode():
            self._submit_background(
                lambda: db.contexto_inicial_venda_no_caixa(self._data_hoje),
                self._complete_initial_context,
            )
        else:
            self._abrir_periodo_para_data(self._data_hoje)
        self._atualizar_relogio()
        self._atualizar_status_fluxo()
        self._sync_after_id = self.after(3000, self._sincronizar_pendencias)

    def _sincronizar_pendencias(self):
        """Tenta enviar vendas offline sem interromper o atendimento."""
        self._sync_after_id = None
        if not self._closed:
            self._submit_background(sync_pending_sales, self._complete_pending_sync)

    def _complete_pending_sync(self, _result, _error=None) -> None:
        if not self._closed:
            self._sync_after_id = self.after(10000, self._sincronizar_pendencias)

    def _submit_background(self, work, done) -> None:
        """Run remote I/O and return its result through the Tkinter event loop."""
        future = self._executor.submit(work)

        def enqueue(completed):
            try:
                self._background_results.put((done, completed.result(), None))
            except Exception as error:
                self._background_results.put((done, None, error))

        future.add_done_callback(enqueue)

    def _drain_background(self) -> None:
        """Apply worker results only from the Tkinter thread."""
        self._background_after_id = None
        while not self._closed:
            try:
                callback, result, error = self._background_results.get_nowait()
            except queue.Empty:
                break
            callback(result, error)
        if not self._closed:
            self._background_after_id = self.after(20, self._drain_background)

    # ------------------------------------------------------------------
    # Construcao da interface
    # ------------------------------------------------------------------
    def _build_ui(self):
        """Monta a estrutura base da janela e conecta os paineis principais."""
        self._build_topbar()
        configure_styles(self, obter_nome_tema_atual())

        self._content_wrap = tk.Frame(self, bg=theme.TEMA_ATUAL["fundo"])
        self._content_wrap.pack(fill="both", expand=True)

        self._notebook = ttk.Notebook(self._content_wrap, style="TNotebook")
        self._notebook.pack(fill="both", expand=True, padx=0, pady=(4, 0))

        self._aba_venda = tk.Frame(self._notebook, bg=theme.TEMA_ATUAL["fundo"])
        self._aba_vendas_correcoes = tk.Frame(self._notebook, bg=theme.TEMA_ATUAL["fundo"])
        self._aba_historico = self._aba_vendas_correcoes
        self._aba_estoque = tk.Frame(self._notebook, bg=theme.TEMA_ATUAL["fundo"])
        self._aba_importacao = tk.Frame(self._notebook, bg=theme.TEMA_ATUAL["fundo"])
        self._aba_relatorios = tk.Frame(self._notebook, bg=theme.TEMA_ATUAL["fundo"])
        self._aba_configuracoes = tk.Frame(self._notebook, bg=theme.TEMA_ATUAL["fundo"])

        self._notebook.add(self._aba_venda, text="Venda")
        self._notebook.add(self._aba_vendas_correcoes, text="Vendas e correções")
        self._notebook.add(self._aba_estoque, text="Estoque")
        self._notebook.add(self._aba_importacao, text="Importação")
        self._notebook.add(self._aba_relatorios, text="Relatórios")
        self._notebook.add(self._aba_configuracoes, text="Configurações")

        self._body = tk.Frame(self._aba_venda, bg=theme.TEMA_ATUAL["fundo"])
        self._body.pack(fill="both", expand=True)
        self._body.columnconfigure(0, weight=1)
        self._body.columnconfigure(1, weight=0, minsize=300)
        self._body.rowconfigure(0, weight=1)
        self._sale_content = self._body

        self._build_left(self._body)
        self._build_right(self._body)
        self._build_footer(self._aba_venda)
        if remote_mode():
            self._lazy_tab_builders = {
                str(self._aba_vendas_correcoes): self._build_vendas_correcoes_tab,
                str(self._aba_estoque): self._build_estoque_tab,
                str(self._aba_importacao): self._build_importacao_tab,
                str(self._aba_relatorios): self._build_relatorios_tab,
                str(self._aba_configuracoes): self._build_configuracoes_tab,
            }
            for tab in self._lazy_tab_builders:
                frame = self.nametowidget(tab)
                tk.Label(
                    frame,
                    text="Carregando ao abrir esta aba…",
                    bg=theme.TEMA_ATUAL["fundo"],
                    fg=theme.TEMA_ATUAL["text_muted"],
                    font=("Segoe UI", 11),
                ).pack(pady=40)
        else:
            self._build_vendas_correcoes_tab()
            self._build_estoque_tab()
            self._build_importacao_tab()
            self._build_relatorios_tab()
            self._build_configuracoes_tab()
        self._registrar_atalhos_operacionais()
        self.bind("<Configure>", self._ajustar_layout_responsivo)

    def _on_main_tab_changed(self, _event=None) -> None:
        """Build remote tabs on demand and renew the sales list when it opens."""
        tab = self._notebook.select()
        builder = getattr(self, "_lazy_tab_builders", {}).pop(tab, None)
        if builder:
            self.after_idle(self._build_selected_tab, tab, builder)
            return
        if tab == str(getattr(self, "_aba_vendas_correcoes", "")):
            self._atualizar_historico()

    def _build_selected_tab(self, tab: str, builder) -> None:
        frame = self.nametowidget(tab)
        for child in frame.winfo_children():
            child.destroy()
        builder()

    def _build_estoque_tab(self):
        """Monta as subabas internas do modulo de estoque."""
        estoque_wrap = tk.Frame(self._aba_estoque, bg=theme.TEMA_ATUAL["fundo"])
        estoque_wrap.pack(fill="both", expand=True)
        self._estoque_notebook = ttk.Notebook(estoque_wrap, style="Inner.TNotebook")
        self._estoque_notebook.pack(fill="both", expand=True, padx=0, pady=(0, 0))

        aba_dashboard = tk.Frame(self._estoque_notebook, bg=theme.TEMA_ATUAL["fundo"])
        aba_produtos = tk.Frame(self._estoque_notebook, bg=theme.TEMA_ATUAL["fundo"])
        aba_movimentacoes = tk.Frame(self._estoque_notebook, bg=theme.TEMA_ATUAL["fundo"])
        aba_config = tk.Frame(self._estoque_notebook, bg=theme.TEMA_ATUAL["fundo"])

        self._estoque_notebook.add(aba_dashboard, text="Dashboard")
        self._estoque_notebook.add(aba_produtos, text="Produtos")
        self._estoque_notebook.add(aba_movimentacoes, text="Movimentações")
        self._estoque_notebook.add(aba_config, text="Configurações")

        dashboard_loader = None
        if remote_mode():
            dashboard_loader = lambda done: self._submit_background(
                db.snapshot_dashboard_estoque,
                lambda snapshot, error: self._complete_background_view(done, snapshot, error),
            )
        self._estoque_dashboard = DashboardEstoque(
            aba_dashboard, autoload=True, loader=dashboard_loader
        )
        self._estoque_dashboard.pack(fill="both", expand=True)
        if remote_mode():
            self._lazy_stock_builders = {
                str(aba_produtos): lambda: self._build_stock_products(aba_produtos),
                str(aba_movimentacoes): lambda: self._build_stock_movements(aba_movimentacoes),
                str(aba_config): lambda: self._build_stock_settings(aba_config),
            }
            self._estoque_notebook.bind("<<NotebookTabChanged>>", self._on_stock_tab_changed, add="+")
        else:
            self._build_stock_products(aba_produtos)
            self._build_stock_movements(aba_movimentacoes)
            self._build_stock_settings(aba_config)

    def _on_stock_tab_changed(self, _event=None) -> None:
        tab = self._estoque_notebook.select()
        builder = getattr(self, "_lazy_stock_builders", {}).pop(tab, None)
        if builder:
            self.after_idle(builder)

    def _build_stock_products(self, parent) -> None:
        panel_loader = None
        if remote_mode():
            panel_loader = lambda done: self._submit_background(
                db.snapshot_operacional_estoque,
                lambda snapshot, error: self._complete_background_view(done, snapshot, error),
            )
        self._estoque_panel = PainelEstoque(parent, autoload=True, loader=panel_loader)
        self._estoque_panel.pack(fill="both", expand=True)

    def _complete_background_view(self, done, data, error=None) -> None:
        if error:
            messagebox.showerror("Central indisponível", "Não foi possível atualizar os dados.")
            return
        done(data)

    def _complete_stock_load(self, view, snapshot, error=None) -> None:
        if error:
            messagebox.showerror("Central indisponível", "Não foi possível carregar os dados de estoque.")
            return
        view.atualizar(snapshot)

    def _build_stock_movements(self, parent) -> None:
        self._estoque_movimentacoes = MovimentacoesEstoque(parent)
        self._estoque_movimentacoes.pack(fill="both", expand=True)

    def _build_stock_settings(self, parent) -> None:
        self._estoque_configuracoes = ConfiguracoesEstoque(parent)
        self._estoque_configuracoes.pack(fill="both", expand=True)

    def _build_topbar(self):
        """Cria o cabeçalho original com título, data, horário e número da venda."""
        tema = theme.TEMA_ATUAL
        bar = tk.Frame(self, bg=tema["shell"], height=74)
        self._topbar = bar
        bar.pack(fill="x")
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg=tema["shell"])
        self._topbar_left = left
        left.pack(side="left", padx=18, pady=12)
        self._lbl_titulo = tk.Label(left, text="Loja da Basílica", bg=tema["shell"], fg=tema["shell_text"], font=("Segoe UI", 16, "bold"))
        self._lbl_titulo.pack(anchor="w")
        self._lbl_subtitulo = tk.Label(
            left,
            text="Caixa rápido para a operação diária da loja",
            bg=tema["shell"],
            fg=tema["shell_muted"],
            font=("Segoe UI", 10),
        )
        self._lbl_subtitulo.pack(anchor="w", pady=(2, 0))

        right = tk.Frame(bar, bg=tema["shell"])
        self._topbar_right = right
        right.pack(side="right", padx=18, pady=12)
        self._lbl_relogio = tk.Label(right, text="--:--", bg=tema["shell"], fg=tema["shell_text"], font=("Segoe UI", 11, "bold"))
        self._lbl_relogio.pack(anchor="e")
        self._lbl_data = tk.Label(right, text=self._data_hoje, bg=tema["shell"], fg=tema["shell_muted"], font=("Segoe UI", 9))
        self._lbl_data.pack(anchor="e")
        self._lbl_venda_num = tk.Label(
            right,
            text="",
            bg=tema["gold"],
            fg=tema["shell"],
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=5,
        )
        self._lbl_venda_num.pack(anchor="e", pady=(6, 0))
        self._atualizar_badge_venda()

        self._topbar_gold_line = tk.Frame(self, bg="#C9972C", height=3)
        self._topbar_gold_line.pack(fill="x")

    def _tab_style_name(self, label: str) -> str:
        return f"{label}.TNotebook"

    def _build_left(self, parent):
        """Cria a coluna principal: busca de produtos e carrinho da venda."""
        left = tk.Frame(parent, bg=theme.BRANCO)
        self._left_panel = left
        left.grid(row=0, column=0, sticky="nsew")

        pad = tk.Frame(left, bg=theme.BRANCO)
        self._sale_pad = pad
        pad.pack(fill="both", expand=True, padx=18, pady=16)

        search_card = Card(pad, padding=16)
        self._search_card = search_card
        search_card.pack(fill="x", pady=(0, 12))

        search_hdr = tk.Frame(search_card, bg=theme.BRANCO)
        search_hdr.pack(fill="x")
        tk.Label(
            search_hdr,
            text="Escaneie o código ou busque pelo nome",
            bg=theme.BRANCO,
            fg=theme.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        tk.Label(
            search_hdr,
            text="[F2]",
            bg=theme.FUNDO2,
            fg=theme.MUTED,
            font=("Segoe UI", 8, "bold"),
            padx=4,
            pady=1,
        ).pack(side="right")

        self._var_busca = tk.StringVar()
        search_panel = tk.Frame(search_card, bg=theme.BRANCO, pady=16)
        self._search_panel = search_panel
        search_panel.pack(fill="x")
        search = SearchInput(
            search_panel,
            self._var_busca,
            "Buscar por nome, código ou código de barras... [F2]",
        )
        search.pack(fill="x")
        self._entry_busca = search.entry
        self._entry_busca.bind("<Return>", self._on_enter_busca)
        self._entry_busca.bind("<Down>", self._focar_sugestao)
        self._entry_busca.bind("<Escape>", lambda _: self._limpar_busca())
        self._focus_after_id = self.after(100, self._focar_busca_inicial)

        self._frame_sugestoes = tk.Frame(search_card, bg=theme.BRANCO)
        self._lst_sugestoes = tk.Listbox(
            self._frame_sugestoes,
            font=("Segoe UI", 10),
            bg=theme.BRANCO,
            fg=theme.TEXTO,
            selectbackground=theme.VERDE_CLAR,
            selectforeground=theme.VERDE_ESC,
            relief="flat",
            activestyle="none",
            highlightthickness=0,
        )
        self._lst_sugestoes.pack(fill="both", expand=True)
        self._lst_sugestoes.bind("<<ListboxSelect>>", self._on_selecionar_sugestao)
        self._lst_sugestoes.bind("<Return>", self._on_selecionar_sugestao)
        self._lst_sugestoes.bind("<Up>", self._voltar_busca)
        self._var_busca.trace_add("write", self._on_busca)

        cart_hdr = tk.Frame(pad, bg=theme.FUNDO2, padx=10, pady=8)
        cart_hdr.pack(fill="x", pady=(0, 4))
        tk.Label(cart_hdr, text="ITEM", bg=theme.FUNDO2, fg=theme.MUTED, font=("Segoe UI", 8, "bold"), anchor="w").pack(side="left", expand=True, fill="x")
        
        right_hdr = tk.Frame(cart_hdr, bg=theme.FUNDO2)
        right_hdr.pack(side="right")
        tk.Label(right_hdr, text="QTD", bg=theme.FUNDO2, fg=theme.MUTED, font=("Segoe UI", 8, "bold"), width=8, anchor="center").pack(side="left")
        tk.Label(right_hdr, text="TOTAL", bg=theme.FUNDO2, fg=theme.MUTED, font=("Segoe UI", 8, "bold"), width=11, anchor="e").pack(side="left", padx=(10, 0))
        tk.Label(right_hdr, text="", bg=theme.FUNDO2, width=8).pack(side="left", padx=(0, 10))

        # Mantidos para a lógica existente, sem criar uma segunda faixa visual.
        self._lbl_resumo_carrinho = tk.Label(pad, text="Carrinho vazio")
        self._btn_limpar = tk.Button(pad, text="Limpar", command=self._limpar_carrinho)

        self._frame_vazio = EmptyState(pad, "Carrinho vazio", "Adicione produtos para liberar a seleção de pagamento e a finalização.")
        self._frame_vazio.pack(fill="both", expand=True)

        self._frame_carrinho = tk.Frame(pad, bg=theme.BRANCO)
        self._canvas_cart = tk.Canvas(self._frame_carrinho, bg=theme.BRANCO, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self._frame_carrinho, orient="vertical", command=self._canvas_cart.yview)
        self._canvas_cart.configure(yscrollcommand=scrollbar.set)
        self._canvas_cart.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._inner_cart = tk.Frame(self._canvas_cart, bg=theme.BRANCO)
        self._cart_rows: dict[int, CartRowWidgets] = {}
        self._canvas_window = self._canvas_cart.create_window((0, 0), window=self._inner_cart, anchor="nw")
        self._inner_cart.bind("<Configure>", self._ajustar_scroll_carrinho)
        self._canvas_cart.bind("<Configure>", self._ajustar_largura_carrinho)
        bind_mousewheel_tree(self._inner_cart, self._canvas_cart)

        dash = tk.Frame(pad, bg=theme.BRANCO)
        self._sale_dash = dash
        dash.pack(fill="x", side="bottom", pady=(12, 0))
        for i in range(3):
            dash.columnconfigure(i, weight=1, uniform="dash")
        
        self._kpi_hoje = KpiCard(dash, label="Hoje", value="R$ 0,00", tone="default")
        self._kpi_hoje.grid(row=0, column=0, padx=(0, 4), sticky="nsew")
        self._kpi_vendas = KpiCard(dash, label="Vendas", value="0", tone="default")
        self._kpi_vendas.grid(row=0, column=1, padx=4, sticky="nsew")
        self._kpi_correcoes = KpiCard(dash, label="Correções", value="0", tone="default")
        self._kpi_correcoes.grid(row=0, column=2, padx=(4, 0), sticky="nsew")

        # Atalhos discretos no rodape do painel esquerdo
        bar_atalhos = tk.Frame(pad, bg=theme.FUNDO2, padx=8, pady=4)
        self._shortcut_bar = bar_atalhos
        bar_atalhos.pack(fill="x", side="bottom", pady=(8, 0))
        tk.Label(
            bar_atalhos,
            text="Atalhos: [F2] Buscar | [Enter] Adicionar | [F4] Pagamento | [F8] Finalizar | [Esc] Limpar busca",
            bg=theme.FUNDO2,
            fg=theme.MUTED,
            font=("Segoe UI", 8),
        ).pack(anchor="w")

    def _build_right(self, parent):
        """Cria a coluna lateral com status, totais e pagamento."""
        self._right_separator = tk.Frame(parent, bg=theme.BORDA, width=1)
        self._right_separator.grid(row=0, column=0, sticky="nse")

        right = tk.Frame(parent, bg=theme.FUNDO, width=300)
        self._right_panel = right
        right.grid(row=0, column=1, sticky="nsew")
        right.pack_propagate(False)

        self._right_action_bar = tk.Frame(right, bg=theme.FUNDO, padx=10, pady=10)
        self._right_action_bar.pack(side="bottom", fill="x")

        self._btn_finalizar = action_button(
            self._right_action_bar,
            text="Finalizar venda  [F8]",
            command=self._finalizar_venda,
            variant="primary",
            font=("Segoe UI", 12, "bold"),
            pady=12,
            state="disabled",
            takefocus=True,
        )
        self._btn_finalizar.pack(fill="x")

        self._right_canvas = tk.Canvas(right, bg=theme.FUNDO, highlightthickness=0)
        self._right_scroll = tk.Scrollbar(right, orient="vertical", command=self._right_canvas.yview, width=16, troughcolor=theme.FUNDO2, bg=theme.BORDA, activebackground=theme.MUTED)
        self._right_canvas.configure(yscrollcommand=self._right_scroll.set)
        self._right_canvas.pack(side="left", fill="both", expand=True)
        self._right_scroll.pack(side="right", fill="y")

        pad = tk.Frame(self._right_canvas, bg=theme.FUNDO)
        self._right_pad = pad
        self._right_window = self._right_canvas.create_window((0, 0), window=pad, anchor="nw")
        pad.bind("<Configure>", self._ajustar_scroll_lateral)
        self._right_canvas.bind("<Configure>", self._ajustar_largura_lateral)
        self._right_canvas.bind("<MouseWheel>", self._rolar_painel_lateral)

        self._card_status = Card(pad, padding=10)
        self._card_status.pack(fill="x", pady=(0, 7))
        self._lbl_status_title = tk.Label(self._card_status, text="Status da venda", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 11, "bold"))
        self._lbl_status_title.pack(anchor="w")
        self._lbl_status_fluxo = tk.Label(self._card_status, text="Período aberto · operação local.", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9), wraplength=270, justify="left")
        self._lbl_status_fluxo.pack(anchor="w", pady=(1, 5))
        
        self._status_pills = tk.Frame(self._card_status, bg=theme.BRANCO)
        self._status_pills.pack(fill="x")
        self._lbl_status_aux = tk.Label(self._card_status, text="") # Dummy for logic

        self._var_responsavel = tk.StringVar()
        self._var_responsavel.trace_add("write", self._salvar_responsavel_periodo)
        tk.Label(
            self._card_status,
            text="Operador",
            bg=theme.BRANCO,
            fg=theme.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(5, 2))
        self._entry_responsavel = tk.Entry(
            self._card_status,
            textvariable=self._var_responsavel,
            font=("Segoe UI", 10),
            relief="solid",
            bd=1,
        )
        self._entry_responsavel.pack(fill="x", ipady=3)

        self._card_pagamento = Card(pad, padding=16)
        self._card_pagamento.pack(fill="x", pady=(0, 12))
        tk.Label(self._card_pagamento, text="Pagamento", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(self._card_pagamento, text="Escolha a forma para liberar finalização.", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 12))

        grid_pgto = tk.Frame(self._card_pagamento, bg=theme.BRANCO)
        self._grid_pgto = grid_pgto
        grid_pgto.pack(fill="x")
        for i in range(2):
            grid_pgto.columnconfigure(i, weight=1, uniform="pgto")
        self._btns_pgto = {}
        pgto_info = [("Debito", "Débito  [F3]", 0, 0), ("Credito", "Crédito  [F4]", 0, 1), ("Pix", "Pix  [F5]", 1, 0), ("Dinheiro", "Dinheiro  [F6]", 1, 1), ("Mais de uma forma", "Mais de uma forma", 2, 0)]
        for nome, texto, row, col in pgto_info:
            btn = action_button(
                grid_pgto,
                text=texto,
                font=("Segoe UI", 10, "bold"),
                bg=theme.FUNDO2,
                fg=theme.TEXTO,
                padx=12,
                pady=10,
                takefocus=True,
                command=lambda n=nome: self._selecionar_pgto(n),
            )
            btn.configure(activebackground=theme.VERDE_CLAR, activeforeground=theme.VERDE_ESC)
            btn.grid(row=row, column=col, columnspan=2 if nome == "Mais de uma forma" else 1, padx=4, pady=4, sticky="nsew")
            self._btns_pgto[nome] = btn

        destino_linha = tk.Frame(self._card_pagamento, bg=theme.BRANCO)
        destino_linha.pack(fill="x", pady=(8, 0))
        tk.Label(destino_linha, text="Destino financeiro", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._var_destino_financeiro = tk.StringVar()
        self._destino_box = ttk.Combobox(destino_linha, textvariable=self._var_destino_financeiro, state="readonly")
        self._destino_box.pack(fill="x", pady=(4, 0))

        panel_totais = tk.Frame(self._card_pagamento, bg=theme.FUNDO2, padx=12, pady=12)
        panel_totais.pack(fill="x", pady=(12, 0))
        tk.Label(
            panel_totais,
            text="Total da venda",
            bg=theme.FUNDO2,
            fg=theme.MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w")
        row_total = tk.Frame(panel_totais, bg=theme.FUNDO2)
        row_total.pack(fill="x", pady=(4, 0))
        self._lbl_total = tk.Label(
            row_total,
            text="R$ 0,00",
            bg=theme.FUNDO2,
            fg=theme.VERDE_ESC,
            font=("Segoe UI", 24, "bold"),
        )
        self._lbl_total.pack(side="left")
        self._badge_pronta = StatusBadge(
            row_total,
            "Pronta para finalizar",
            bg=theme.TEMA_ATUAL["primary_soft"],
            fg=theme.TEMA_ATUAL["primary"],
        )
        self._lbl_n_itens = tk.Label(panel_totais, text="")
        self._lbl_n_unid = tk.Label(panel_totais, text="")
        self._lbl_pgto_resumo = tk.Label(
            panel_totais,
            text="",
            bg=theme.FUNDO2,
            fg=theme.TEXTO,
            font=("Segoe UI", 9, "bold"),
            justify="left",
            anchor="w",
            wraplength=250,
        )
        self._lbl_forma_pgto = tk.Label(panel_totais, text="")

        bind_mousewheel_tree(pad, self._right_canvas)

    def _build_footer(self, parent):
        """Cria o rodape com indicadores do periodo e acoes globais."""
        tk.Frame(parent, bg=theme.BORDA, height=1).pack(fill="x", side="bottom")
        footer = tk.Frame(parent, bg=theme.BRANCO, height=44)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        acoes_footer = tk.Frame(footer, bg=theme.BRANCO)
        acoes_footer.pack(side="right", padx=12, pady=6)
        action_button(
            acoes_footer,
            text="Fechar Período da Loja",
            command=self._encerrar_dia,
            variant="danger",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=5,
        ).pack(side="right")
        stats = tk.Frame(footer, bg=theme.BRANCO)
        stats.pack(side="left", fill="x", expand=True, padx=16, pady=8)
        tk.Label(stats, text="Período", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9)).pack(side="left")
        self._lbl_periodo = tk.Label(stats, text="01", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 9, "bold"))
        self._lbl_periodo.pack(side="left", padx=(4, 16))
        tk.Label(stats, text="Vendas no período", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9)).pack(side="left")
        self._lbl_vendas_dia = tk.Label(stats, text="0", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 9, "bold"))
        self._lbl_vendas_dia.pack(side="left", padx=(4, 16))
        tk.Label(stats, text="Total do período", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9)).pack(side="left")
        self._lbl_total_dia = tk.Label(stats, text="R$ 0,00", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 9, "bold"))
        self._lbl_total_dia.pack(side="left", padx=(4, 0))
    def _build_vendas_correcoes_tab(self):
        """Monta a aba de Vendas e correções (evoluída de Últimas vendas para Issue #15)."""
        self._vendas_correcoes_view = VendasCorrecoesView(
            self._aba_vendas_correcoes,
            on_sale_updated=self._apos_atualizacao_venda,
            autoload=not remote_mode(),
            loader=(
                (
                    lambda filtros, done: self._submit_background(
                        lambda: sales_runtime.consultar_vendas_correcoes(filtros),
                        lambda resultado, error: self._complete_background_view(done, resultado, error),
                    )
                )
                if remote_mode()
                else None
            ),
        )
        self._vendas_correcoes_view.pack(fill="both", expand=True)
        if remote_mode():
            self._submit_background(
                lambda: sales_runtime.consultar_vendas_correcoes(),
                lambda resultado, error: self._complete_lazy_view(self._vendas_correcoes_view, resultado, error),
            )

    def _build_history_tab(self):
        """Compatibilidade para montagem do histórico de vendas."""
        self._build_vendas_correcoes_tab()

    def _build_importacao_tab(self):
        """Monta o fluxo guiado em 4 etapas da aba de Importação (Issue #14)."""
        self._importacao_view = ImportacaoGuidedView(
            self._aba_importacao,
            on_import_complete=self._atualizar_painel_estoque,
        )
        self._importacao_view.pack(fill="both", expand=True)

    def _build_relatorios_tab(self):
        """Monta a aba de Relatórios e Fechamento com movimentação líquida (Issue #18)."""
        self._relatorios_view = RelatoriosView(
            self._aba_relatorios,
            periodo_id_provider=lambda: getattr(self, "_periodo_id", 1),
            destinos=list(getattr(self, "_initial_destinations", [])) if remote_mode() else None,
            autoload=not remote_mode(),
        )
        self._relatorios_view.pack(fill="both", expand=True)
        if remote_mode():
            self._submit_background(
                lambda: reports_runtime.obter_fechamento_financeiro(self._periodo_id),
                lambda dados, error: self._complete_lazy_view(self._relatorios_view, dados, error),
            )

    def _complete_lazy_view(self, view, data, error=None) -> None:
        if error:
            messagebox.showerror("Central indisponível", "Não foi possível carregar a aba selecionada.")
            return
        view.atualizar(data)

    def _build_configuracoes_tab(self):
        """Monta a aba de Configurações e Manutenção (Tema claro/escuro, Backup/Restauração)."""
        pad = tk.Frame(self._aba_configuracoes, bg=theme.TEMA_ATUAL["fundo"], padx=18, pady=16)
        pad.pack(fill="both", expand=True)

        PageHeader(
            pad,
            "Configurações e manutenção",
            "Gerencie preferências visuais de tema, manutenção do banco de dados e backups.",
        ).pack(fill="x", pady=(0, 16))

        grid = tk.Frame(pad, bg=theme.TEMA_ATUAL["fundo"])
        grid.pack(fill="x", expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        card_tema = Card(grid, padding=20)
        card_tema.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        SectionHeader(card_tema, "Tema", "Escolha a cor base do PDV.").pack(anchor="w", fill="x", pady=(0, 14))

        if not hasattr(self, "_var_tema_opcao"):
            self._var_tema_opcao = tk.StringVar(value=obter_nome_tema_atual())
        else:
            self._var_tema_opcao.set(obter_nome_tema_atual())

        for valor_tema, texto_tema in (("claro", "Tema Claro"), ("escuro", "Tema Escuro")):
            ativo = obter_nome_tema_atual() == valor_tema
            bg = theme.TEMA_ATUAL["primary"] if ativo else theme.TEMA_ATUAL["surface_2"]
            fg = "#FFFFFF" if ativo else theme.TEMA_ATUAL["texto"]
            btn = tk.Button(
                card_tema,
                text=texto_tema,
                command=lambda t=valor_tema: self._alternar_tema(t),
                bg=bg,
                fg=fg,
                font=("Segoe UI", 10, "bold"),
                relief="flat",
                cursor="hand2",
                padx=16,
                pady=10,
            )
            btn.pack(anchor="w", fill="x", pady=(0, 8))

        card_maint = Card(grid, padding=20)
        card_maint.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        SectionHeader(card_maint, "Backup e restauração", "Gerencie o banco de dados.").pack(anchor="w", fill="x", pady=(0, 14))

        action_button(card_maint, text="Criar backup", command=self._criar_backup, variant="primary").pack(anchor="w", fill="x", pady=(0, 8))
        action_button(card_maint, text="Restaurar backup", command=self._restaurar_backup, variant="danger").pack(anchor="w", fill="x")

        card_destinos = Card(grid, padding=20)
        card_destinos.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(16, 0))
        SectionHeader(card_destinos, "Destinos financeiros", "Cadastre onde cada forma de pagamento é recebida.").pack(anchor="w", fill="x", pady=(0, 12))
        corpo_destinos = tk.Frame(card_destinos, bg=theme.TEMA_ATUAL["surface"])
        corpo_destinos.pack(fill="x")
        tema = theme.TEMA_ATUAL
        corpo_destinos.columnconfigure(0, weight=1)
        corpo_destinos.columnconfigure(1, weight=1)
        self._lista_destinos = tk.Listbox(
            corpo_destinos,
            height=6,
            font=("Segoe UI", 10),
            bg=tema["surface_2"],
            fg=tema["text"],
            selectbackground=tema["primary_soft"],
            selectforeground=tema["text"],
            highlightbackground=tema["border_soft"],
            highlightcolor=tema["focus_ring"],
            relief="flat",
        )
        self._lista_destinos.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._lista_destinos.bind("<<ListboxSelect>>", self._carregar_destino_selecionado)
        formulario = tk.Frame(corpo_destinos, bg=theme.TEMA_ATUAL["surface"])
        formulario.grid(row=0, column=1, sticky="nsew")
        self._var_nome_destino = tk.StringVar()
        StyledEntry(formulario, textvariable=self._var_nome_destino, bg=tema["surface_2"], fg=tema["text"]).pack(fill="x", ipady=6, pady=(0, 6))
        self._vars_formas_destino = {forma: tk.BooleanVar() for forma in ("Dinheiro", "Pix", "Debito", "Credito")}
        formas_linha = tk.Frame(formulario, bg=theme.TEMA_ATUAL["surface"])
        formas_linha.pack(fill="x", pady=(0, 8))
        for forma, var in self._vars_formas_destino.items():
            tk.Checkbutton(
                formas_linha,
                text=forma,
                variable=var,
                bg=tema["surface"],
                fg=tema["text"],
                selectcolor=tema["surface_2"],
                activebackground=tema["surface"],
                activeforeground=tema["text"],
            ).pack(side="left", padx=(0, 8))
        acoes_destinos = tk.Frame(formulario, bg=tema["surface"])
        acoes_destinos.pack(fill="x")
        botoes_destinos = [
            action_button(acoes_destinos, text="Adicionar destino", command=self._adicionar_destino, variant="primary"),
            action_button(acoes_destinos, text="Atualizar selecionado", command=self._atualizar_destino, variant="secondary"),
            action_button(acoes_destinos, text="Tornar padrão", command=self._definir_destino_padrao, variant="secondary"),
            action_button(acoes_destinos, text="Inativar selecionado", command=self._inativar_destino, variant="danger"),
        ]
        for indice, botao in enumerate(botoes_destinos):
            acoes_destinos.columnconfigure(indice, weight=1)
            botao.grid(row=0, column=indice, sticky="ew", padx=(0 if indice == 0 else 6, 0))

        def ajustar_destinos(event):
            estreito = event.width < 760
            self._lista_destinos.grid_configure(
                row=0,
                column=0,
                columnspan=2 if estreito else 1,
                padx=0 if estreito else (0, 12),
                pady=(0, 10) if estreito else 0,
            )
            formulario.grid_configure(row=1 if estreito else 0, column=0 if estreito else 1, columnspan=2 if estreito else 1)

        corpo_destinos.bind("<Configure>", ajustar_destinos)

        def ajustar_configuracoes(event):
            estreito = event.width < 760
            card_tema.grid_configure(row=0, column=0, columnspan=2 if estreito else 1, padx=0 if estreito else (0, 8))
            card_maint.grid_configure(
                row=1 if estreito else 0,
                column=0 if estreito else 1,
                columnspan=2 if estreito else 1,
                padx=0 if estreito else (8, 0),
                pady=(10, 0) if estreito else 0,
            )
            card_destinos.grid_configure(row=2 if estreito else 1, pady=(10 if estreito else 16, 0))

        grid.bind("<Configure>", ajustar_configuracoes)
        self._recarregar_destinos()

    def _recarregar_destinos(self):
        self._destinos_config = db.listar_destinos_financeiros(incluir_inativos=True)
        self._lista_destinos.delete(0, "end")
        for destino in self._destinos_config:
            status = "ativo" if destino["ativo"] else "inativo"
            self._lista_destinos.insert("end", f"{destino['nome']} — {destino['formas']} ({status})")

    def _adicionar_destino(self):
        formas = [forma for forma, var in self._vars_formas_destino.items() if var.get()]
        try:
            db.criar_destino_financeiro(self._var_nome_destino.get(), formas)
            self._var_nome_destino.set("")
            for var in self._vars_formas_destino.values():
                var.set(False)
            self._recarregar_destinos()
        except Exception as erro:
            messagebox.showerror("Destino financeiro", str(erro))

    def _carregar_destino_selecionado(self, _event=None):
        selecao = self._lista_destinos.curselection()
        if not selecao:
            return
        destino = self._destinos_config[selecao[0]]
        self._var_nome_destino.set(destino["nome"])
        formas = set(destino["formas"].split(","))
        for forma, var in self._vars_formas_destino.items():
            var.set(forma in formas)

    def _inativar_destino(self):
        selecao = self._lista_destinos.curselection()
        if not selecao:
            return
        db.inativar_destino_financeiro(int(self._destinos_config[selecao[0]]["id"]))
        self._recarregar_destinos()

    def _atualizar_destino(self):
        selecao = self._lista_destinos.curselection()
        if not selecao:
            return
        formas = [forma for forma, var in self._vars_formas_destino.items() if var.get()]
        try:
            db.atualizar_destino_financeiro(
                int(self._destinos_config[selecao[0]]["id"]), self._var_nome_destino.get(), formas
            )
            self._recarregar_destinos()
        except Exception as erro:
            messagebox.showerror("Destino financeiro", str(erro))

    def _definir_destino_padrao(self):
        selecao = self._lista_destinos.curselection()
        if not selecao:
            return
        formas = [forma for forma, var in self._vars_formas_destino.items() if var.get()]
        try:
            db.definir_destino_padrao(int(self._destinos_config[selecao[0]]["id"]), formas)
            self._recarregar_destinos()
        except Exception as erro:
            messagebox.showerror("Destino financeiro", str(erro))

    def _alternar_tema(self, nome_tema: str):
        """Alterna dinamicamente entre tema claro e escuro."""
        tema_anterior = dict(theme.TEMA_ATUAL)
        definir_tema_atual(nome_tema)
        configure_styles(self, nome_tema)
        self._aplicar_tema_na_casca(nome_tema)
        apply_theme_to_widget_tree(self, tema_anterior)
        self._reconstruir_aba_configuracoes()

    def _reconstruir_aba_configuracoes(self):
        """Recontrói os widgets da aba de configurações para atualizar o tema."""
        if hasattr(self, "_aba_configuracoes"):
            for child in self._aba_configuracoes.winfo_children():
                child.destroy()
            self._build_configuracoes_tab()

    def _aplicar_tema_na_casca(self, nome_tema: str):
        """Aplica as cores do tema ativo nos elementos da casca principal."""
        bg = theme.TEMA_ATUAL["fundo"]
        bg_surface = theme.TEMA_ATUAL["surface"]
        fg_texto = theme.TEMA_ATUAL["texto"]
        fg_muted = theme.TEMA_ATUAL["texto_suave"]

        self.configure(bg=bg)
        if hasattr(self, "_content_wrap"):
            self._content_wrap.configure(bg=bg)
        for aba in (
            getattr(self, "_aba_venda", None),
            getattr(self, "_aba_vendas_correcoes", None),
            getattr(self, "_aba_estoque", None),
            getattr(self, "_aba_importacao", None),
            getattr(self, "_aba_relatorios", None),
            getattr(self, "_aba_configuracoes", None),
        ):
            if aba:
                aba.configure(bg=bg)

        if hasattr(self, "_body"):
            self._body.configure(bg=bg)
        if hasattr(self, "_left_panel"):
            self._left_panel.configure(bg=bg_surface)
        if hasattr(self, "_right_panel"):
            self._right_panel.configure(bg=bg)

    def _criar_linha_info(self, parent, label, attr_name):
        """Adiciona uma linha simples de label/valor em cards de resumo."""
        row = tk.Frame(parent, bg=theme.BRANCO)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9)).pack(side="left")
        value = tk.Label(row, text="0", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 9, "bold"))
        value.pack(side="right")
        setattr(self, attr_name, value)

    # ------------------------------------------------------------------
    # Busca de produtos
    # ------------------------------------------------------------------
    def _on_busca(self, *_):
        """Agenda Busca de produto sem bloquear a thread Tkinter."""
        termo = self._var_busca.get().strip()
        if self._search_debounce_id:
            self.after_cancel(self._search_debounce_id)
            self._search_debounce_id = None
        self._search_generation += 1
        generation = self._search_generation
        if not termo or termo == PLACEHOLDER_BUSCA:
            self._esconder_sugestoes()
            return
        if hasattr(self, "_lbl_status_fluxo"):
            self._lbl_status_fluxo.config(text="Buscando produto…")
        self._search_debounce_id = self.after(180, self._start_product_search, termo, generation, False)

    def _start_product_search(self, termo: str, generation: int, enter: bool) -> None:
        """Start at most one remote query for a term generation."""
        self._search_debounce_id = None
        if generation in self._search_inflight:
            if enter:
                self._search_enter_generation = generation
            return
        self._search_inflight[generation] = termo
        if enter:
            self._search_enter_generation = generation
        search = getattr(self, "_search", db.buscar_produto)
        self._submit_background(
            lambda: list(search(termo)),
            lambda results, error: self._complete_product_search(generation, termo, results, error),
        )

    def _complete_product_search(self, generation: int, termo: str, resultados, error=None) -> None:
        """Discard stale results and expose only the current Busca de produto."""
        self._search_inflight.pop(generation, None)
        if self._closed or generation != self._search_generation or self._var_busca.get().strip() != termo:
            return
        if error:
            self._esconder_sugestoes()
            if hasattr(self, "_lbl_status_fluxo"):
                self._lbl_status_fluxo.config(text="Central indisponível. Verifique a conexão.")
            return
        self._search_result_term = termo
        if hasattr(self, "_atualizar_status_fluxo"):
            self._atualizar_status_fluxo()
        enter = self._search_enter_generation == generation
        self._search_enter_generation = None
        if enter and self._add_best_product_match(termo, resultados):
            return
        self._render_product_results(resultados)

    def _render_product_results(self, resultados) -> None:
        """Render current suggestions after remote work completes."""
        if not resultados or not self._lst_sugestoes or not self._frame_sugestoes:
            self._esconder_sugestoes()
            return

        self._resultados_busca = list(resultados)
        self._lst_sugestoes.delete(0, "end")
        for produto in self._resultados_busca:
            descricao = f"{produto['nome']}  |  Cod. {produto['codigo']}  |  {moeda(produto['preco'])}"
            self._lst_sugestoes.insert("end", descricao)
        if not self._frame_sugestoes.winfo_ismapped():
            self._frame_sugestoes.pack(fill="x", padx=12, pady=(0, 10))
        self._lst_sugestoes.configure(height=min(len(self._resultados_busca), 5))
        if self._manter_foco_after_id:
            self.after_cancel(self._manter_foco_after_id)
        self._manter_foco_after_id = self.after_idle(self._manter_foco_busca)

    def _manter_foco_busca(self):
        """Mantem o cursor no campo de busca apos atualizar a lista."""
        self._manter_foco_after_id = None
        if self._entry_busca.winfo_exists():
            self._entry_busca.focus_set()
            self._entry_busca.icursor("end")

    def _limpar_busca(self):
        """Limpa o termo de busca e esconde sugestoes."""
        self._var_busca.set("")
        self._esconder_sugestoes()
        if hasattr(self, "_entry_busca") and self._entry_busca.winfo_exists():
            self._entry_busca.focus()

    def _focar_campo_busca(self, _=None):
        """Foca no campo de busca de produtos."""
        if hasattr(self, "_entry_busca") and self._entry_busca.winfo_exists():
            self._notebook.select(self._aba_venda)
            self._entry_busca.focus()
            self._entry_busca.icursor("end")

    def _registrar_atalhos_operacionais(self):
        """Liga o caminho comum da Venda no caixa a atalhos globais."""
        self.bind_all("<F2>", self._focar_campo_busca)
        self.bind_all("<F3>", lambda _: self._selecionar_pgto_atalho("Debito"))
        self.bind_all("<F4>", lambda _: self._selecionar_pgto_atalho("Credito"))
        self.bind_all("<F5>", lambda _: self._selecionar_pgto_atalho("Pix"))
        self.bind_all("<F6>", lambda _: self._selecionar_pgto_atalho("Dinheiro"))
        self.bind_all("<F8>", self._finalizar_venda_por_atalho)

    def _selecionar_pgto_atalho(self, pgto: str):
        self._notebook.select(self._aba_venda)
        if not self._carrinho:
            self._focar_campo_busca()
            return "break"
        self._selecionar_pgto(pgto)
        return "break"

    def _focar_pagamento(self, _=None):
        """Leva o foco ao primeiro pagamento quando o carrinho esta pronto."""
        self._notebook.select(self._aba_venda)
        if not self._carrinho:
            self._focar_campo_busca()
            return "break"
        selecionado = self._pagamento if self._pagamento in self._btns_pgto else "Debito"
        self._btns_pgto[selecionado].focus_set()
        return "break"

    def _finalizar_venda_por_atalho(self, _=None):
        """Finaliza via F8 ou direciona o foco para a etapa ainda pendente."""
        if not self._carrinho:
            self._focar_campo_busca()
        elif not self._pagamento:
            self._focar_pagamento()
        else:
            self._finalizar_venda()
        return "break"

    def _on_enter_busca(self, _=None):
        """Reuse a valid result or finish one asynchronous query on Enter."""
        termo = self._var_busca.get().strip()
        if not termo or termo == PLACEHOLDER_BUSCA:
            return
        if self._search_result_term == termo and self._add_best_product_match(termo, self._resultados_busca):
            return "break"
        if self._search_debounce_id:
            self.after_cancel(self._search_debounce_id)
            self._search_debounce_id = None
        generation = self._search_generation
        self._start_product_search(termo, generation, True)
        return "break"

    def _add_best_product_match(self, termo: str, resultados) -> bool:
        """Add an exact code match or the sole valid result."""
        for product in resultados or []:
            if product["codigo"] == termo or product.get("cod_barras") == termo:
                self._adicionar_produto(dict(product))
                return True
        if len(resultados or []) == 1:
            self._adicionar_produto(dict(resultados[0]))
            return True
        return False

    def _focar_sugestao(self, _=None):
        """Move o foco do teclado para a primeira sugestao encontrada."""
        if self._lst_sugestoes and self._lst_sugestoes.size() > 0:
            self._lst_sugestoes.focus()
            self._lst_sugestoes.selection_clear(0, "end")
            self._lst_sugestoes.selection_set(0)

    def _voltar_busca(self, _=None):
        """Retorna o foco ao campo de busca ao sair da lista de sugestoes."""
        if self._lst_sugestoes and self._lst_sugestoes.curselection():
            if self._lst_sugestoes.curselection()[0] == 0:
                self._entry_busca.focus()
                return "break"
        self._entry_busca.focus()

    def _on_selecionar_sugestao(self, _=None):
        """Adiciona ao carrinho o produto selecionado na lista."""
        if not self._lst_sugestoes:
            return
        selecao = self._lst_sugestoes.curselection()
        if not selecao:
            return
        produto = self._resultados_busca[selecao[0]]
        self._adicionar_produto(dict(produto))

    def _esconder_sugestoes(self):
        """Oculta a lista de sugestoes e limpa o cache da busca."""
        if self._frame_sugestoes and self._frame_sugestoes.winfo_exists():
            self._frame_sugestoes.pack_forget()
        self._resultados_busca = []

    # ------------------------------------------------------------------
    # Carrinho e totais
    # ------------------------------------------------------------------
    def _adicionar_produto(self, produto: dict):
        """Inclui o produto no carrinho ou incrementa sua quantidade."""
        self._esconder_sugestoes()
        self._var_busca.set("")
        self._entry_busca.focus()

        produto_id = produto["id"]
        estoque = produto.get("estoque", 99)
        for item in self._carrinho:
            if item["produto_id"] == produto_id:
                item["quantidade"] += 1
                item["estoque"] = estoque
                self._renderizar_carrinho()
                self._atualizar_totais()
                return

        self._carrinho.append(
            {
                "produto_id": produto_id,
                "codigo": produto["codigo"],
                "nome": produto["nome"],
                "preco_unit": produto["preco"],
                "quantidade": 1,
                "estoque": estoque,
            }
        )
        self._renderizar_carrinho()
        self._atualizar_totais()

    def _alterar_qty(self, produto_id: int, delta: int):
        """Ajusta a quantidade de um item ja presente no carrinho."""
        for item in self._carrinho:
            if item["produto_id"] == produto_id:
                item["quantidade"] += delta
                if item["quantidade"] <= 0:
                    self._carrinho = [registro for registro in self._carrinho if registro["produto_id"] != produto_id]
                break
        self._renderizar_carrinho()
        self._atualizar_totais()

    def _remover_item(self, produto_id: int):
        """Remove um produto especifico do carrinho."""
        self._carrinho = [registro for registro in self._carrinho if registro["produto_id"] != produto_id]
        self._renderizar_carrinho()
        self._atualizar_totais()

    def _limpar_carrinho(self):
        """Zera a venda em andamento e limpa o pagamento selecionado."""
        self._carrinho.clear()
        self._limpar_pagamento()
        self._renderizar_carrinho()
        self._atualizar_totais()
        self._resetar_btns_pgto()

    def _renderizar_carrinho(self):
        """Atualiza a lista visual e reconstrói somente quando sua estrutura muda."""
        if not self._carrinho:
            for widget in self._inner_cart.winfo_children():
                widget.destroy()
            self._cart_rows.clear()
            self._frame_vazio.pack(fill="both", expand=True)
            self._frame_carrinho.pack_forget()
            if hasattr(self, '_lbl_resumo_carrinho'):
                self._lbl_resumo_carrinho.config(text="Carrinho vazio")
            return

        self._frame_vazio.pack_forget()
        self._frame_carrinho.pack(fill="both", expand=True)
        total_itens = sum(item["quantidade"] for item in self._carrinho)
        if hasattr(self, '_lbl_resumo_carrinho'):
            self._lbl_resumo_carrinho.config(text=f"{len(self._carrinho)} itens | {total_itens} unidades")

        ids_atuais = tuple(self._cart_rows)
        ids_desejados = tuple(item["produto_id"] for item in self._carrinho)
        if ids_atuais == ids_desejados:
            for item in self._carrinho:
                self._atualizar_linha_carrinho(item, self._cart_rows[item["produto_id"]])
            return

        for widget in self._inner_cart.winfo_children():
            widget.destroy()
        self._cart_rows.clear()

        for i, item in enumerate(self._carrinho):
            produto_id = item["produto_id"]

            row = tk.Frame(self._inner_cart, bg=theme.BRANCO, padx=10, pady=8)
            row.pack(fill="x")

            info = tk.Frame(row, bg=theme.BRANCO)
            info.pack(side="left", fill="x", expand=True)
            nome_label = tk.Label(info, bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 10, "bold"), wraplength=380, justify="left")
            nome_label.pack(anchor="w")

            codigo_label = tk.Label(
                info,
                bg=theme.BRANCO,
                fg=theme.MUTED,
                font=("Segoe UI", 9),
            )
            codigo_label.pack(anchor="w", pady=(2, 0))

            alerta_label = StatusBadge(
                info,
                "",
                bg=theme.TEMA_ATUAL["warning_soft"],
                fg=theme.TEMA_ATUAL["warning"],
            )

            controls = tk.Frame(row, bg=theme.BRANCO)
            controls.pack(side="right")

            qty_frame = tk.Frame(controls, bg=theme.BRANCO)
            qty_frame.pack(side="left")
            tk.Button(qty_frame, text="-", font=("Segoe UI", 10, "bold"), bg=theme.FUNDO2, fg=theme.TEXTO, relief="flat", cursor="hand2", width=2, command=lambda p=produto_id: self._alterar_qty(p, -1)).pack(side="left")
            quantidade_label = tk.Label(qty_frame, bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 10, "bold"), width=5)
            quantidade_label.pack(side="left")
            tk.Button(qty_frame, text="+", font=("Segoe UI", 10, "bold"), bg=theme.FUNDO2, fg=theme.TEXTO, relief="flat", cursor="hand2", width=2, command=lambda p=produto_id: self._alterar_qty(p, 1)).pack(side="left")

            subtotal_label = tk.Label(controls, bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 10, "bold"), width=11, anchor="e")
            subtotal_label.pack(side="left", padx=(10, 0))

            action_button(controls, text="Remover", variant="ghost", command=lambda p=produto_id: self._remover_item(p), font=("Segoe UI", 9)).pack(side="left", padx=(10, 0))

            widgets = CartRowWidgets(
                row=row,
                nome=nome_label,
                codigo=codigo_label,
                alerta=alerta_label,
                quantidade=quantidade_label,
                subtotal=subtotal_label,
            )
            self._cart_rows[produto_id] = widgets
            self._atualizar_linha_carrinho(item, widgets)
            
            if i < len(self._carrinho) - 1:
                tk.Frame(self._inner_cart, bg=theme.BORDER_LIGHT, height=1).pack(fill="x", padx=10)
        bind_mousewheel_tree(self._inner_cart, self._canvas_cart)

    def _atualizar_linha_carrinho(self, item: dict, widgets: CartRowWidgets) -> None:
        widgets.nome.configure(text=item["nome"])
        widgets.codigo.configure(text=f"Cod. {item['codigo']}")
        widgets.quantidade.configure(text=f"{item['quantidade']} un.")
        widgets.subtotal.configure(text=moeda(item["quantidade"] * item["preco_unit"]))

        estoque_restante = item.get("estoque")
        alerta = widgets.alerta
        if estoque_restante is not None and estoque_restante <= 5:
            alerta.configure(text=f"⚠️ Estoque baixo: {estoque_restante}")
            if not alerta.winfo_manager():
                alerta.pack(anchor="w", pady=(4, 0))
        else:
            alerta.pack_forget()

    def _atualizar_totais(self):
        """Recalcula subtotal, quantidade, resumo de pagamento e status."""
        total = sum(item["quantidade"] * item["preco_unit"] for item in self._carrinho)
        itens = len(self._carrinho)
        unidades = sum(item["quantidade"] for item in self._carrinho)

        self._lbl_total.config(text=moeda(total))
        self._lbl_n_itens.config(text=str(itens))
        self._lbl_n_unid.config(text=str(unidades))
        self._atualizar_resumo_pagamento_lateral()
        self._atualizar_btn_finalizar()
        self._atualizar_status_fluxo()

    def _atualizar_resumo_pagamento_lateral(self) -> None:
        """Mostra forma e detalhes estruturados sem ocupar espaço quando vazios."""
        resumo = self._resumo_pagamento()
        self._lbl_pgto_resumo.config(text=resumo)
        if self._pagamento:
            self._lbl_pgto_resumo.pack(fill="x", pady=(8, 0))
        else:
            self._lbl_pgto_resumo.pack_forget()

    # ------------------------------------------------------------------
    # Pagamento
    # ------------------------------------------------------------------
    def _selecionar_pgto(self, nome: str):
        """Valida e registra a forma de pagamento escolhida."""
        if nome == "Dinheiro":
            if not self._coletar_dinheiro():
                return
        elif nome in ("Debito", "Credito"):
            if not self._coletar_bandeira(nome):
                return
        elif nome == "Mais de uma forma":
            if not self._coletar_pagamento_misto():
                return
        else:
            self._pagamento_detalhe = ""
            self._valor_recebido = None
            self._troco = None

        self._pagamento = nome
        self._atualizar_destinos_pagamento(nome)
        for forma, botao in self._btns_pgto.items():
            if forma == nome:
                botao.config(bg=theme.PGTO_BG[nome], fg=theme.PGTO_FG[nome], relief="flat", bd=0)
            else:
                botao.config(bg=theme.FUNDO2, fg=theme.TEXTO, relief="flat", bd=0)
        self._atualizar_totais()

    def _resetar_btns_pgto(self):
        """Desmarca visualmente os botoes de pagamento."""
        self._limpar_pagamento()
        for botao in self._btns_pgto.values():
            botao.config(bg=theme.FUNDO2, fg=theme.TEXTO, relief="flat", bd=0)
        self._atualizar_totais()

    def _limpar_pagamento(self):
        """Apaga os dados temporarios ligados ao pagamento da venda."""
        self._pagamento = None
        self._pagamento_detalhe = ""
        self._valor_recebido = None
        self._troco = None
        self._pagamentos_estruturados = []
        if hasattr(self, "_var_destino_financeiro"):
            self._var_destino_financeiro.set("")

    def _atualizar_destinos_pagamento(self, forma: str) -> None:
        """Carrega destinos compatíveis e mantém o primeiro como padrão."""
        if forma == "Mais de uma forma":
            self._destinos_disponiveis = {}
            self._destino_box.configure(values=())
            self._var_destino_financeiro.set("Definido por parcela")
            return
        destinos = []
        self._destinos_disponiveis = {}
        todos_destinos = self._listar_destinos_financeiros()
        todos_destinos.sort(key=lambda item: (forma not in item.get("formas_padrao", ""), item["nome"]))
        for destino in todos_destinos:
            if forma in destino["formas"]:
                destinos.append(destino["nome"])
                self._destinos_disponiveis[destino["nome"]] = int(destino["id"])
        self._destino_box.configure(values=destinos)
        self._var_destino_financeiro.set(destinos[0] if destinos else "")

    def _listar_destinos_financeiros(self) -> list[dict]:
        """Normaliza respostas locais sqlite3.Row e respostas remotas JSON."""
        destinos = list(getattr(self, "_initial_destinations", [])) or db.listar_destinos_financeiros()
        return [dict(destino) for destino in destinos]

    def _pagamentos_da_venda(self) -> list[dict]:
        """Monta parcelas estruturadas para persistência central."""
        if self._pagamento == "Mais de uma forma":
            return self._pagamentos_estruturados
        pagamento = {
            "forma": self._pagamento,
            "valor_centavos": valor_para_centavos(self._total_carrinho()),
            "detalhe": self._pagamento_detalhe,
            "valor_recebido_centavos": valor_para_centavos(self._valor_recebido) if self._valor_recebido is not None else None,
            "troco_centavos": valor_para_centavos(self._troco) if self._troco is not None else None,
        }
        destino = self._var_destino_financeiro.get()
        if destino in self._destinos_disponiveis:
            pagamento["destino_id"] = self._destinos_disponiveis[destino]
        return [pagamento]

    def _total_carrinho(self) -> float:
        """Retorna o total monetario da venda em andamento."""
        return sum(item["quantidade"] * item["preco_unit"] for item in self._carrinho)

    def _resumo_pagamento(self) -> str:
        """Gera o texto resumido exibido na lateral e no historico."""
        return summarize_payment(
            self._pagamento,
            PaymentDetails(
                detail=self._pagamento_detalhe,
                received=self._valor_recebido,
                change=self._troco,
            ),
        )

    def _parse_moeda(self, texto: str) -> float:
        """Interpreta textos como `10`, `10,50` ou `R$ 10,50`."""
        return parse_currency(texto)

    def _coletar_dinheiro(self) -> bool:
        """Abre um dialog para valor recebido e calculo de troco."""
        total = self._total_carrinho()
        dialog = tk.Toplevel(self)
        dialog.withdraw()
        dialog.title("Pagamento em dinheiro")
        dialog.configure(bg=theme.FUNDO)
        dialog.resizable(False, False)
        dialog.transient(self)
        bind_escape_to_close(dialog)
        configure_styles(dialog)

        frame = Card(dialog, padding=18)
        frame.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(frame, text="Valor recebido em dinheiro", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(frame, text=f"Total da venda: {moeda(total)}", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 12))

        valor_var = tk.StringVar()
        troco_var = tk.StringVar(value="Troco: R$ 0,00")
        erro_var = tk.StringVar(value="")
        entrada = tk.Entry(frame, textvariable=valor_var, font=("Segoe UI", 16), relief="flat", bg=theme.FUNDO2, fg=theme.TEXTO)
        entrada.pack(fill="x", ipady=8)
        tk.Label(frame, textvariable=troco_var, bg=theme.BRANCO, fg=theme.VERDE_ESC, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 2))
        tk.Label(frame, textvariable=erro_var, bg=theme.BRANCO, fg=theme.VERMELHO, font=("Segoe UI", 9)).pack(anchor="w")

        resultado = {"ok": False, "valor": None, "troco": None}

        def atualizar(*_):
            try:
                valor = self._parse_moeda(valor_var.get())
            except ValueError:
                troco_var.set("Troco: R$ 0,00")
                erro_var.set("")
                return
            troco = valor - total
            troco_var.set(f"Troco: {moeda(max(troco, 0))}")
            erro_var.set("Valor menor que o total da venda." if troco < -0.001 else "")

        def confirmar():
            try:
                valor = self._parse_moeda(valor_var.get())
            except ValueError:
                erro_var.set("Informe um valor valido, como 50 ou 50,00.")
                return
            troco = valor - total
            if troco < -0.001:
                erro_var.set("Valor menor que o total da venda.")
                return
            resultado.update({"ok": True, "valor": valor, "troco": troco})
            dialog.destroy()

        valor_var.trace_add("write", atualizar)
        botoes = tk.Frame(frame, bg=theme.BRANCO)
        botoes.pack(fill="x", pady=(14, 0))
        tk.Button(botoes, text="Cancelar", bg=theme.FUNDO2, fg=theme.MUTED, relief="flat", command=dialog.destroy).pack(side="right", padx=(8, 0), ipadx=10, ipady=6)
        tk.Button(botoes, text="Confirmar", bg=theme.VERDE_ESC, fg=theme.BRANCO, relief="flat", command=confirmar).pack(side="right", ipadx=10, ipady=6)
        entrada.bind("<Return>", lambda _event: confirmar())
        dialog.update_idletasks()
        largura = max(420, dialog.winfo_reqwidth())
        altura = max(260, dialog.winfo_reqheight())
        x = self.winfo_rootx() + max(0, (self.winfo_width() - largura) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - altura) // 2)
        dialog.geometry(f"{largura}x{altura}+{x}+{y}")
        dialog.deiconify()
        dialog.lift()
        dialog.grab_set()
        entrada.focus_set()
        self.wait_window(dialog)

        if not resultado["ok"]:
            return False
        self._pagamento_detalhe = f"Recebido {moeda(resultado['valor'])}; troco {moeda(resultado['troco'])}"
        self._valor_recebido = resultado["valor"]
        self._troco = resultado["troco"]
        return True

    def _coletar_pagamento_misto(self) -> bool:
        """Coleta um pagamento composto por duas ou mais formas."""
        dialog = BaseModal(
            self,
            title="Mais de uma forma",
            subtitle="Selecione duas ou mais formas e detalhe os cartoes escolhidos.",
            width=680,
            height=620,
        )
        dialog.resizable(False, False)

        tema = theme.TEMA_ATUAL
        canvas = tk.Canvas(dialog.body_frame, bg=tema["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(dialog.body_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        frame = tk.Frame(canvas, bg=tema["bg"])
        frame_window = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(frame_window, width=event.width))

        def rolar(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        dialog.bind("<MouseWheel>", rolar)
        tk.Label(frame, text="Selecione duas formas de pagamento", bg=theme.FUNDO, fg=theme.TEXTO, font=("Segoe UI", 13, "bold")).pack(
            anchor="w"
        )
        tk.Label(frame, text="O detalhe aparecerá no histórico e na planilha.", bg=theme.FUNDO, fg=theme.MUTED, font=("Segoe UI", 10)).pack(
            anchor="w", pady=(4, 10)
        )

        vars_pgto = {
            forma: tk.BooleanVar(value=False)
            for forma in MIXED_PAYMENT_METHODS
        }
        valores_parcela = {forma: tk.StringVar(value="0,00") for forma in MIXED_PAYMENT_METHODS}
        destinos_por_forma: dict[str, list[tuple[str, int, bool]]] = {forma: [] for forma in MIXED_PAYMENT_METHODS}
        destinos_cadastrados = self._listar_destinos_financeiros()
        for destino in destinos_cadastrados:
            for forma in MIXED_PAYMENT_METHODS:
                if forma in destino["formas"]:
                    destinos_por_forma[forma].append((destino["nome"], int(destino["id"]), forma in destino.get("formas_padrao", "")))
        for forma in destinos_por_forma:
            destinos_por_forma[forma].sort(key=lambda item: (not item[2], item[0]))
        destinos_vars = {
            forma: tk.StringVar(value=opcoes[0][0] if opcoes else "")
            for forma, opcoes in destinos_por_forma.items()
        }
        detalhes_cartao = {}
        total_venda = self._total_carrinho()

        def redistribuir_valores():
            selecionadas = [forma for forma, var in vars_pgto.items() if var.get()]
            if not selecionadas:
                return
            total_centavos = valor_para_centavos(total_venda)
            base, resto = divmod(total_centavos, len(selecionadas))
            for indice, forma in enumerate(selecionadas):
                valores_parcela[forma].set(f"{(base + (1 if indice < resto else 0)) / 100:.2f}".replace(".", ","))

        def detalhe_texto(forma: str) -> str:
            info = detalhes_cartao.get(forma, {})
            if forma == "Debito":
                bandeira_var = info.get("bandeira_var")
                bandeira = bandeira_var.get() if bandeira_var else CARD_BRANDS[0]
                return f"{bandeira}"
            if forma == "Credito":
                bandeira_var = info.get("bandeira_var")
                parcela_var = info.get("parcelas_var")
                bandeira = bandeira_var.get() if bandeira_var else CARD_BRANDS[0]
                parcelas = parcela_var.get() if parcela_var else "1"
                return f"{bandeira} | {parcelas}x"
            if forma == "Dinheiro":
                valor_var = info.get("valor_var")
                if not valor_var or not valor_var.get().strip():
                    return ""
                valor = self._parse_moeda(valor_var.get())
                troco = max(valor - total_venda, 0)
                return f"Recebido {moeda(valor)}; troco {moeda(troco)}"
            return ""

        def atualizar_visibilidade(forma: str):
            info = detalhes_cartao.get(forma)
            if not info:
                return
            if vars_pgto[forma].get():
                info["parcela"].pack(fill="x", pady=(6, 0))
                if info.get("card"):
                    info["card"].pack(fill="x", pady=(8, 0))
            else:
                info["parcela"].pack_forget()
                if info.get("card"):
                    info["card"].pack_forget()

        for forma in MIXED_PAYMENT_METHODS:
            linha = Card(frame, padding=10)
            linha.pack(fill="x", pady=(0, 8))

            check = tk.Checkbutton(
                linha,
                text=PAYMENT_LABELS[forma],
                variable=vars_pgto[forma],
                indicatoron=False,
                bg=tema["surface_2"],
                fg=tema["text"],
                selectcolor=tema["primary_soft"],
                activebackground=tema["surface_hover"],
                activeforeground=tema["text"],
                font=FONTES["botao"],
                relief="flat",
                bd=0,
                padx=14,
                pady=8,
                cursor="hand2",
                command=lambda f=forma: (redistribuir_valores(), atualizar_visibilidade(f)),
            )
            check.pack(fill="x", anchor="w")

            parcela = tk.Frame(linha, bg=tema["surface"], padx=10, pady=8)
            detalhes_cartao[forma] = {"parcela": parcela}
            tk.Label(parcela, text="Valor desta parcela", bg=tema["surface"], fg=tema["text_muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
            StyledEntry(parcela, textvariable=valores_parcela[forma]).pack(fill="x", pady=(3, 6))
            tk.Label(parcela, text="Destino financeiro", bg=tema["surface"], fg=tema["text_muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
            ttk.Combobox(parcela, textvariable=destinos_vars[forma], values=[nome for nome, _, _ in destinos_por_forma[forma]], state="readonly").pack(fill="x", pady=(3, 0))
            parcela.pack_forget()

            if forma in ("Debito", "Credito"):
                detalhe_card = tk.Frame(linha, bg=tema["surface"], padx=10, pady=8)
                detalhes_cartao[forma]["card"] = detalhe_card

                bandeira_var = tk.StringVar(value=CARD_BRANDS[0])
                detalhes_cartao[forma]["bandeira_var"] = bandeira_var
                tk.Label(
                    detalhe_card,
                    text="Bandeira",
                    bg=tema["surface"],
                    fg=tema["text_muted"],
                    font=("Segoe UI", 8, "bold"),
                ).pack(anchor="w", pady=(0, 4))
                self._criar_grade_opcoes(
                    detalhe_card,
                    bandeira_var,
                    CARD_BRANDS,
                    colunas=3,
                )

                if forma == "Credito":
                    parcela_var = tk.StringVar(value="1")
                    detalhes_cartao[forma]["parcelas_var"] = parcela_var
                    tk.Label(
                        detalhe_card,
                        text="Parcelas",
                        bg=tema["surface"],
                        fg=tema["text_muted"],
                        font=("Segoe UI", 8, "bold"),
                    ).pack(anchor="w", pady=(8, 4))
                    self._criar_grade_opcoes(
                        detalhe_card,
                        parcela_var,
                        CARD_INSTALLMENTS,
                        colunas=6,
                        sufixo="x",
                    )

                detalhe_card.pack_forget()
            elif forma == "Dinheiro":
                detalhe_card = tk.Frame(linha, bg=tema["surface"], padx=10, pady=8)
                valor_var = tk.StringVar()
                troco_var = tk.StringVar(value=f"Troco: {moeda(0)}")
                detalhes_cartao[forma].update({
                    "card": detalhe_card,
                    "valor_var": valor_var,
                    "troco_var": troco_var,
                })

                tk.Label(
                    detalhe_card,
                    text=f"Total da venda: {moeda(total_venda)}",
                    bg=tema["surface"],
                    fg=tema["text_muted"],
                    font=FONTES["corpo"],
                ).pack(anchor="w", pady=(0, 8))

                campo_valor = LabeledField(
                    detalhe_card,
                    label="Valor recebido em dinheiro",
                    widget_factory=lambda parent, var=valor_var: StyledEntry(parent, textvariable=var),
                    bg=tema["surface"],
                )
                campo_valor.widget.pack(fill="x", ipady=4)
                campo_valor.pack(fill="x", pady=(0, 8))

                tk.Label(
                    detalhe_card,
                    textvariable=troco_var,
                    bg=tema["surface"],
                    fg=tema["primary"],
                    font=FONTES["subtitulo"],
                ).pack(anchor="w")

                def atualizar_troco(*_, var=valor_var, destino=troco_var, forma_atual=forma):
                    try:
                        valor = self._parse_moeda(var.get())
                        parcela = self._parse_moeda(valores_parcela[forma_atual].get())
                    except ValueError:
                        destino.set(f"Troco: {moeda(0)}")
                        return
                    destino.set(f"Troco: {moeda(max(valor - parcela, 0))}")

                valor_var.trace_add("write", atualizar_troco)
                detalhe_card.pack_forget()
            atualizar_visibilidade(forma)

        erro_var = tk.StringVar(value="")
        tk.Label(frame, textvariable=erro_var, bg=tema["bg"], fg=tema["danger"], font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 0))
        resultado = {"ok": False, "detalhe": ""}

        def confirmar():
            selecionadas = [forma for forma, var in vars_pgto.items() if var.get()]
            if len(selecionadas) < 2:
                erro_var.set("Selecione pelo menos duas formas.")
                return
            partes = []
            pagamentos = []
            soma_centavos = 0
            for forma in selecionadas:
                try:
                    valor_centavos = valor_para_centavos(
                        self._parse_moeda(valores_parcela[forma].get())
                    )
                except ValueError:
                    erro_var.set(f"Informe um valor válido para {PAYMENT_LABELS[forma]}.")
                    return
                if valor_centavos <= 0:
                    erro_var.set(f"O valor de {PAYMENT_LABELS[forma]} deve ser maior que zero.")
                    return
                destino_nome = destinos_vars[forma].get()
                destino_id = next((identificador for nome, identificador, _ in destinos_por_forma[forma] if nome == destino_nome), None)
                if destino_id is None:
                    erro_var.set(f"Configure um destino financeiro para {PAYMENT_LABELS[forma]}.")
                    return
                if forma in ("Debito", "Credito"):
                    detalhe = detalhe_texto(forma)
                    partes.append(f"{forma} ({detalhe})" if detalhe else forma)
                elif forma == "Dinheiro":
                    try:
                        detalhe = detalhe_texto(forma)
                    except ValueError:
                        erro_var.set("Informe um valor valido em dinheiro, como 50 ou 50,00.")
                        return
                    if not detalhe:
                        erro_var.set("Informe o valor recebido em dinheiro.")
                        return
                    partes.append(f"Dinheiro ({detalhe})")
                else:
                    partes.append(forma)
                    detalhe = ""
                pagamentos.append({"forma": forma, "destino_id": destino_id, "valor_centavos": valor_centavos, "detalhe": detalhe})
                soma_centavos += valor_centavos
            if soma_centavos != valor_para_centavos(total_venda):
                erro_var.set(f"A soma das parcelas deve ser {moeda(total_venda)}.")
                return
            valor_recebido = None
            troco = None
            if "Dinheiro" in selecionadas:
                valor_recebido = self._parse_moeda(detalhes_cartao["Dinheiro"]["valor_var"].get())
                valor_dinheiro = self._parse_moeda(valores_parcela["Dinheiro"].get())
                troco = max(valor_recebido - valor_dinheiro, 0)
                for pagamento_item in pagamentos:
                    if pagamento_item["forma"] == "Dinheiro":
                        pagamento_item["valor_recebido_centavos"] = valor_para_centavos(valor_recebido)
                        pagamento_item["troco_centavos"] = valor_para_centavos(troco)
            resultado.update({
                "ok": True,
                "detalhe": " + ".join(partes),
                "valor_recebido": valor_recebido,
                "troco": troco,
                "pagamentos": pagamentos,
            })
            dialog.close()

        action_button(dialog.footer_frame, text="Cancelar", variant="ghost", command=dialog.close).pack(
            side="right", padx=(8, 0)
        )
        action_button(dialog.footer_frame, text="Confirmar", variant="primary", command=confirmar).pack(side="right")
        bind_mousewheel_tree(frame, canvas)
        dialog.show()
        self.wait_window(dialog)

        if not resultado["ok"]:
            return False
        self._pagamento_detalhe = resultado["detalhe"]
        self._valor_recebido = resultado.get("valor_recebido")
        self._troco = resultado.get("troco")
        self._pagamentos_estruturados = resultado.get("pagamentos", [])
        return True

    def _criar_grade_opcoes(
        self,
        parent: tk.Widget,
        variable: tk.StringVar,
        opcoes: list[str] | tuple[str, ...],
        *,
        colunas: int = 3,
        sufixo: str = "",
    ) -> list[tk.Radiobutton]:
        """Cria opcoes visiveis em vez de dropdown para escolhas curtas."""
        tema = theme.TEMA_ATUAL
        grid = tk.Frame(parent, bg=tema["surface"])
        grid.pack(fill="x", pady=(4, 8))
        botoes: list[tk.Radiobutton] = []

        def atualizar():
            for botao in botoes:
                selecionado = botao.cget("value") == variable.get()
                botao.configure(
                    bg=tema["primary_soft"] if selecionado else tema["surface_2"],
                    fg=tema["primary"] if selecionado else tema["text"],
                    relief="solid" if selecionado else "flat",
                    bd=1 if selecionado else 0,
                    highlightbackground=tema["primary"] if selecionado else tema["border_soft"],
                )

        for idx, opcao in enumerate(opcoes):
            row = idx // colunas
            col = idx % colunas
            grid.columnconfigure(col, weight=1, uniform="opcoes")
            botao = tk.Radiobutton(
                grid,
                text=f"{opcao}{sufixo}",
                value=opcao,
                variable=variable,
                indicatoron=False,
                command=atualizar,
                bg=tema["surface_2"],
                fg=tema["text"],
                selectcolor=tema["primary_soft"],
                activebackground=tema["surface_hover"],
                activeforeground=tema["text"],
                font=FONTES["botao"],
                relief="flat",
                bd=0,
                padx=10,
                pady=8,
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=tema["border_soft"],
            )
            botao.grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0), pady=(0, 6))
            botoes.append(botao)

        atualizar()
        return botoes

    def _coletar_bandeira(self, tipo: str) -> bool:
        """Solicita bandeira e, no credito, quantidade de parcelas."""
        eh_debito = tipo == "Debito"
        dialog = BaseModal(
            self,
            title="Cartão de débito" if eh_debito else "Cartão de crédito",
            subtitle="Informe os dados que serão registrados na venda e no relatório.",
            width=560,
            height=430 if eh_debito else 560,
        )
        dialog.resizable(False, False)
        frame = Card(dialog.body_frame, padding=16)
        frame.pack(fill="both", expand=True)

        escolhida = tk.StringVar(value=CARD_BRANDS[0])
        tk.Label(
            frame,
            text="Bandeira",
            bg=theme.BRANCO,
            fg=theme.MUTED,
            font=FONTES["label_sm"],
        ).pack(anchor="w")
        self._criar_grade_opcoes(frame, escolhida, CARD_BRANDS, colunas=2)

        parcela_var = tk.StringVar(value="1")
        if not eh_debito:
            tk.Label(
                frame,
                text="Parcelas",
                bg=theme.BRANCO,
                fg=theme.MUTED,
                font=FONTES["label_sm"],
            ).pack(anchor="w", pady=(12, 6))
            self._criar_grade_opcoes(
                frame,
                parcela_var,
                CARD_INSTALLMENTS,
                colunas=4,
                sufixo="x",
            )

        resultado = {"ok": False}

        def confirmar():
            resultado["ok"] = True
            dialog.close()

        action_button(dialog.footer_frame, text="Cancelar", variant="ghost", command=dialog.close).pack(
            side="right", padx=(8, 0)
        )
        action_button(dialog.footer_frame, text="Confirmar", variant="primary", command=confirmar).pack(side="right")
        dialog.bind("<Return>", lambda _event: confirmar())
        dialog.show()
        self.wait_window(dialog)

        if not resultado["ok"]:
            return False
        detalhe = escolhida.get().strip()
        if not eh_debito:
            detalhe = f"{detalhe} | {parcela_var.get().strip()}x"
        self._pagamento_detalhe = detalhe
        self._valor_recebido = None
        self._troco = None
        return True

    # ------------------------------------------------------------------
    # Estado do fluxo de venda
    # ------------------------------------------------------------------
    def _atualizar_btn_finalizar(self):
        """Habilita ou bloqueia a finalizacao conforme o estado da venda."""
        pode_finalizar = bool(self._carrinho) and bool(self._pagamento)
        self._btn_finalizar.config(
            state="normal" if pode_finalizar else "disabled",
            bg=theme.VERDE_ESC if pode_finalizar else theme.BORDA,
            fg=theme.BRANCO if pode_finalizar else theme.MUTED,
        )

    def _atualizar_status_fluxo(self):
        """Atualiza o card lateral com a proxima acao esperada."""
        if hasattr(self, "_status_pills"):
            for w in self._status_pills.winfo_children():
                w.destroy()

        if self._feedback_apos_venda:
            self._lbl_status_fluxo.config(text=self._feedback_apos_venda)
            return

        # Verifica se algum item no carrinho possui estoque baixo (<= 5)
        alertas = sum(1 for i in self._carrinho if i.get("estoque") is not None and i.get("estoque") <= 5)

        if not self._carrinho:
            self._lbl_status_fluxo.config(text="Adicione produtos para liberar pagamento e finalização.")
            self._badge_pronta.pack_forget() if hasattr(self, '_badge_pronta') else None
            return

        if hasattr(self, "_status_pills"):
            StatusBadge(self._status_pills, f"{len(self._carrinho)} itens no carrinho", bg=theme.TEMA_ATUAL["primary_soft"], fg=theme.TEMA_ATUAL["primary"]).pack(anchor="w", pady=(0, 6))
            if alertas > 0:
                StatusBadge(self._status_pills, f"{alertas} alerta{'s' if alertas > 1 else ''} de estoque baixo", bg=theme.TEMA_ATUAL["warning_soft"], fg=theme.TEMA_ATUAL["warning"]).pack(anchor="w", pady=(0, 6))
            
            if self._pagamento:
                StatusBadge(self._status_pills, "Pagamento selecionado", bg=theme.TEMA_ATUAL["primary_soft"], fg=theme.TEMA_ATUAL["primary"]).pack(anchor="w", pady=(0, 6))
            bind_mousewheel_tree(self._right_pad, self._right_canvas)

        if not self._pagamento:
            self._lbl_status_fluxo.config(text="Foco na busca e carrinho válido. Selecione um pagamento.")
            self._badge_pronta.pack_forget() if hasattr(self, '_badge_pronta') else None
            return

        self._lbl_status_fluxo.config(text="Foco na busca, carrinho válido e pagamento selecionado.")
        if hasattr(self, '_badge_pronta'):
            self._badge_pronta.pack(side="right", padx=(12, 0))

    def _responsavel_atual(self) -> str:
        """Retorna o nome do responsavel vinculado ao periodo atual."""
        return self._var_responsavel.get().strip()

    def _salvar_responsavel_periodo(self, *_):
        """Persiste automaticamente o responsavel quando o campo muda."""
        if self._atualizando_responsavel or not self._periodo_id:
            return
        if remote_mode():
            periodo_id = self._periodo_id
            responsavel = self._responsavel_atual()
            self._submit_background(
                lambda: db.atualizar_responsavel_periodo(periodo_id, responsavel),
                lambda _result, _error: None,
            )
        else:
            db.atualizar_responsavel_periodo(self._periodo_id, self._responsavel_atual())

    # ------------------------------------------------------------------
    # Periodos e vendas
    # ------------------------------------------------------------------
    def _aplicar_totais_periodo(self, totais: dict) -> None:
        """Atualiza rodapé e KPIs com valores persistidos do Período da Loja."""
        self._vendas_dia = int(totais.get("transacoes") or 0)
        self._total_dia = float(totais.get("total") or 0)
        self._correcoes_periodo = int(totais.get("correcoes") or 0)
        self._lbl_vendas_dia.config(text=str(self._vendas_dia))
        self._lbl_total_dia.config(text=moeda(self._total_dia))
        if "_lbl_header_vendas" in self.__dict__:
            self._lbl_header_vendas.config(text=str(self._vendas_dia))
            self._lbl_header_total.config(text=moeda(self._total_dia))
        self._kpi_hoje.value_label.config(text=moeda(self._total_dia))
        self._kpi_vendas.value_label.config(text=str(self._vendas_dia))
        self._kpi_correcoes.value_label.config(text=str(self._correcoes_periodo))

    def _atualizar_resumo_periodo(self) -> None:
        """Recarrega KPIs após Venda, Correção pós-venda ou Cancelamento."""
        if not self._periodo_id:
            return
        if remote_mode():
            periodo_id = self._periodo_id
            self._submit_background(
                lambda: db.totais_periodo(periodo_id),
                lambda totais, erro: None if erro else self._aplicar_totais_periodo(totais),
            )
            return
        self._aplicar_totais_periodo(db.totais_periodo(self._periodo_id))

    def _apos_atualizacao_venda(self) -> None:
        """Sincroniza estoque e resumo quando uma venda é corrigida."""
        self._atualizar_painel_estoque()
        self._atualizar_resumo_periodo()

    def _abrir_periodo_para_data(self, data: str):
        """Carrega ou cria o periodo aberto correspondente a uma data."""
        periodo = db.obter_ou_criar_periodo_aberto(data)
        totais = db.totais_periodo(periodo["id"])

        self._data_hoje = periodo["data"]
        self._periodo_id = periodo["id"]
        self._periodo_seq = periodo["sequencia"]
        self._num_venda = db.proximo_num_venda(self._periodo_id)
        self._lbl_data.config(text=self._data_hoje)
        self._lbl_periodo.config(text=f"{self._periodo_seq:02d}")
        if "_lbl_header_periodo" in self.__dict__:
            self._lbl_header_periodo.config(text=f"{self._periodo_seq:02d}")
        self._aplicar_totais_periodo(totais)

        self._atualizando_responsavel = True
        self._var_responsavel.set(periodo["responsavel"] or "")
        self._atualizando_responsavel = False

        self._atualizar_badge_venda()
        self._atualizar_totais()
        self._atualizar_historico()

    def _complete_initial_context(self, context, error=None) -> None:
        """Apply the aggregated opening context after the first useful paint."""
        if error:
            self._lbl_status_fluxo.config(text="Central indisponível. Venda offline disponível conforme permissão.")
            return
        periodo = context["periodo"]
        totais = context["totais"]
        self._initial_destinations = context["destinos"]
        self._data_hoje = periodo["data"]
        self._periodo_id = periodo["id"]
        self._periodo_seq = periodo["sequencia"]
        self._num_venda = context["proximo_num_venda"]
        self._lbl_data.config(text=self._data_hoje)
        self._lbl_periodo.config(text=f"{self._periodo_seq:02d}")
        if "_lbl_header_periodo" in self.__dict__:
            self._lbl_header_periodo.config(text=f"{self._periodo_seq:02d}")
        self._aplicar_totais_periodo(totais)
        self._atualizando_responsavel = True
        self._var_responsavel.set(periodo["responsavel"] or "")
        self._atualizando_responsavel = False
        self._atualizar_badge_venda()
        self._atualizar_totais()

    def _finalizar_venda(self):
        """Grava a venda, atualiza indicadores e prepara o proximo atendimento."""
        if not self._carrinho or not self._pagamento:
            return
        responsavel = self._responsavel_atual()
        if not responsavel:
            messagebox.showerror("Operador obrigatório", "Informe o Operador antes de finalizar a Venda no caixa.")
            self._entry_responsavel.focus_set()
            return

        total = self._total_carrinho()
        numero_venda = self._num_venda
        pagamento = self._resumo_pagamento()
        args = (
            self._periodo_id,
            self._num_venda,
            [dict(item) for item in self._carrinho],
            self._pagamento,
        )
        kwargs = {
            "pagamento_detalhe": self._pagamento_detalhe,
            "valor_recebido": self._valor_recebido,
            "troco": self._troco,
            "responsavel": responsavel,
            "data": self._data_hoje,
            "pagamentos": self._pagamentos_da_venda(),
            "chave_idempotencia": self._sale_uuid,
        }
        if remote_mode():
            self._btn_finalizar.config(state="disabled")
            self._submit_background(
                lambda: db.registrar_venda(*args, **kwargs),
                lambda resultado, error: self._complete_sale_registration(
                    resultado, error, total, numero_venda, pagamento
                ),
            )
            return
        try:
            resultado_venda = db.registrar_venda(*args, **kwargs)
        except Exception as error:
            self._complete_sale_registration(None, error, total, numero_venda, pagamento)
            return
        self._complete_sale_registration(resultado_venda, None, total, numero_venda, pagamento)

    def _complete_sale_registration(self, resultado_venda, error, total, numero_venda, pagamento) -> None:
        if error:
            self._btn_finalizar.config(state="normal")
            self._atualizar_totais()
            messagebox.showerror("Venda não concluída", str(error))
            return

        self._aplicar_totais_periodo(
            {
                "transacoes": self._vendas_dia + 1,
                "total": self._total_dia + total,
                "correcoes": self._correcoes_periodo,
            }
        )

        self._nova_venda(consultar_servidor=not remote_mode() and not bool(resultado_venda and resultado_venda.get("offline")))
        self._atualizar_historico()
        self._atualizar_painel_estoque()
        self._mostrar_feedback_venda(
            f"Venda #{numero_venda:03d} salva offline e aguardando sincronização."
            if resultado_venda and resultado_venda.get("offline")
            else f"Venda #{numero_venda:03d} registrada por {moeda(total)} em {pagamento}."
        )
        alertas = (resultado_venda or {}).get("alertas_estoque", [])
        if alertas:
            linhas = [
                f"{alerta.get('codigo') or alerta.get('nome') or 'Produto'}: saldo {alerta['saldo_resultante']}"
                for alerta in alertas
            ]
            messagebox.showwarning(
                "Estoque negativo registrado",
                "A Venda no caixa foi concluída, mas estes produtos ficaram com saldo negativo:\n\n"
                + "\n".join(linhas),
            )

    def _nova_venda(self, consultar_servidor: bool = True):
        """Reseta a tela para iniciar uma nova venda no mesmo periodo."""
        if self._feedback_after_id:
            self.after_cancel(self._feedback_after_id)
            self._feedback_after_id = None
        self._num_venda = db.proximo_num_venda(self._periodo_id) if consultar_servidor else self._num_venda + 1
        self._sale_uuid = str(uuid.uuid4())
        self._atualizar_badge_venda()
        self._limpar_carrinho()
        self._entry_busca.focus()

    def _mostrar_feedback_venda(self, mensagem: str):
        """Exibe uma mensagem temporaria de sucesso apos a venda."""
        self._feedback_apos_venda = mensagem
        self._atualizar_status_fluxo()
        self._feedback_after_id = self.after(3500, self._limpar_feedback_venda)

    def _limpar_feedback_venda(self):
        """Remove a mensagem temporaria e devolve o status normal do fluxo."""
        self._feedback_after_id = None
        self._feedback_apos_venda = None
        self._atualizar_status_fluxo()

    # ------------------------------------------------------------------
    # Relatorios e importacao
    # ------------------------------------------------------------------
    def _exportar_periodo(self, pasta_saida: str):
        """Monta os dados do periodo e delega a geracao do relatorio."""
        periodo = db.obter_periodo(self._periodo_id)
        if not periodo or not db.vendas_do_periodo(self._periodo_id):
            return None

        return period_report(self._periodo_id, Path(pasta_saida) / f"Relatorio_periodo-{self._periodo_id}.xlsx")

    def _exportar_relatorio(self):
        """Permite ao operador escolher a pasta de exportacao manual."""
        if not db.vendas_do_periodo(self._periodo_id):
            messagebox.showinfo("Sem dados", "Nenhuma venda registrada no periodo atual para exportar.")
            return

        pasta = filedialog.askdirectory(title="Salvar relatorio em...")
        if not pasta:
            return

        caminho = self._exportar_periodo(pasta)
        messagebox.showinfo("Relatorio gerado", f"Arquivo salvo em:\n{caminho}")

    def _encerrar_dia(self):
        """Fecha o Período da Loja atomicamente e exporta o snapshot depois."""
        responsavel = self._responsavel_atual()
        if not responsavel:
            messagebox.showerror("Operador obrigatório", "Informe o Operador antes de fechar o Período da Loja.")
            self._entry_responsavel.focus_set()
            return
        try:
            sync_pending_sales()
        except Exception:
            pass
        if pending_sales():
            messagebox.showerror("Sincronização pendente", "Existem vendas offline ainda não confirmadas. Reconecte ao servidor antes de encerrar o período.")
            return
        if self._carrinho:
            confirmar = messagebox.askyesno(
                "Encerrar dia",
                "Existe uma venda em andamento no carrinho. Deseja descarta-la para encerrar o dia?",
            )
            if not confirmar:
                return
            self._limpar_carrinho()

        periodo_atual = db.obter_periodo(self._periodo_id)
        if not periodo_atual:
            messagebox.showerror("Erro", "Nao foi possivel localizar o periodo atual do caixa.")
            return

        periodo_fechado_id = self._periodo_id
        try:
            snapshot = db.fechar_periodo_loja(periodo_fechado_id, responsavel)
        except Exception as error:
            messagebox.showerror("Período não fechado", str(error))
            return

        self._periodo_id = int(snapshot["proximo_periodo_id"])
        novo_periodo = db.obter_periodo(self._periodo_id)
        if novo_periodo is None:
            messagebox.showerror(
                "Período fechado",
                "O fechamento foi salvo, mas o novo Período da Loja não pôde ser carregado. Reinicie o PDV.",
            )
            return
        self._abrir_periodo_para_data(novo_periodo["data"])
        self._mostrar_feedback_venda(f"Periodo {self._periodo_seq:02d} pronto para novas vendas.")

        teve_vendas = int(snapshot.get("total_vendas_centavos", 0)) > 0
        caminho = None
        if teve_vendas:
            try:
                caminho = period_report(
                    periodo_fechado_id,
                    REPORTS_DIR / f"Relatorio_periodo-{periodo_fechado_id}.xlsx",
                )
            except Exception as error:
                messagebox.showerror(
                    "Período fechado; relatório pendente",
                    "O fechamento financeiro foi salvo, mas o XLSX não foi gerado. "
                    f"Exporte novamente pela tela de relatórios.\n\nDetalhe: {error}",
                )
                return

        if teve_vendas:
            messagebox.showinfo(
                "Dia encerrado",
                "O periodo foi encerrado e o relatorio foi exportado automaticamente para:\n"
                f"{caminho}\n\nNovo periodo iniciado: {self._periodo_seq:02d}.",
            )
        else:
            messagebox.showinfo(
                "Dia encerrado",
                f"Nenhuma venda registrada no periodo anterior.\nNovo periodo iniciado: {self._periodo_seq:02d}.",
            )

    def _importar_planilha(self):
        """Importa produtos a partir de CSV ou planilhas Excel."""
        responsavel = self._responsavel_atual()
        if not responsavel:
            messagebox.showerror("Operador obrigatório", "Informe o Operador antes de importar produtos.")
            self._entry_responsavel.focus_set()
            return
        arquivo = filedialog.askopenfilename(
            title="Selecionar planilha de produtos",
            filetypes=[
                ("Planilhas", "*.csv *.xlsx *.xlsm *.xltx *.xltm"),
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx *.xlsm *.xltx *.xltm"),
                ("Todos", "*.*"),
            ],
        )
        if not arquivo:
            return
        try:
            previa = importacao_service.previsualizar(arquivo)
            modo = confirmar_importacao(self, previa)
            if not modo:
                return
            resultado = importacao_service.importar(
                arquivo,
                modo,
                responsavel=responsavel,
                lote_id=str(uuid.uuid4()),
                hash_arquivo=previa.get("sha256", ""),
            )
            messagebox.showinfo(
                "Importacao concluida",
                f"{resultado['inseridos']} produtos inseridos\n"
                f"{resultado['atualizados']} produtos atualizados\n"
                f"{resultado['ajustados']} ajustes de estoque registrados\n"
                f"{resultado['ignorados']} linhas ignoradas\n"
                f"Coluna de estoque: {resultado['coluna_estoque'] or 'nao mapeada'}",
            )
            self._atualizar_painel_estoque()
        except Exception as erro:
            messagebox.showerror("Erro na importacao", str(erro))

    def _criar_backup(self):
        try:
            caminho = create_backup(BACKUPS_DIR / f"loja_{datetime.now():%Y%m%d_%H%M%S}.db")
            messagebox.showinfo("Backup concluido", f"Backup criado com sucesso em:\n{caminho}")
        except Exception as erro:
            messagebox.showerror("Erro no backup", f"Nao foi possivel criar o backup.\n\n{erro}")

    def _restaurar_backup(self):
        arquivo = filedialog.askopenfilename(
            title="Selecionar backup do banco de dados",
            initialdir=str(BACKUPS_DIR),
            filetypes=[("Banco SQLite", "*.db"), ("Todos os arquivos", "*.*")],
        )
        if not arquivo:
            return

        caminho = Path(arquivo)
        confirmar = messagebox.askyesno(
            "⚠️ CONFIRMAÇÃO DE AÇÃO SENSÍVEL - RESTAURAR BACKUP",
            "Você está prestes a RESTAURAR o banco de dados do sistema.\n\n"
            "⚠️ ATENÇÃO E RISCO:\n"
            "• O banco de dados atual SERÁ SUBSTITUÍDO pelo arquivo selecionado.\n"
            "• Vendas recentes e alterações não salvas serão sobrescritas.\n"
            "• Um backup de segurança do estado atual será criado automaticamente antes da restauração.\n\n"
            f"Arquivo de backup selecionado:\n{caminho.name}\n\n"
            "Deseja realmente prosseguir com a restauração do sistema?",
            icon="warning",
        )
        if not confirmar:
            return

        try:
            resultado = restore_backup(caminho)
            anterior = resultado.get("backup_anterior")
            self._abrir_periodo_para_data(datetime.now().strftime("%d/%m/%Y"))
            self._atualizar_painel_estoque()
            self._atualizar_historico()
            detalhe = f"\n\nBackup de segurança gerado antes da restauração:\n{anterior}" if anterior else ""
            messagebox.showinfo("Restauração concluída", f"O banco de dados foi restaurado com sucesso.{detalhe}")
        except Exception as erro:
            messagebox.showerror("Erro na restauração", f"Não foi possível restaurar o backup.\n\n{erro}")

    # ------------------------------------------------------------------
    # Ajustes visuais e sincronizacao da interface
    # ------------------------------------------------------------------
    def _ajustar_scroll_carrinho(self, _event=None):
        """Atualiza a area rolavel do carrinho apos mudancas de conteudo."""
        self._canvas_cart.configure(scrollregion=self._canvas_cart.bbox("all"))

    def _ajustar_largura_carrinho(self, event):
        """Mantem o frame interno do carrinho com a largura do canvas."""
        self._canvas_cart.itemconfigure(self._canvas_window, width=event.width)

    def _ajustar_scroll_lateral(self, _event=None):
        """Recalcula a rolagem da coluna lateral direita."""
        if self._right_canvas:
            self._right_canvas.configure(scrollregion=self._right_canvas.bbox("all"))

    def _ajustar_largura_lateral(self, event):
        """Ajusta a largura do conteudo lateral ao redimensionar a janela."""
        if self._right_canvas and self._right_window:
            self._right_canvas.itemconfigure(self._right_window, width=event.width)

    def _rolar_painel_lateral(self, event):
        """Traduz a roda do mouse para a rolagem do painel lateral."""
        if self._right_canvas:
            self._right_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    # Historico e edicao de vendas
    # ------------------------------------------------------------------
    def _atualizar_historico(self):
        """Recarrega a grade com as vendas e correções do período atual."""
        if hasattr(self, "_vendas_correcoes_view"):
            self._vendas_correcoes_view.solicitar_atualizacao()

    def _atualizar_painel_estoque(self):
        """Sincroniza a aba de estoque apos vendas ou importacoes."""
        if remote_mode():
            if hasattr(self, "_estoque_dashboard"):
                self._submit_background(
                    db.snapshot_dashboard_estoque,
                    lambda snapshot, error: self._complete_stock_load(self._estoque_dashboard, snapshot, error),
                )
            if hasattr(self, "_estoque_panel"):
                self._submit_background(
                    db.snapshot_operacional_estoque,
                    lambda snapshot, error: self._complete_stock_load(self._estoque_panel, snapshot, error),
                )
            return
        for atributo in (
            "_estoque_dashboard",
            "_estoque_panel",
            "_estoque_movimentacoes",
            "_estoque_configuracoes",
        ):
            painel = getattr(self, atributo, None)
            if painel is not None:
                painel.atualizar()

    def _editar_venda_selecionada(self):
        """Abre um dialog para corrigir pagamento e responsavel de uma venda."""
        if not self._historico_tree or not self._periodo_id:
            return
        selecao = self._historico_tree.selection()
        if not selecao:
            messagebox.showinfo("Selecionar venda", "Selecione uma venda na lista para editar.")
            return

        num_venda = int(selecao[0])
        linhas = [dict(row) for row in db.vendas_do_periodo(self._periodo_id) if row["num_venda"] == num_venda]
        if not linhas:
            messagebox.showerror("Erro", "Nao foi possivel localizar os dados desta venda.")
            return

        venda_base = linhas[0]
        total = sum(item["quantidade"] * item["preco_unit"] for item in linhas)

        dialog = tk.Toplevel(self)
        dialog.title(f"Editar venda #{num_venda:03d}")
        dialog.configure(bg=theme.FUNDO)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        bind_escape_to_close(dialog)
        configure_styles(dialog)

        frame = Card(dialog, padding=18)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(frame, text=f"Venda #{num_venda:03d}", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(frame, text=f"Total: {moeda(total)}", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 10))

        pagamento_var = tk.StringVar(value=venda_base["pagamento"])
        responsavel_var = tk.StringVar(value=(venda_base["responsavel"] or "").strip())
        bandeira_var = tk.StringVar(value="")
        parcelas_var = tk.StringVar(value="1")
        valor_recebido_var = tk.StringVar(value="")
        troco_var = tk.StringVar(value="")
        detalhe_atual = (venda_base["pagamento_detalhe"] or "").strip()

        if venda_base["pagamento"] in ("Debito", "Credito") and detalhe_atual:
            partes = [parte.strip() for parte in detalhe_atual.split("|") if parte.strip()]
            if partes:
                bandeira_var.set(partes[0])
            if venda_base["pagamento"] == "Credito" and len(partes) > 1 and partes[1].endswith("x"):
                parcelas_var.set(partes[1].replace("x", ""))
        elif venda_base["pagamento"] in ("Debito", "Credito"):
            bandeira_var.set(CARD_BRANDS[0])
        elif venda_base["pagamento"] == "Dinheiro":
            if venda_base["valor_recebido"] is not None:
                valor_recebido_var.set(moeda(float(venda_base["valor_recebido"])))
            if venda_base["troco"] is not None:
                troco_var.set(moeda(float(venda_base["troco"])))
        elif detalhe_atual:
            bandeira_var.set(detalhe_atual)

        form = tk.Frame(frame, bg=theme.BRANCO)
        form.pack(fill="x")
        tk.Label(form, text="Forma de pagamento", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        pagamento_box = ttk.Combobox(form, textvariable=pagamento_var, values=["Debito", "Credito", "Pix", "Dinheiro", "Mais de uma forma"], state="readonly", width=24, font=("Segoe UI", 11))
        pagamento_box.grid(row=1, column=0, sticky="ew", pady=(4, 10))
        form.grid_columnconfigure(0, weight=1)

        detalhe_card = tk.Frame(form, bg=theme.BRANCO)
        detalhe_card.grid(row=2, column=0, sticky="ew")
        bandeira_frame = tk.Frame(detalhe_card, bg=theme.BRANCO)
        parcelas_frame = tk.Frame(detalhe_card, bg=theme.BRANCO)
        dinheiro_frame = tk.Frame(detalhe_card, bg=theme.BRANCO)

        tk.Label(bandeira_frame, text="Bandeira", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        bandeira_box = ttk.Combobox(
            bandeira_frame,
            textvariable=bandeira_var,
            values=CARD_BRANDS,
            state="readonly",
            width=18,
            font=("Segoe UI", 11),
        )
        bandeira_box.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        tk.Label(parcelas_frame, text="Parcelas", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        parcelas_box = ttk.Combobox(
            parcelas_frame,
            textvariable=parcelas_var,
            values=CARD_INSTALLMENTS,
            state="readonly",
            width=10,
            font=("Segoe UI", 11),
        )
        parcelas_box.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        tk.Label(dinheiro_frame, text="Valor recebido", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        valor_recebido_entry = tk.Entry(dinheiro_frame, textvariable=valor_recebido_var, font=("Segoe UI", 11), relief="flat", bg=theme.FUNDO2, fg=theme.TEXTO)
        valor_recebido_entry.grid(row=1, column=0, sticky="ew", ipady=6)
        tk.Label(dinheiro_frame, text="Troco", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=(8, 0))
        troco_entry = tk.Entry(dinheiro_frame, textvariable=troco_var, font=("Segoe UI", 11), relief="flat", bg=theme.FUNDO2, fg=theme.TEXTO)
        troco_entry.grid(row=3, column=0, sticky="ew", ipady=6)

        tk.Label(form, text="Responsavel", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky="w", pady=(10, 0))
        responsavel_entry = tk.Entry(form, textvariable=responsavel_var, font=("Segoe UI", 11), relief="flat", bg=theme.FUNDO2, fg=theme.TEXTO)
        responsavel_entry.grid(row=4, column=0, sticky="ew", ipady=6)

        info_var = tk.StringVar(value="")
        tk.Label(frame, textvariable=info_var, bg=theme.BRANCO, fg=theme.VERMELHO, font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 0))

        def alternar_campos(*_):
            for w in (bandeira_frame, parcelas_frame, dinheiro_frame):
                w.grid_forget()
            tipo = pagamento_var.get()
            if tipo == "Debito":
                bandeira_frame.grid(row=2, column=0, sticky="ew")
                if not bandeira_var.get().strip():
                    bandeira_var.set(CARD_BRANDS[0])
            elif tipo == "Credito":
                bandeira_frame.grid(row=2, column=0, sticky="ew")
                parcelas_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
                if not bandeira_var.get().strip():
                    bandeira_var.set(CARD_BRANDS[0])
                if not parcelas_var.get().strip():
                    parcelas_var.set("1")
            elif tipo == "Dinheiro":
                dinheiro_frame.grid(row=2, column=0, sticky="ew")
            form.update_idletasks()

        pagamento_var.trace_add("write", alternar_campos)
        alternar_campos()

        def confirmar():
            tipo = pagamento_var.get()
            detalhe = ""
            valor_recebido = None
            troco = None
            if tipo == "Debito":
                if not bandeira_var.get().strip():
                    info_var.set("Escolha a bandeira do debito.")
                    return
                detalhe = bandeira_var.get().strip()
            elif tipo == "Credito":
                if not bandeira_var.get().strip():
                    info_var.set("Escolha a bandeira do credito.")
                    return
                detalhe = f"{bandeira_var.get().strip()} | {parcelas_var.get().strip()}x"
            elif tipo == "Dinheiro":
                try:
                    valor_recebido = self._parse_moeda(valor_recebido_var.get())
                except ValueError:
                    info_var.set("Informe o valor recebido em dinheiro.")
                    return
                try:
                    troco = self._parse_moeda(troco_var.get())
                except ValueError:
                    troco = max(valor_recebido - total, 0)
                if troco < 0:
                    info_var.set("Troco nao pode ser negativo.")
                    return
            elif tipo == "Mais de uma forma":
                detalhe = detalhe_atual or "Editar manualmente no historico"

            db.atualizar_venda(self._periodo_id, num_venda, tipo, pagamento_detalhe=detalhe, valor_recebido=valor_recebido, troco=troco, responsavel=responsavel_var.get())
            dialog.destroy()
            self._atualizar_historico()
            self._atualizar_status_fluxo()

        botoes = tk.Frame(frame, bg=theme.BRANCO)
        botoes.pack(fill="x", pady=(14, 0))
        tk.Button(botoes, text="Cancelar", bg=theme.FUNDO2, fg=theme.MUTED, relief="flat", command=dialog.destroy).pack(side="right", padx=(8, 0), ipadx=10, ipady=6)
        tk.Button(botoes, text="Salvar", bg=theme.VERDE_ESC, fg=theme.BRANCO, relief="flat", command=confirmar).pack(side="right", ipadx=10, ipady=6)
        responsavel_entry.focus()
        self.wait_window(dialog)

    # ------------------------------------------------------------------
    # Responsividade e utilitarios de interface
    # ------------------------------------------------------------------
    def _ajustar_layout_responsivo(self, event=None):
        """Reposiciona os paineis quando a janela fica mais estreita."""
        if event is not None and event.widget is not self:
            return
        largura = self.winfo_width()
        altura = self.winfo_height()
        compacto = largura < 760
        compacto_altura = altura < 760
        if compacto_altura != self._compacto_altura:
            self._compacto_altura = compacto_altura
            self._aplicar_compacto_altura(compacto_altura)

        if compacto:
            altura_lateral = max(220, min(300, int(altura * 0.38)))
            self._sale_content.rowconfigure(0, minsize=altura_lateral)
            self._right_panel.configure(width=max(300, largura), height=altura_lateral)
        else:
            minimo_lateral = 270 if largura < 980 else 300
            largura_lateral = max(minimo_lateral, min(360, int(largura * 0.26)))
            self._sale_content.columnconfigure(1, minsize=largura_lateral)
            self._right_panel.configure(width=largura_lateral, height=1)
            self._lbl_pgto_resumo.configure(wraplength=max(220, largura_lateral - 28))

        if compacto == self._layout_compacto:
            return
        self._layout_compacto = compacto

        self._left_panel.grid_forget()
        self._right_separator.grid_forget()
        self._right_panel.grid_forget()
        if compacto:
            self._sale_content.columnconfigure(0, weight=1)
            self._sale_content.columnconfigure(1, weight=0, minsize=0)
            self._sale_content.rowconfigure(0, weight=1)
            self._left_panel.grid(row=0, column=0, sticky="nsew")
            self._right_separator.grid(row=1, column=0, sticky="ew")
            self._right_panel.grid(row=2, column=0, sticky="ew")
        else:
            self._sale_content.columnconfigure(0, weight=1)
            self._sale_content.columnconfigure(1, weight=0)
            self._sale_content.rowconfigure(0, weight=1)
            self._left_panel.grid(row=0, column=0, sticky="nsew")
            self._right_separator.grid(row=0, column=0, sticky="nse")
            self._right_panel.grid(row=0, column=1, sticky="nsew")

    def _aplicar_compacto_altura(self, compacto: bool):
        """Reduz espacos e fontes em alturas menores para preservar usabilidade."""
        if compacto:
            self._topbar.configure(height=54)
            self._topbar_left.pack_configure(padx=14, pady=7)
            self._topbar_right.pack_configure(padx=14, pady=7)
            self._lbl_titulo.configure(font=("Segoe UI", 13, "bold"))
            self._lbl_subtitulo.configure(font=("Segoe UI", 8))
            self._lbl_relogio.configure(font=("Segoe UI", 9))
            self._lbl_data.configure(font=("Segoe UI", 8))
            self._lbl_venda_num.configure(font=("Segoe UI", 8, "bold"), padx=7, pady=2)
            self._lbl_venda_num.pack_configure(pady=(4, 0))

            self._sale_pad.pack_configure(padx=10, pady=8)
            self._search_card.configure(padx=10, pady=8)
            self._search_card.pack_configure(pady=(0, 6))
            self._search_panel.configure(pady=7)
            self._sale_dash.pack_configure(pady=(5, 0))
            self._shortcut_bar.configure(pady=2)
            self._shortcut_bar.pack_configure(pady=(4, 0))
            for kpi in (self._kpi_hoje, self._kpi_vendas, self._kpi_correcoes):
                kpi.configure(padx=8, pady=5)
                kpi.value_label.configure(font=("Segoe UI", 12, "bold"))

            self._card_status.configure(padx=9, pady=7)
            self._card_status.pack_configure(pady=(0, 6))
            self._lbl_status_title.configure(font=("Segoe UI", 10, "bold"))
            self._lbl_status_fluxo.configure(font=("Segoe UI", 8), wraplength=250)
            self._lbl_status_fluxo.pack_configure(pady=(1, 3))
            self._lbl_status_aux.configure(font=("Segoe UI", 8), wraplength=230)
            self._lbl_total.configure(font=("Segoe UI", 17, "bold"))
            self._lbl_forma_pgto.pack_configure(pady=(0, 3))
            self._right_action_bar.configure(padx=8, pady=7)
            self._btn_finalizar.configure(font=("Segoe UI", 10, "bold"), pady=9)
            for botao in self._btns_pgto.values():
                botao.configure(font=("Segoe UI", 8, "bold"), pady=7)
                botao.grid_configure(padx=3, pady=3)
        else:
            self._topbar.configure(height=74)
            self._topbar_left.pack_configure(padx=18, pady=12)
            self._topbar_right.pack_configure(padx=18, pady=12)
            self._lbl_titulo.configure(font=("Segoe UI", 16, "bold"))
            self._lbl_subtitulo.configure(font=("Segoe UI", 10))
            self._lbl_relogio.configure(font=("Segoe UI", 11))
            self._lbl_data.configure(font=("Segoe UI", 9))
            self._lbl_venda_num.configure(font=("Segoe UI", 10, "bold"), padx=10, pady=5)
            self._lbl_venda_num.pack_configure(pady=(8, 0))

            self._sale_pad.pack_configure(padx=18, pady=16)
            self._search_card.configure(padx=16, pady=16)
            self._search_card.pack_configure(pady=(0, 12))
            self._search_panel.configure(pady=16)
            self._sale_dash.pack_configure(pady=(12, 0))
            self._shortcut_bar.configure(pady=4)
            self._shortcut_bar.pack_configure(pady=(8, 0))
            for kpi in (self._kpi_hoje, self._kpi_vendas, self._kpi_correcoes):
                kpi.configure(padx=14, pady=11)
                kpi.value_label.configure(font=FONTES["numero_card"])

            self._card_status.configure(padx=10, pady=9)
            self._card_status.pack_configure(pady=(0, 7))
            self._lbl_status_title.configure(font=("Segoe UI", 11, "bold"))
            self._lbl_status_fluxo.configure(font=("Segoe UI", 9), wraplength=280)
            self._lbl_status_fluxo.pack_configure(pady=(1, 5))
            self._lbl_status_aux.configure(font=("Segoe UI", 9), wraplength=230)
            self._lbl_total.configure(font=("Segoe UI", 20, "bold"))
            self._lbl_forma_pgto.pack_configure(pady=(0, 6))
            self._right_action_bar.configure(padx=10, pady=10)
            self._btn_finalizar.configure(font=("Segoe UI", 12, "bold"), pady=12)
            for botao in self._btns_pgto.values():
                botao.configure(font=("Segoe UI", 10, "bold"), pady=12)
                botao.grid_configure(padx=4, pady=4)

        self._ajustar_scroll_lateral()

    def _atualizar_badge_venda(self):
        """Atualiza o selo com numero do periodo e da venda atual."""
        self._lbl_venda_num.config(text=f"Período {self._periodo_seq:02d}  |  Venda #{self._num_venda:03d}")

    def _atualizar_relogio(self):
        """Atualiza horário e fecha o Período da Loja ao virar a data."""
        agora = datetime.now()
        self._lbl_relogio.config(text=agora.strftime("%H:%M"))
        nova_data = agora.strftime("%d/%m/%Y")
        if nova_data != self._data_hoje and not self._carrinho:
            self._abrir_periodo_para_data(nova_data)
        self._clock_after_id = self.after(30000, self._atualizar_relogio)

    def _focar_busca_inicial(self) -> None:
        self._focus_after_id = None
        if hasattr(self, "_entry_busca") and self._entry_busca.winfo_exists():
            self._entry_busca.focus()

    def destroy(self) -> None:
        """Cancela callbacks pendentes antes de destruir a janela."""
        self._closed = True
        for after_id in (
            self._feedback_after_id,
            self._focus_after_id,
            self._manter_foco_after_id,
            self._clock_after_id,
            self._background_after_id,
            self._search_debounce_id,
            self._sync_after_id,
        ):
            if after_id:
                try:
                    self.after_cancel(after_id)
                except tk.TclError:
                    pass
        self._executor.shutdown(wait=False, cancel_futures=True)
        close_remote_client()
        super().destroy()

    def _add_placeholder(self, entry: tk.Entry, text: str):
        """Simula placeholder em `Entry`, algo nativo ausente no Tkinter."""
        entry.insert(0, text)
        entry.config(fg=theme.MUTED)

        def on_focus_in(_):
            if entry.get() == text:
                entry.delete(0, "end")
                entry.config(fg=theme.TEXTO)

        def on_focus_out(_):
            if not entry.get():
                entry.insert(0, text)
                entry.config(fg=theme.MUTED)

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
