"""
Aplicacao principal do caixa da Loja da Basilica.

Este modulo concentra a interface grafica em Tkinter e orquestra o fluxo
principal do sistema:

1. Inicializa a base local de dados e o estado do caixa.
2. Monta as abas da interface de vendas, historico e estoque.
3. Controla o carrinho, os pagamentos e o fechamento das vendas.
4. Abre e encerra periodos, exporta relatorios e importa produtos.

Dependencias de negocio:
- `database.py`: persistencia, consultas e registro das vendas.
- `relatorio.py`: geracao do arquivo final do periodo.
- `estoque/painel.py`: painel visual de manutencao do estoque.

Execucao: `python main.py`
Requisitos: Python 3.10+, openpyxl
"""

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
"""
Aplicacao principal do caixa da Loja da Basilica.

Este modulo concentra a interface grafica em Tkinter e orquestra o fluxo
principal do sistema:

1. Inicializa a base local de dados e o estado do caixa.
2. Monta as abas da interface de vendas, historico e estoque.
3. Controla o carrinho, os pagamentos e o fechamento das vendas.
4. Abre e encerra periodos, exporta relatorios e importa produtos.

Dependencias de negocio:
- `database.py`: persistencia, consultas e registro das vendas.
- `relatorio.py`: geracao do arquivo final do periodo.
- `estoque/painel.py`: painel visual de manutencao do estoque.

Execucao: `python main.py`
Requisitos: Python 3.10+, openpyxl
"""

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import database as db
import tema as theme
from app.services import backup_service, importacao_service, relatorios_service
from app.ui.importacao_view import ImportacaoGuidedView
from app.ui.relatorios_view import RelatoriosView
from app.ui.vendas_correcoes_view import VendasCorrecoesView
from estoque.dashboard import DashboardEstoque
from estoque.painel import PainelEstoque
from app.ui.components import (
    Card,
    DataTable,
    EmptyState,
    LabeledField,
    PageHeader,
    SearchInput,
    SectionHeader,
    StatusBadge,
    action_button,
    apply_theme_to_widget_tree,
    bind_escape_to_close,
    configure_styles,
)
from tema import (
    FONTES,
    definir_tema_atual,
    moeda,
    obter_nome_tema_atual,
)
BANDEIRAS_CREDITO = ["Visa", "Mastercard", "Elo", "American Express", "Hipercard"]
PARCELAS_CREDITO = [str(i) for i in range(1, 13)]
PLACEHOLDER_BUSCA = "Escaneie o código ou busque pelo nome"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELATORIOS_DIR = PROJECT_ROOT / "relatorios"
BACKUPS_DIR = PROJECT_ROOT / "backups"


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
            tk.Label(bloco, text=texto, bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Entry(bloco, textvariable=var, bg=theme.FUNDO2, fg=theme.TEXTO, relief="flat", width=largura).pack(fill="x", ipady=6)
        ttk.Combobox(
            linha,
            textvariable=self._var_tipo,
            values=["Todos", "ENTRADA", "VENDA", "PERDA", "AJUSTE", "INVENTARIO"],
            state="readonly",
            width=16,
        ).pack(side="left", padx=(0, 10), ipady=3)

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
        self.geometry("1180x720")
        self.minsize(760, 560)
        self.configure(bg=theme.TEMA_ATUAL["fundo"])

        db.inicializar()
        configure_styles(self, obter_nome_tema_atual())

        self._data_hoje = datetime.now().strftime("%d/%m/%Y")
        self._periodo_id = 0
        self._periodo_seq = 1
        self._num_venda = 1
        self._carrinho: list[dict] = []
        self._pagamento: str | None = None
        self._pagamento_detalhe = ""
        self._valor_recebido: float | None = None
        self._troco: float | None = None
        self._vendas_dia = 0
        self._total_dia = 0.0
        self._resultados_busca: list = []
        self._feedback_apos_venda: str | None = None
        self._feedback_after_id: str | None = None
        self._atualizando_responsavel = False
        self._layout_compacto = False

        self._frame_sugestoes: tk.Frame | None = None
        self._lst_sugestoes: tk.Listbox | None = None
        self._historico_tree: ttk.Treeview | None = None
        self._right_canvas: tk.Canvas | None = None
        self._right_window: int | None = None
        self._compacto_altura = False

        self._build_ui()
        self._abrir_periodo_para_data(self._data_hoje)
        self._atualizar_relogio()
        self._atualizar_status_fluxo()

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
        self._notebook.pack(fill="both", expand=True, padx=18, pady=(4, 0))

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

        self._build_left(self._body)
        self._build_right(self._body)
        self._build_footer(self._aba_venda)
        self._build_vendas_correcoes_tab()
        self._build_estoque_tab()
        self._build_importacao_tab()
        self._build_relatorios_tab()
        self._build_configuracoes_tab()
        self._registrar_atalhos_operacionais()
        self.bind("<Configure>", self._ajustar_layout_responsivo)

    def _build_estoque_tab(self):
        """Monta as subabas internas do modulo de estoque."""
        estoque_wrap = tk.Frame(self._aba_estoque, bg=theme.TEMA_ATUAL["fundo"])
        estoque_wrap.pack(fill="both", expand=True)
        self._estoque_notebook = ttk.Notebook(estoque_wrap, style="TNotebook")
        self._estoque_notebook.pack(fill="both", expand=True, padx=18, pady=(0, 0))

        aba_dashboard = tk.Frame(self._estoque_notebook, bg=theme.TEMA_ATUAL["fundo"])
        aba_produtos = tk.Frame(self._estoque_notebook, bg=theme.TEMA_ATUAL["fundo"])
        aba_movimentacoes = tk.Frame(self._estoque_notebook, bg=theme.TEMA_ATUAL["fundo"])
        aba_config = tk.Frame(self._estoque_notebook, bg=theme.TEMA_ATUAL["fundo"])

        self._estoque_notebook.add(aba_dashboard, text="Dashboard")
        self._estoque_notebook.add(aba_produtos, text="Produtos")
        self._estoque_notebook.add(aba_movimentacoes, text="Movimentações")
        self._estoque_notebook.add(aba_config, text="Configurações")

        self._estoque_dashboard = DashboardEstoque(aba_dashboard)
        self._estoque_dashboard.pack(fill="both", expand=True)
        self._estoque_panel = PainelEstoque(aba_produtos)
        self._estoque_panel.pack(fill="both", expand=True)
        self._estoque_movimentacoes = MovimentacoesEstoque(aba_movimentacoes)
        self._estoque_movimentacoes.pack(fill="both", expand=True)
        self._estoque_configuracoes = ConfiguracoesEstoque(aba_config)
        self._estoque_configuracoes.pack(fill="both", expand=True)

    def _build_topbar(self):
        """Cria o cabecalho com titulo, data, horario e numero da venda (Variante A)."""
        bar = tk.Frame(self, bg="#171614", height=74)
        self._topbar = bar
        bar.pack(fill="x")
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg="#171614")
        self._topbar_left = left
        left.pack(side="left", padx=18, pady=12)
        self._lbl_titulo = tk.Label(left, text="Loja da Basilica", bg="#171614", fg="#F7F2E7", font=("Segoe UI", 16, "bold"))
        self._lbl_titulo.pack(anchor="w")
        self._lbl_subtitulo = tk.Label(
            left,
            text="Caixa rápido para a operação diária da loja",
            bg="#171614",
            fg="#C9C0B0",
            font=("Segoe UI", 10),
        )
        self._lbl_subtitulo.pack(anchor="w", pady=(2, 0))

        right = tk.Frame(bar, bg="#171614")
        self._topbar_right = right
        right.pack(side="right", padx=18, pady=12)
        self._lbl_relogio = tk.Label(right, text="--:--", bg="#171614", fg="#F7F2E7", font=("Segoe UI", 11, "bold"))
        self._lbl_relogio.pack(anchor="e")
        self._lbl_data = tk.Label(right, text=self._data_hoje, bg="#171614", fg="#C9C0B0", font=("Segoe UI", 9))
        self._lbl_data.pack(anchor="e")
        self._lbl_venda_num = tk.Label(
            right,
            text="",
            bg="#D5A33B",
            fg="#171614",
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
        pad.pack(fill="both", expand=True, padx=18, pady=16)

        hero = Card(pad, padding=14, bg=theme.FUNDO2)
        hero.pack(fill="x", pady=(0, 12))
        tk.Label(hero, text="Registro de venda (Variante A)", bg=theme.FUNDO2, fg=theme.TEXTO, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(hero, text="Busque pelo nome, código interno ou código de barras para montar a venda.", bg=theme.FUNDO2, fg=theme.MUTED, font=("Segoe UI", 9), wraplength=560, justify="left").pack(anchor="w", pady=(4, 0))

        search_card = Card(pad, padding=12)
        search_card.pack(fill="x", pady=(0, 12))

        search_hdr = tk.Frame(search_card, bg=theme.BRANCO)
        search_hdr.pack(fill="x")
        tk.Label(search_hdr, text="BUSCAR PRODUTO", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(search_hdr, text="[F2]", bg=theme.FUNDO2, fg=theme.MUTED, font=("Segoe UI", 8, "bold"), padx=4, pady=1).pack(side="right")

        self._var_busca = tk.StringVar()
        search = SearchInput(search_card, self._var_busca, "Buscar por nome, código ou código de barras... [F2]")
        search.pack(fill="x", pady=(8, 8))
        self._entry_busca = search.entry
        self._entry_busca.bind("<Return>", self._on_enter_busca)
        self._entry_busca.bind("<Down>", self._focar_sugestao)
        self._entry_busca.bind("<Escape>", lambda _: self._limpar_busca())
        self.after(100, lambda: self._entry_busca.focus() if hasattr(self, "_entry_busca") else None)

        self._frame_sugestoes = tk.Frame(search_card, bg=theme.BRANCO)
        self._lst_sugestoes = tk.Listbox(self._frame_sugestoes, font=("Segoe UI", 10), bg=theme.BRANCO, fg=theme.TEXTO, selectbackground=theme.VERDE_CLAR, selectforeground=theme.VERDE_ESC, relief="flat", activestyle="none", highlightthickness=0)
        self._lst_sugestoes.pack(fill="both", expand=True)
        self._lst_sugestoes.bind("<<ListboxSelect>>", self._on_selecionar_sugestao)
        self._lst_sugestoes.bind("<Return>", self._on_selecionar_sugestao)
        self._lst_sugestoes.bind("<Up>", self._voltar_busca)
        self._var_busca.trace_add("write", self._on_busca)

        hdr = tk.Frame(pad, bg=theme.BRANCO)
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text="ITENS DA VENDA", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9, "bold")).pack(side="left")
        self._lbl_resumo_carrinho = tk.Label(hdr, text="Carrinho vazio", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9))
        self._lbl_resumo_carrinho.pack(side="left", padx=(12, 0))
        self._btn_limpar = tk.Button(hdr, text="Limpar venda", bg=theme.BRANCO, fg=theme.VERMELHO, font=("Segoe UI", 9), relief="flat", cursor="hand2", command=self._limpar_carrinho)
        self._btn_limpar.pack(side="right")
        self._btn_limpar.pack_forget()

        self._frame_vazio = EmptyState(pad, "Carrinho vazio", "Adicione produtos para liberar a seleção de pagamento e a finalização.")
        self._frame_vazio.pack(fill="both", expand=True)

        self._frame_carrinho = tk.Frame(pad, bg=theme.BRANCO)
        self._canvas_cart = tk.Canvas(self._frame_carrinho, bg=theme.BRANCO, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self._frame_carrinho, orient="vertical", command=self._canvas_cart.yview)
        self._canvas_cart.configure(yscrollcommand=scrollbar.set)
        self._canvas_cart.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._inner_cart = tk.Frame(self._canvas_cart, bg=theme.BRANCO)
        self._canvas_window = self._canvas_cart.create_window((0, 0), window=self._inner_cart, anchor="nw")
        self._inner_cart.bind("<Configure>", self._ajustar_scroll_carrinho)
        self._canvas_cart.bind("<Configure>", self._ajustar_largura_carrinho)

        # Atalhos discretos no rodape do painel esquerdo
        bar_atalhos = tk.Frame(pad, bg=theme.FUNDO2, padx=8, pady=4)
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

        self._card_status = Card(pad, padding=16, bg=theme.VERDE_ESC)
        self._card_status.pack(fill="x", pady=(0, 12))
        tk.Label(self._card_status, text="Pr?ximo passo", bg=theme.VERDE_ESC, fg="#CFEBDD", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._lbl_status_fluxo = tk.Label(self._card_status, text="", bg=theme.VERDE_ESC, fg=theme.BRANCO, font=("Segoe UI", 13, "bold"), wraplength=230, justify="left")
        self._lbl_status_fluxo.pack(anchor="w", pady=(8, 4))
        self._lbl_status_aux = tk.Label(self._card_status, text="", bg=theme.VERDE_ESC, fg="#DDF4EA", font=("Segoe UI", 9), wraplength=230, justify="left")
        self._lbl_status_aux.pack(anchor="w")

        card_responsavel = Card(pad, padding=14)
        self._card_responsavel = card_responsavel
        card_responsavel.pack(fill="x", pady=(0, 12))
        tk.Label(card_responsavel, text="RESPONS?VEL DO PER?ODO", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(card_responsavel, text="O nome informado sai no relat?rio exportado.", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 8))
        self._var_responsavel = tk.StringVar()
        self._var_responsavel.trace_add("write", self._salvar_responsavel_periodo)
        self._entry_responsavel = tk.Entry(card_responsavel, textvariable=self._var_responsavel, font=("Segoe UI", 11), relief="flat", bg=theme.FUNDO2, fg=theme.TEXTO, insertbackground=theme.VERDE_ESC, bd=0)
        self._entry_responsavel.pack(fill="x", ipady=8)

        totais = Card(pad, padding=14)
        self._totais_card = totais
        totais.pack(fill="x", pady=(0, 12))

        self._criar_linha_info(totais, "Itens diferentes", "_lbl_n_itens")
        self._criar_linha_info(totais, "Unidades", "_lbl_n_unid")
        self._criar_linha_info(totais, "Pagamento", "_lbl_pgto_resumo")
        self._lbl_pgto_resumo.config(text="Nao selecionado")
        tk.Frame(totais, bg=theme.BORDA, height=1).pack(fill="x", pady=8)

        bloco_total = tk.Frame(totais, bg=theme.BRANCO)
        bloco_total.pack(fill="x")
        tk.Label(bloco_total, text="Total da venda", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 10)).pack(side="left")
        self._lbl_total = tk.Label(bloco_total, text="R$ 0,00", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 20, "bold"))
        self._lbl_total.pack(side="right")

        pagamento_header = tk.Frame(pad, bg=theme.FUNDO)
        pagamento_header.pack(fill="x", pady=(0, 6))
        self._lbl_forma_pgto = tk.Label(pagamento_header, text="FORMA DE PAGAMENTO", bg=theme.FUNDO, fg=theme.MUTED, font=("Segoe UI", 9, "bold"))
        self._lbl_forma_pgto.pack(side="left")
        tk.Label(pagamento_header, text="[F4]", bg=theme.FUNDO2, fg=theme.MUTED, font=("Segoe UI", 8, "bold"), padx=4, pady=1).pack(side="right")

        grid_pgto = tk.Frame(pad, bg=theme.FUNDO)
        self._grid_pgto = grid_pgto
        grid_pgto.pack(fill="x")
        for i in range(2):
            grid_pgto.columnconfigure(i, weight=1, uniform="pgto")
        self._btns_pgto = {}
        pgto_info = [("Debito", "Cart?o de d?bito", 0, 0), ("Credito", "Cart?o de cr?dito", 0, 1), ("Pix", "Pix", 1, 0), ("Dinheiro", "Dinheiro", 1, 1), ("Mais de uma forma", "Mais de uma forma", 2, 0)]
        for nome, texto, row, col in pgto_info:
            btn = action_button(
                grid_pgto,
                text=texto,
                font=("Segoe UI", 10, "bold"),
                bg=theme.BRANCO,
                fg=theme.MUTED,
                padx=12,
                pady=10,
                takefocus=True,
                command=lambda n=nome: self._selecionar_pgto(n),
            )
            btn.configure(activebackground=theme.VERDE_CLAR, activeforeground=theme.VERDE_ESC)
            btn.grid(row=row, column=col, columnspan=2 if nome == "Mais de uma forma" else 1, padx=4, pady=4, sticky="nsew")
            self._btns_pgto[nome] = btn

        self._lbl_ajuda = tk.Label(pad, text="Enter adiciona o item mais prov?vel.", bg=theme.FUNDO, fg=theme.MUTED, font=("Segoe UI", 9))
        self._lbl_ajuda.pack(anchor="w", pady=(10, 0))

    def _build_footer(self, parent):
        """Cria o rodape com indicadores do periodo e acoes globais."""
        tk.Frame(parent, bg=theme.BORDA, height=1).pack(fill="x", side="bottom")
        footer = tk.Frame(parent, bg=theme.BRANCO, height=44)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        acoes_footer = tk.Frame(footer, bg=theme.BRANCO)
        acoes_footer.pack(side="right", padx=12, pady=6)
        stats = tk.Frame(footer, bg=theme.BRANCO)
        stats.pack(side="left", fill="x", expand=True, padx=16, pady=8)
        tk.Label(stats, text="Per?odo", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9)).pack(side="left")
        self._lbl_periodo = tk.Label(stats, text="01", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 9, "bold"))
        self._lbl_periodo.pack(side="left", padx=(4, 16))
        tk.Label(stats, text="Vendas no per?odo", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9)).pack(side="left")
        self._lbl_vendas_dia = tk.Label(stats, text="0", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 9, "bold"))
        self._lbl_vendas_dia.pack(side="left", padx=(4, 16))
        tk.Label(stats, text="Total do per?odo", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 9)).pack(side="left")
        self._lbl_total_dia = tk.Label(stats, text="R$ 0,00", bg=theme.BRANCO, fg=theme.TEXTO, font=("Segoe UI", 9, "bold"))
        self._lbl_total_dia.pack(side="left", padx=(4, 0))

        for label, fg, callback in (
            ("Encerrar dia", theme.VERDE_ESC, self._encerrar_dia),
            ("Exportar relatório", theme.AZUL, self._exportar_relatorio),
            ("Importar produtos", theme.MUTED, self._importar_planilha),
        ):
            tk.Button(acoes_footer, text=label, bg=theme.BRANCO, fg=fg, font=("Segoe UI", 9), relief="flat", cursor="hand2", padx=10, pady=8, command=callback).pack(side="right", padx=(0, 4))

    def _build_vendas_correcoes_tab(self):
        """Monta a aba de Vendas e correções (evoluída de Últimas vendas para Issue #15)."""
        self._vendas_correcoes_view = VendasCorrecoesView(
            self._aba_vendas_correcoes,
            on_sale_updated=self._atualizar_painel_estoque,
        )
        self._vendas_correcoes_view.pack(fill="both", expand=True)

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
        )
        self._relatorios_view.pack(fill="both", expand=True)

    def _build_configuracoes_tab(self):
        """Monta a aba de Configurações e Manutenção (Tema claro/escuro, Backup/Restauração)."""
        pad = tk.Frame(self._aba_configuracoes, bg=theme.TEMA_ATUAL["fundo"], padx=18, pady=16)
        pad.pack(fill="both", expand=True)

        PageHeader(
            pad,
            "Configurações e manutenção",
            "Gerencie preferências visuais de tema, manutenção do banco de dados e backups.",
        ).pack(fill="x", pady=(0, 16))

        # --- SEÇÃO 1: Preferências Gerais / Tema Visual ---
        card_tema = Card(pad, padding=20)
        card_tema.pack(fill="x", pady=(0, 16))

        SectionHeader(
            card_tema,
            "Aparência e Tema Visual",
            "Escolha o tema de cores para a interface do PDV. O Tema Claro é o padrão da operação.",
        ).pack(anchor="w", fill="x", pady=(0, 14))

        box_botoes_tema = tk.Frame(card_tema, bg=theme.TEMA_ATUAL["surface"])
        box_botoes_tema.pack(anchor="w")

        if not hasattr(self, "_var_tema_opcao"):
            self._var_tema_opcao = tk.StringVar(value=obter_nome_tema_atual())
        else:
            self._var_tema_opcao.set(obter_nome_tema_atual())

        for valor_tema, texto_tema in (("claro", "☀️ Tema Claro (Padrão)"), ("escuro", "🌙 Tema Escuro")):
            frame_opcao = tk.Frame(box_botoes_tema, bg=theme.TEMA_ATUAL["surface_2"], padx=12, pady=8)
            frame_opcao.pack(side="left", padx=(0, 12))

            rb = tk.Radiobutton(
                frame_opcao,
                text=texto_tema,
                value=valor_tema,
                variable=self._var_tema_opcao,
                command=lambda t=valor_tema: self._alternar_tema(t),
                bg=theme.TEMA_ATUAL["surface_2"],
                fg=theme.TEMA_ATUAL["texto"],
                activebackground=theme.TEMA_ATUAL["surface_2"],
                activeforeground=theme.TEMA_ATUAL["texto"],
                font=FONTES["corpo_bold"],
                selectcolor=theme.TEMA_ATUAL["surface_2"],
                cursor="hand2",
            )
            rb.pack(side="left", padx=(0, 6))

            if obter_nome_tema_atual() == valor_tema:
                badge = StatusBadge(frame_opcao, "Ativo", bg=theme.TEMA_ATUAL["primary_soft"], fg=theme.TEMA_ATUAL["primary"])
                badge.pack(side="left")

        # --- SEÇÃO 2: Manutenção Sensível e Backup ---
        card_maint = Card(pad, padding=20)
        card_maint.pack(fill="x", pady=(0, 16))

        SectionHeader(
            card_maint,
            "Manutenção e Banco de Dados",
            "Área reservada para geração de backups e restauração do banco de dados SQLite local.",
        ).pack(anchor="w", fill="x", pady=(0, 16))

        # Bloco A: Criar Backup (Apresentação Simples)
        box_criar = tk.Frame(card_maint, bg=theme.TEMA_ATUAL["surface_2"], padx=16, pady=14)
        box_criar.pack(fill="x", pady=(0, 16))

        tk.Label(
            box_criar,
            text="Criar Backup de Segurança",
            bg=theme.TEMA_ATUAL["surface_2"],
            fg=theme.TEMA_ATUAL["texto"],
            font=FONTES["subtitulo"],
        ).pack(anchor="w")

        tk.Label(
            box_criar,
            text="Gera uma cópia imediata do banco de dados na pasta de backups local (backups/). Recomendado antes de manutenções.",
            bg=theme.TEMA_ATUAL["surface_2"],
            fg=theme.TEMA_ATUAL["texto_suave"],
            font=FONTES["corpo"],
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        action_button(
            box_criar,
            text="📦 Criar backup agora",
            command=self._criar_backup,
            bg=theme.TEMA_ATUAL["primary"],
            fg="#FFFFFF",
        ).pack(anchor="w")

        # Bloco B: Restaurar Backup (Linguagem de Risco e Confirmação Forte)
        box_restaurar = tk.Frame(card_maint, bg=theme.TEMA_ATUAL["danger_soft"], padx=16, pady=14)
        box_restaurar.pack(fill="x")

        hdr_restaurar = tk.Frame(box_restaurar, bg=theme.TEMA_ATUAL["danger_soft"])
        hdr_restaurar.pack(fill="x", anchor="w")

        tk.Label(
            hdr_restaurar,
            text="Restaurar Banco de Dados",
            bg=theme.TEMA_ATUAL["danger_soft"],
            fg=theme.TEMA_ATUAL["danger"],
            font=FONTES["subtitulo"],
        ).pack(side="left")

        badge_risco = StatusBadge(hdr_restaurar, "AÇÃO SENSÍVEL DE MANUTENÇÃO", bg=theme.TEMA_ATUAL["danger"], fg="#FFFFFF")
        badge_risco.pack(side="left", padx=(10, 0))

        tk.Label(
            box_restaurar,
            text="⚠️ ATENÇÃO: A restauração de backup substitui todos os dados atuais do caixa (vendas, estoque e histórico) pelas informações do arquivo selecionado. Um backup de segurança do estado atual é criado automaticamente antes da substituição.",
            bg=theme.TEMA_ATUAL["danger_soft"],
            fg=theme.TEMA_ATUAL["texto"],
            font=FONTES["corpo_bold"],
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(8, 12))

        action_button(
            box_restaurar,
            text="⚠️ Restaurar backup a partir de arquivo...",
            command=self._restaurar_backup,
            bg=theme.TEMA_ATUAL["danger"],
            fg="#FFFFFF",
        ).pack(anchor="w")

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
        """Consulta o banco conforme o usuario digita e exibe sugestoes."""
        termo = self._var_busca.get().strip()
        if not termo or termo == PLACEHOLDER_BUSCA:
            self._esconder_sugestoes()
            return

        resultados = db.buscar_produto(termo)
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
        self.after_idle(self._manter_foco_busca)

    def _manter_foco_busca(self):
        """Mantem o cursor no campo de busca apos atualizar a lista."""
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
        self.bind_all("<F4>", self._focar_pagamento)
        self.bind_all("<F8>", self._finalizar_venda_por_atalho)

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
        """Adiciona o item mais provavel ou correspondencia unica quando o operador pressiona Enter."""
        termo = self._var_busca.get().strip()
        if not termo or termo == PLACEHOLDER_BUSCA:
            return

        resultado = db.buscar_produto(termo)
        if resultado:
            for prod in resultado:
                if prod["codigo"] == termo or prod["cod_barras"] == termo:
                    self._adicionar_produto(dict(prod))
                    return
            if len(resultado) == 1:
                self._adicionar_produto(dict(resultado[0]))
                return

        if len(self._resultados_busca) == 1:
            self._adicionar_produto(dict(self._resultados_busca[0]))

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
        """Reconstrui visualmente a lista de itens da venda atual."""
        for widget in self._inner_cart.winfo_children():
            widget.destroy()

        if not self._carrinho:
            self._frame_vazio.pack(fill="both", expand=True)
            self._frame_carrinho.pack_forget()
            self._btn_limpar.pack_forget()
            self._lbl_resumo_carrinho.config(text="Carrinho vazio")
            return

        self._frame_vazio.pack_forget()
        self._frame_carrinho.pack(fill="both", expand=True)
        self._btn_limpar.pack(side="right")
        total_itens = sum(item["quantidade"] for item in self._carrinho)
        self._lbl_resumo_carrinho.config(text=f"{len(self._carrinho)} itens | {total_itens} unidades")

        for item in self._carrinho:
            produto_id = item["produto_id"]
            subtotal = item["quantidade"] * item["preco_unit"]

            row = tk.Frame(self._inner_cart, bg=theme.FUNDO2, padx=10, pady=10)
            row.pack(fill="x", pady=4, padx=2)

            info = tk.Frame(row, bg=theme.FUNDO2)
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=item["nome"], bg=theme.FUNDO2, fg=theme.TEXTO, font=("Segoe UI", 10, "bold"), wraplength=380, justify="left").pack(anchor="w")

            sub_txt = f"Cod. {item['codigo']}  |  {moeda(item['preco_unit'])} por unidade"
            tk.Label(
                info,
                text=sub_txt,
                bg=theme.FUNDO2,
                fg=theme.MUTED,
                font=("Segoe UI", 9),
            ).pack(anchor="w", pady=(2, 0))

            # Alerta de Estoque Baixo (quando restarem 5 unidades ou menos)
            estoque_restante = item.get("estoque")
            if estoque_restante is not None and estoque_restante <= 5:
                tk.Label(
                    info,
                    text=f"⚠️ Estoque baixo: {estoque_restante} produtos restantes",
                    bg=theme.FUNDO2,
                    fg="#C9972C",
                    font=("Segoe UI", 8, "bold"),
                ).pack(anchor="w", pady=(2, 0))

            controls = tk.Frame(row, bg=theme.FUNDO2)
            controls.pack(side="right")
            tk.Label(controls, text=moeda(subtotal), bg=theme.FUNDO2, fg=theme.TEXTO, font=("Segoe UI", 10, "bold"), width=11, anchor="e").pack(
                side="right", padx=(10, 0)
            )

            qty_frame = tk.Frame(controls, bg=theme.FUNDO2)
            qty_frame.pack(side="right")
            tk.Button(
                qty_frame,
                text="-",
                font=("Segoe UI", 11, "bold"),
                bg=theme.BRANCO,
                fg=theme.TEXTO,
                relief="flat",
                cursor="hand2",
                width=2,
                command=lambda p=produto_id: self._alterar_qty(p, -1),
            ).pack(side="left")
            tk.Label(qty_frame, text=str(item["quantidade"]), bg=theme.FUNDO2, fg=theme.TEXTO, font=("Segoe UI", 10, "bold"), width=3).pack(
                side="left"
            )
            tk.Button(
                qty_frame,
                text="+",
                font=("Segoe UI", 11, "bold"),
                bg=theme.BRANCO,
                fg=theme.TEXTO,
                relief="flat",
                cursor="hand2",
                width=2,
                command=lambda p=produto_id: self._alterar_qty(p, 1),
            ).pack(side="left")

            tk.Button(
                controls,
                text="Remover",
                font=("Segoe UI", 8),
                bg=theme.FUNDO2,
                fg=theme.MUTED,
                relief="flat",
                cursor="hand2",
                command=lambda p=produto_id: self._remover_item(p),
            ).pack(side="right", padx=(0, 10))

    def _atualizar_totais(self):
        """Recalcula subtotal, quantidade, resumo de pagamento e status."""
        total = sum(item["quantidade"] * item["preco_unit"] for item in self._carrinho)
        itens = len(self._carrinho)
        unidades = sum(item["quantidade"] for item in self._carrinho)

        self._lbl_total.config(text=moeda(total))
        self._lbl_n_itens.config(text=str(itens))
        self._lbl_n_unid.config(text=str(unidades))
        self._lbl_pgto_resumo.config(text=self._resumo_pagamento())
        self._atualizar_btn_finalizar()
        self._atualizar_status_fluxo()

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
        for forma, botao in self._btns_pgto.items():
            if forma == nome:
                botao.config(bg=theme.PGTO_BG[nome], fg=theme.PGTO_FG[nome], relief="solid", bd=2)
            else:
                botao.config(bg=theme.BRANCO, fg=theme.MUTED, relief="flat", bd=0)
        self._atualizar_totais()

    def _resetar_btns_pgto(self):
        """Desmarca visualmente os botoes de pagamento."""
        self._limpar_pagamento()
        for botao in self._btns_pgto.values():
            botao.config(bg=theme.BRANCO, fg=theme.MUTED, relief="flat", bd=0)
        self._atualizar_totais()

    def _limpar_pagamento(self):
        """Apaga os dados temporarios ligados ao pagamento da venda."""
        self._pagamento = None
        self._pagamento_detalhe = ""
        self._valor_recebido = None
        self._troco = None

    def _total_carrinho(self) -> float:
        """Retorna o total monetario da venda em andamento."""
        return sum(item["quantidade"] * item["preco_unit"] for item in self._carrinho)

    def _resumo_pagamento(self) -> str:
        """Gera o texto resumido exibido na lateral e no historico."""
        if not self._pagamento:
            return "Nao selecionado"
        if self._pagamento in ("Debito", "Credito") and self._pagamento_detalhe:
            return f"{self._pagamento} | {self._pagamento_detalhe}"
        if self._pagamento == "Dinheiro" and self._valor_recebido is not None and self._troco is not None:
            return f"Dinheiro | Recebido {moeda(self._valor_recebido)} | Troco {moeda(self._troco)}"
        if self._pagamento == "Mais de uma forma" and self._pagamento_detalhe:
            return self._pagamento_detalhe
        return self._pagamento

    def _parse_moeda(self, texto: str) -> float:
        """Interpreta textos como `10`, `10,50` ou `R$ 10,50`."""
        texto = texto.strip().replace("R$", "").replace(" ", "")
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        return float(texto)

    def _coletar_dinheiro(self) -> bool:
        """Abre um dialog para valor recebido e calculo de troco."""
        total = self._total_carrinho()
        dialog = tk.Toplevel(self)
        dialog.title("Pagamento em dinheiro")
        dialog.configure(bg=theme.FUNDO)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
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
        entrada.focus()
        self.wait_window(dialog)

        if not resultado["ok"]:
            return False
        self._pagamento_detalhe = f"Recebido {moeda(resultado['valor'])}; troco {moeda(resultado['troco'])}"
        self._valor_recebido = resultado["valor"]
        self._troco = resultado["troco"]
        return True

    def _coletar_pagamento_misto(self) -> bool:
        """Coleta um pagamento composto por duas ou mais formas."""
        dialog = tk.Toplevel(self)
        dialog.title("Mais de uma forma")
        dialog.configure(bg=theme.FUNDO)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        bind_escape_to_close(dialog)

        frame = tk.Frame(dialog, bg=theme.FUNDO, padx=18, pady=16)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Selecione duas formas de pagamento", bg=theme.FUNDO, fg=theme.TEXTO, font=("Segoe UI", 13, "bold")).pack(
            anchor="w"
        )
        tk.Label(frame, text="O detalhe aparecera no historico e na planilha.", bg=theme.FUNDO, fg=theme.MUTED, font=("Segoe UI", 10)).pack(
            anchor="w", pady=(4, 10)
        )

        vars_pgto = {forma: tk.BooleanVar(value=False) for forma in FORMAS_PGTO}
        detalhes_cartao = {}

        def detalhe_texto(forma: str) -> str:
            info = detalhes_cartao.get(forma, {})
            if forma == "Debito":
                bandeira = info.get("bandeira", BANDEIRAS_DEBITO[0])
                return f"{bandeira}"
            if forma == "Credito":
                bandeira = info.get("bandeira", BANDEIRAS_CREDITO[0])
                parcelas = info.get("parcelas", "1")
                return f"{bandeira} | {parcelas}x"
            return ""

        def atualizar_visibilidade(forma: str):
            info = detalhes_cartao.get(forma)
            if not info:
                return
            if vars_pgto[forma].get():
                info["card"].pack(fill="x", pady=(0, 2))
            else:
                info["card"].pack_forget()

        for forma in FORMAS_PGTO:
            linha = tk.Frame(frame, bg=theme.FUNDO)
            linha.pack(fill="x", pady=2)

            check = tk.Checkbutton(
                linha,
                text=forma,
                variable=vars_pgto[forma],
                bg=theme.FUNDO,
                fg=theme.TEXTO,
                selectcolor=theme.BRANCO,
                activebackground=theme.FUNDO,
                font=("Segoe UI", 11),
                command=lambda f=forma: atualizar_visibilidade(f),
            )
            check.pack(side="left", anchor="w")

            if forma in ("Debito", "Credito"):
                detalhe_card = tk.Frame(linha, bg=theme.FUNDO2, padx=10, pady=8)
                detalhes_cartao[forma] = {"card": detalhe_card}

                bandeira_var = tk.StringVar(value=(BANDEIRAS_DEBITO[0] if forma == "Debito" else BANDEIRAS_CREDITO[0]))
                detalhes_cartao[forma]["bandeira_var"] = bandeira_var
                tk.Label(
                    detalhe_card,
                    text="Bandeira",
                    bg=theme.FUNDO2,
                    fg=theme.MUTED,
                    font=("Segoe UI", 8, "bold"),
                ).grid(row=0, column=0, sticky="w")
                bandeira_box = ttk.Combobox(
                    detalhe_card,
                    textvariable=bandeira_var,
                    values=BANDEIRAS_DEBITO if forma == "Debito" else BANDEIRAS_CREDITO,
                    state="readonly",
                    width=13,
                    font=("Segoe UI", 10),
                )
                bandeira_box.grid(row=1, column=0, padx=(0, 8), pady=(2, 0), sticky="w")

                if forma == "Credito":
                    parcela_var = tk.StringVar(value="1")
                    detalhes_cartao[forma]["parcelas_var"] = parcela_var
                    tk.Label(
                        detalhe_card,
                        text="Parcelas",
                        bg=theme.FUNDO2,
                        fg=theme.MUTED,
                        font=("Segoe UI", 8, "bold"),
                    ).grid(row=0, column=1, sticky="w")
                    parcela_box = ttk.Combobox(
                        detalhe_card,
                        textvariable=parcela_var,
                        values=PARCELAS_CREDITO,
                        state="readonly",
                        width=7,
                        font=("Segoe UI", 10),
                    )
                    parcela_box.grid(row=1, column=1, pady=(2, 0), sticky="w")

                detalhe_card.pack_forget()
                detalhe_card.grid_columnconfigure(0, weight=0)
                detalhe_card.grid_columnconfigure(1, weight=0)
                detalhe_card.pack_configure(anchor="e")
                info_box = tk.Frame(linha, bg=theme.FUNDO)
                info_box.pack(side="right")
                tk.Label(
                    info_box,
                    text="",
                    bg=theme.FUNDO,
                    fg=theme.VERDE_ESC,
                    font=("Segoe UI", 8, "bold"),
                ).pack()
                detalhes_cartao[forma]["info_box"] = info_box
                detalhe_card.pack(side="right", padx=(8, 0))
                atualizar_visibilidade(forma)
            else:
                tk.Frame(linha, bg=theme.FUNDO).pack(side="right")

        erro_var = tk.StringVar(value="")
        tk.Label(frame, textvariable=erro_var, bg=theme.FUNDO, fg=theme.VERMELHO, font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 0))
        resultado = {"ok": False, "detalhe": ""}

        def confirmar():
            selecionadas = [forma for forma, var in vars_pgto.items() if var.get()]
            if len(selecionadas) < 2:
                erro_var.set("Selecione pelo menos duas formas.")
                return
            partes = []
            for forma in selecionadas:
                if forma in ("Debito", "Credito"):
                    detalhe = detalhe_texto(forma)
                    partes.append(f"{forma} ({detalhe})" if detalhe else forma)
                else:
                    partes.append(forma)
            resultado.update({"ok": True, "detalhe": " + ".join(partes)})
            dialog.destroy()

        botoes = tk.Frame(frame, bg=theme.FUNDO)
        botoes.pack(fill="x", pady=(14, 0))
        tk.Button(botoes, text="Cancelar", bg=theme.FUNDO2, fg=theme.MUTED, relief="flat", command=dialog.destroy).pack(
            side="right", padx=(8, 0), ipadx=10, ipady=6
        )
        tk.Button(botoes, text="Confirmar", bg=theme.VERDE_ESC, fg=theme.BRANCO, relief="flat", command=confirmar).pack(
            side="right", ipadx=10, ipady=6
        )
        self.wait_window(dialog)

        if not resultado["ok"]:
            return False
        self._pagamento_detalhe = resultado["detalhe"]
        self._valor_recebido = None
        self._troco = None
        return True

    def _coletar_bandeira(self, tipo: str) -> bool:
        """Solicita bandeira e, no credito, quantidade de parcelas."""
        bandeiras = BANDEIRAS_DEBITO if tipo == "Debito" else BANDEIRAS_CREDITO
        dialog = tk.Toplevel(self)
        dialog.title("Bandeira do cartao")
        dialog.configure(bg=theme.FUNDO)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        bind_escape_to_close(dialog)

        frame = tk.Frame(dialog, bg=theme.FUNDO, padx=18, pady=16)
        frame.pack(fill="both", expand=True)
        titulo = "Escolha a bandeira do cartao de debito" if tipo == "Debito" else "Escolha a bandeira do cartao de credito"
        tk.Label(frame, text=titulo, bg=theme.FUNDO, fg=theme.TEXTO, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(
            frame,
            text="A bandeira sera registrada na venda e na planilha.",
            bg=theme.FUNDO,
            fg=theme.MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 10))

        escolhida = tk.StringVar(value=bandeiras[0])
        linha = tk.Frame(frame, bg=theme.FUNDO)
        linha.pack(fill="x")
        for bandeira in bandeiras:
            tk.Radiobutton(
                linha,
                text=bandeira,
                value=bandeira,
                variable=escolhida,
                bg=theme.FUNDO,
                fg=theme.TEXTO,
                selectcolor=theme.BRANCO,
                activebackground=theme.FUNDO,
                font=("Segoe UI", 11),
                anchor="w",
            ).pack(fill="x", pady=2)

        parcela_var = tk.StringVar(value="1")
        if tipo == "Credito":
            tk.Label(frame, text="Quantidade de parcelas", bg=theme.FUNDO, fg=theme.MUTED, font=("Segoe UI", 10, "bold")).pack(
                anchor="w", pady=(12, 4)
            )
            parcela_box = ttk.Combobox(
                frame,
                textvariable=parcela_var,
                values=PARCELAS_CREDITO,
                state="readonly",
                width=8,
                font=("Segoe UI", 11),
            )
            parcela_box.pack(anchor="w")
            parcela_box.set("1")

        resultado = {"ok": False}

        def confirmar():
            resultado["ok"] = True
            dialog.destroy()

        botoes = tk.Frame(frame, bg=theme.FUNDO)
        botoes.pack(fill="x", pady=(14, 0))
        tk.Button(botoes, text="Cancelar", bg=theme.FUNDO2, fg=theme.MUTED, relief="flat", command=dialog.destroy).pack(
            side="right", padx=(8, 0), ipadx=10, ipady=6
        )
        tk.Button(botoes, text="Confirmar", bg=theme.VERDE_ESC, fg=theme.BRANCO, relief="flat", command=confirmar).pack(
            side="right", ipadx=10, ipady=6
        )
        self.wait_window(dialog)

        if not resultado["ok"]:
            return False
        detalhe = escolhida.get().strip()
        if tipo == "Credito":
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
        if self._feedback_apos_venda:
            self._lbl_status_fluxo.config(text=self._feedback_apos_venda)
            self._lbl_status_aux.config(text="O caixa já está pronto para registrar a venda seguinte.")
            return

        # Verifica se algum item no carrinho possui estoque baixo (<= 5)
        item_baixo = next((i for i in self._carrinho if i.get("estoque") is not None and i.get("estoque") <= 5), None)

        if not self._carrinho:
            self._lbl_status_fluxo.config(text="Adicione os produtos da venda.")
            self._lbl_status_aux.config(text="Depois escolha a forma de pagamento para liberar a finalização.")
            return
        if not self._pagamento:
            self._lbl_status_fluxo.config(text="Escolha a forma de pagamento.")
            if item_baixo:
                self._lbl_status_aux.config(text=f"⚠️ Atenção: {item_baixo['nome']} tem {item_baixo['estoque']} produtos restantes.")
            else:
                self._lbl_status_aux.config(text=f"Venda parcial em {moeda(self._total_carrinho())}.")
            return

        self._lbl_status_fluxo.config(text="Venda pronta para finalizar.")
        if item_baixo:
            self._lbl_status_aux.config(text=f"Pagamento: {self._resumo_pagamento()} (⚠️ {item_baixo['estoque']} produtos restantes).")
        else:
            self._lbl_status_aux.config(text=f"Pagamento selecionado: {self._resumo_pagamento()}.")

    def _responsavel_atual(self) -> str:
        """Retorna o nome do responsavel vinculado ao periodo atual."""
        return self._var_responsavel.get().strip()

    def _salvar_responsavel_periodo(self, *_):
        """Persiste automaticamente o responsavel quando o campo muda."""
        if self._atualizando_responsavel or not self._periodo_id:
            return
        db.atualizar_responsavel_periodo(self._periodo_id, self._responsavel_atual())

    # ------------------------------------------------------------------
    # Periodos e vendas
    # ------------------------------------------------------------------
    def _abrir_periodo_para_data(self, data: str):
        """Carrega ou cria o periodo aberto correspondente a uma data."""
        periodo = db.obter_ou_criar_periodo_aberto(data)
        totais = db.totais_periodo(periodo["id"])

        self._data_hoje = periodo["data"]
        self._periodo_id = periodo["id"]
        self._periodo_seq = periodo["sequencia"]
        self._num_venda = db.proximo_num_venda(self._periodo_id)
        self._vendas_dia = totais["transacoes"]
        self._total_dia = totais["total"]

        self._lbl_data.config(text=self._data_hoje)
        self._lbl_periodo.config(text=f"{self._periodo_seq:02d}")
        self._lbl_vendas_dia.config(text=str(self._vendas_dia))
        self._lbl_total_dia.config(text=moeda(self._total_dia))

        self._atualizando_responsavel = True
        self._var_responsavel.set(periodo["responsavel"] or "")
        self._atualizando_responsavel = False

        self._atualizar_badge_venda()
        self._atualizar_totais()
        self._atualizar_historico()

    def _finalizar_venda(self):
        """Grava a venda, atualiza indicadores e prepara o proximo atendimento."""
        if not self._carrinho or not self._pagamento:
            return

        total = self._total_carrinho()
        numero_venda = self._num_venda
        pagamento = self._resumo_pagamento()
        db.registrar_venda(
            self._periodo_id,
            self._num_venda,
            self._carrinho,
            self._pagamento,
            pagamento_detalhe=self._pagamento_detalhe,
            valor_recebido=self._valor_recebido,
            troco=self._troco,
            responsavel=self._responsavel_atual(),
            data=self._data_hoje,
        )

        self._vendas_dia += 1
        self._total_dia += total
        self._lbl_vendas_dia.config(text=str(self._vendas_dia))
        self._lbl_total_dia.config(text=moeda(self._total_dia))

        self._nova_venda()
        self._atualizar_historico()
        self._atualizar_painel_estoque()
        self._mostrar_feedback_venda(
            f"Venda #{numero_venda:03d} registrada por {moeda(total)} em {pagamento}."
        )

    def _nova_venda(self):
        """Reseta a tela para iniciar uma nova venda no mesmo periodo."""
        if self._feedback_after_id:
            self.after_cancel(self._feedback_after_id)
            self._feedback_after_id = None
        self._num_venda = db.proximo_num_venda(self._periodo_id)
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

        return relatorios_service.gerar_relatorio_periodo(
            self._periodo_id,
            pasta_saida,
            responsavel=periodo["responsavel"] or self._responsavel_atual(),
        )

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
        """Fecha o periodo atual, exporta o relatorio e inicia outro periodo."""
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

        caminho = self._exportar_periodo(str(RELATORIOS_DIR))
        teve_vendas = caminho is not None

        db.encerrar_periodo(self._periodo_id)
        self._abrir_periodo_para_data(datetime.now().strftime("%d/%m/%Y"))
        self._mostrar_feedback_venda(f"Periodo {self._periodo_seq:02d} pronto para novas vendas.")

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
            resultado = importacao_service.importar(arquivo, modo)
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
            caminho = backup_service.criar_backup(db.DB_PATH, BACKUPS_DIR)
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
            anterior = backup_service.restaurar_backup(caminho, db.DB_PATH, BACKUPS_DIR)
            db.inicializar()
            self._abrir_periodo_para_data(datetime.now().strftime("%d/%m/%Y"))
            self._atualizar_painel_estoque()
            self._atualizar_historico()
            detalhe = f"\n\nBackup de segurança gerado antes da restauração:\n{anterior.name}" if anterior else ""
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
            self._vendas_correcoes_view.atualizar()

    def _atualizar_painel_estoque(self):
        """Sincroniza a aba de estoque apos vendas ou importacoes."""
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
            bandeira_var.set(BANDEIRAS_CREDITO[0])
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
        bandeira_box = ttk.Combobox(bandeira_frame, textvariable=bandeira_var, values=BANDEIRAS_CREDITO, state="readonly", width=18, font=("Segoe UI", 11))
        bandeira_box.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        tk.Label(parcelas_frame, text="Parcelas", bg=theme.BRANCO, fg=theme.MUTED, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        parcelas_box = ttk.Combobox(parcelas_frame, textvariable=parcelas_var, values=PARCELAS_CREDITO, state="readonly", width=10, font=("Segoe UI", 11))
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
                    bandeira_var.set(BANDEIRAS_DEBITO[0])
            elif tipo == "Credito":
                bandeira_frame.grid(row=2, column=0, sticky="ew")
                parcelas_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
                if not bandeira_var.get().strip():
                    bandeira_var.set(BANDEIRAS_CREDITO[0])
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
        compacto = self.winfo_width() < 980
        compacto_altura = self.winfo_height() < 760
        if compacto_altura != self._compacto_altura:
            self._compacto_altura = compacto_altura
            self._aplicar_compacto_altura(compacto_altura)

        if compacto == self._layout_compacto:
            return
        self._layout_compacto = compacto

        self._left_panel.grid_forget()
        self._right_separator.grid_forget()
        self._right_panel.grid_forget()
        if compacto:
            self._body.columnconfigure(0, weight=1)
            self._body.columnconfigure(1, weight=0, minsize=0)
            self._body.rowconfigure(0, weight=1)
            self._body.rowconfigure(1, weight=0)
            self._body.rowconfigure(2, weight=0, minsize=260)
            self._left_panel.grid(row=0, column=0, sticky="nsew")
            self._right_separator.grid(row=1, column=0, sticky="ew")
            self._right_panel.configure(width=300, height=260)
            self._right_panel.grid(row=2, column=0, sticky="ew")
        else:
            self._body.columnconfigure(0, weight=1)
            self._body.columnconfigure(1, weight=0, minsize=300)
            self._body.rowconfigure(0, weight=1)
            self._body.rowconfigure(1, weight=0)
            self._body.rowconfigure(2, weight=0, minsize=0)
            self._left_panel.grid(row=0, column=0, sticky="nsew")
            self._right_separator.grid(row=0, column=0, sticky="nse")
            self._right_panel.configure(width=300, height=1)
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

            self._card_status.configure(padx=10, pady=9)
            self._card_status.pack_configure(pady=(0, 7))
            self._lbl_status_fluxo.configure(font=("Segoe UI", 10, "bold"), wraplength=230)
            self._lbl_status_fluxo.pack_configure(pady=(4, 2))
            self._lbl_status_aux.configure(font=("Segoe UI", 8), wraplength=230)
            self._card_responsavel.configure(padx=10, pady=8)
            self._card_responsavel.pack_configure(pady=(0, 7))
            self._entry_responsavel.pack_configure(ipady=5)
            self._totais_card.configure(padx=10, pady=9)
            self._totais_card.pack_configure(pady=(0, 7))
            self._lbl_total.configure(font=("Segoe UI", 17, "bold"))
            self._lbl_forma_pgto.pack_configure(pady=(0, 3))
            self._right_action_bar.configure(padx=8, pady=7)
            self._btn_finalizar.configure(font=("Segoe UI", 10, "bold"), pady=9)
            self._lbl_ajuda.pack_forget()
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

            self._card_status.configure(padx=16, pady=16)
            self._card_status.pack_configure(pady=(0, 12))
            self._lbl_status_fluxo.configure(font=("Segoe UI", 13, "bold"), wraplength=230)
            self._lbl_status_fluxo.pack_configure(pady=(8, 4))
            self._lbl_status_aux.configure(font=("Segoe UI", 9), wraplength=230)
            self._card_responsavel.configure(padx=14, pady=12)
            self._card_responsavel.pack_configure(pady=(0, 12))
            self._entry_responsavel.pack_configure(ipady=8)
            self._totais_card.configure(padx=14, pady=14)
            self._totais_card.pack_configure(pady=(0, 12))
            self._lbl_total.configure(font=("Segoe UI", 20, "bold"))
            self._lbl_forma_pgto.pack_configure(pady=(0, 6))
            self._right_action_bar.configure(padx=10, pady=10)
            self._btn_finalizar.configure(font=("Segoe UI", 12, "bold"), pady=12)
            self._lbl_ajuda.pack(anchor="w", pady=(10, 0))
            for botao in self._btns_pgto.values():
                botao.configure(font=("Segoe UI", 10, "bold"), pady=12)
                botao.grid_configure(padx=4, pady=4)

        self._ajustar_scroll_lateral()

    def _atualizar_badge_venda(self):
        """Atualiza o selo com numero do periodo e da venda atual."""
        self._lbl_venda_num.config(text=f"Periodo {self._periodo_seq:02d}  |  Venda #{self._num_venda:03d}")

    def _atualizar_relogio(self):
        """Atualiza o horario visivel e troca o periodo quando vira o dia."""
        agora = datetime.now()
        self._lbl_relogio.config(text=agora.strftime("%H:%M"))
        nova_data = agora.strftime("%d/%m/%Y")
        if nova_data != self._data_hoje and not self._carrinho:
            self._abrir_periodo_para_data(nova_data)
        self.after(30000, self._atualizar_relogio)

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
