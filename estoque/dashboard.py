"""Dashboard gerencial do modulo de estoque."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import database as db
from app.ui.components import Card, DataTable, EmptyState, PageHeader
from tema import AZUL, BRANCO, COLORS, ESPACOS, FONTES, FUNDO, MUTED, TEXTO, VERDE_ESC, VERMELHO, moeda

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except Exception:  # pragma: no cover - depende do ambiente grafico local
    Figure = None
    FigureCanvasTkAgg = None


def criar_figura(titulo: str, largura: float = 4.1, altura: float = 2.9):
    """Cria uma figura padronizada para os graficos do dashboard."""
    figura = Figure(figsize=(largura, altura), dpi=92)
    figura.patch.set_facecolor(BRANCO)
    ax = figura.add_subplot(111)
    ax.set_title(titulo, fontsize=10, fontweight="bold", color=TEXTO, pad=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["border_subtle"])
    ax.spines["bottom"].set_color(COLORS["border_subtle"])
    ax.set_facecolor(BRANCO)
    return figura


def renderizar_grafico(frame, figure):
    """Renderiza a figura matplotlib dentro do frame informado."""
    canvas = FigureCanvasTkAgg(figure, master=frame)
    widget = canvas.get_tk_widget()
    widget.pack(fill="both", expand=True)
    canvas.draw()
    return canvas


class DashboardEstoque(tk.Frame):
    """Tela de dashboard do estoque."""

    KPI_SPECS = (
        ("skus_ativos", "SKUs ativos", "Produtos ativos cadastrados", "BX", "green"),
        ("produtos_criticos", "Alertas críticos", "Estoque no mínimo ou abaixo", "!", "red"),
        ("valor_total_venda", "Valor a venda", "Potencial bruto de venda", "$", "green"),
        ("produtos_alerta", "Itens baixo estoque", "Abaixo do ponto de pedido", "~", "amber"),
        ("sem_custo", "Sem custo cadastrado", "Produtos sem custo unitário", "C", "amber"),
        ("sem_estoque_minimo", "Sem mínimo definido", "Cadastro pendente de parâmetro", "M", "gray"),
    )

    ICON_VARIANTS = {
        "green": (COLORS["success_bg"], COLORS["success_dot"]),
        "red": (COLORS["danger_bg"], COLORS["danger_dot"]),
        "amber": (COLORS["warning_bg"], COLORS["warning_dot"]),
        "blue": (COLORS["info_bg"], COLORS["info_dot"]),
        "gray": (COLORS["bg_secondary"], COLORS["text_tertiary"]),
    }

    def __init__(self, parent):
        super().__init__(parent, bg=FUNDO)
        self._cards: dict[str, tk.Label] = {}
        self._graficos_frame: tk.Frame | None = None
        self._acoes_tree: ttk.Treeview | None = None
        self._canvas: tk.Canvas | None = None
        self._scroll_widgets: set[str] = set()
        self._build_ui()
        self.atualizar()

    def _build_ui(self):
        PageHeader(
            self,
            "Dashboard de estoque",
            "Visão rápida de saldo, risco e valor acumulado dos produtos.",
            "Atualizar dashboard",
            self.atualizar,
        ).pack(fill="x", padx=ESPACOS["xl"], pady=(ESPACOS["xl"], 12))

        self._canvas = tk.Canvas(self, bg=FUNDO, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scroll.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._conteudo = tk.Frame(self._canvas, bg=FUNDO, padx=ESPACOS["xl"], pady=0)
        self._window = self._canvas.create_window((0, 0), window=self._conteudo, anchor="nw")
        self._conteudo.bind("<Configure>", lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda event: self._canvas.itemconfigure(self._window, width=event.width))
        self._bind_mousewheel_recursivo(self._canvas)

        self._cards_frame = tk.Frame(self._conteudo, bg=FUNDO)
        self._cards_frame.pack(fill="x", pady=(0, ESPACOS["md"]))
        for idx, spec in enumerate(self.KPI_SPECS):
            self._criar_card(self._cards_frame, *spec, idx=idx)

        self._graficos_frame = tk.Frame(self._conteudo, bg=FUNDO)
        self._graficos_frame.pack(fill="both", expand=True, pady=(4, 0))

        tk.Label(
            self._conteudo,
            text="Produtos que exigem ação",
            bg=FUNDO,
            fg=TEXTO,
            font=FONTES["secao"],
        ).pack(anchor="w", pady=(ESPACOS["lg"], 8))

        tabela_card = Card(self._conteudo, padding=0)
        tabela_card.pack(fill="both", expand=True, pady=(0, ESPACOS["xl"]))
        colunas = ("codigo", "produto", "status", "estoque", "minimo", "valor")
        titulos = {
            "codigo": "Cód.",
            "produto": "Produto",
            "status": "Status",
            "estoque": "Estoque",
            "minimo": "Mínimo",
            "valor": "Valor a custo",
        }
        larguras = {"codigo": 90, "produto": 380, "status": 120, "estoque": 90, "minimo": 90, "valor": 140}
        self._acoes_tree = DataTable(tabela_card, colunas, titulos, larguras, height=8)
        self._acoes_tree.column("produto", anchor="w")
        self._acoes_tree.pack(side="left", fill="both", expand=True)
        scroll_tree = ttk.Scrollbar(tabela_card, orient="vertical", command=self._acoes_tree.yview)
        self._acoes_tree.configure(yscrollcommand=scroll_tree.set)
        scroll_tree.pack(side="right", fill="y")
        self._bind_mousewheel_recursivo(self._conteudo)

    def _criar_card(
        self,
        parent: tk.Frame,
        chave: str,
        titulo: str,
        subtitulo: str,
        icon_text: str,
        icon_variant: str,
        *,
        idx: int,
    ):
        card = Card(parent, padding=14)
        card.grid(row=idx // 3, column=idx % 3, sticky="nsew", padx=(0, 10), pady=(0, 10))
        parent.columnconfigure(idx % 3, weight=1)

        icon_bg, icon_fg = self.ICON_VARIANTS[icon_variant]
        icon_box = tk.Frame(card, bg=icon_bg, width=40, height=40)
        icon_box.pack(side="left", padx=(0, 14))
        icon_box.pack_propagate(False)
        tk.Label(icon_box, text=icon_text, bg=icon_bg, fg=icon_fg, font=(FONTES["titulo"][0], 13, "bold")).pack(expand=True)

        content = tk.Frame(card, bg=BRANCO)
        content.pack(side="left", fill="both", expand=True)
        tk.Label(content, text=titulo, bg=BRANCO, fg=COLORS["text_tertiary"], font=FONTES["label"]).pack(anchor="w")
        value = tk.Label(content, text="0", bg=BRANCO, fg=TEXTO, font=FONTES["numero_card_lg"])
        value.pack(anchor="w", pady=(4, 0))
        tk.Label(content, text=subtitulo, bg=BRANCO, fg=MUTED, font=FONTES["corpo"]).pack(anchor="w", pady=(2, 0))
        self._cards[chave] = value

    def atualizar(self):
        resumo = db.dashboard_resumo_estoque()
        for chave, label in self._cards.items():
            valor = resumo.get(chave, 0)
            label.config(text=moeda(valor) if chave.startswith("valor_") else str(valor))
            if chave in {"produtos_criticos", "sem_custo"}:
                label.config(fg=VERMELHO)
            elif chave in {"valor_total_venda", "skus_ativos"}:
                label.config(fg=VERDE_ESC)
            elif chave in {"produtos_alerta", "sem_estoque_minimo"}:
                label.config(fg=COLORS["warning_dot"])
        self._renderizar_graficos()
        self._renderizar_acoes(resumo.get("produtos_acao", []))

    def _limpar_frame(self, frame: tk.Frame):
        for child in frame.winfo_children():
            child.destroy()

    def _card_grafico(self, parent: tk.Frame, titulo: str):
        frame = Card(parent, padding=10)
        frame.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=(0, 10))
        if Figure is None or FigureCanvasTkAgg is None:
            EmptyState(frame, "Gráfico indisponível", "Instale matplotlib para visualizar esta análise.").pack(fill="both", expand=True)
            return frame, None
        return frame, criar_figura(titulo)

    def _renderizar_graficos(self):
        if not self._graficos_frame:
            return
        self._limpar_frame(self._graficos_frame)

        linhas = [
            (("Distribuição por status", self._grafico_status), ("Curva ABC", self._grafico_abc)),
            (("Valor por categoria", self._grafico_categorias), ("Top valor a custo", self._grafico_valor_parado)),
            (("Top vendidos 30 dias", self._grafico_vendidos), ("Entradas x saídas", self._grafico_movimentos)),
        ]
        for linha in linhas:
            linha_frame = tk.Frame(self._graficos_frame, bg=FUNDO)
            linha_frame.pack(fill="x")
            for titulo, funcao in linha:
                card, figura = self._card_grafico(linha_frame, titulo)
                if figura is not None:
                    funcao(figura)
                    grafico = renderizar_grafico(card, figura)
                    self._bind_mousewheel_recursivo(grafico.get_tk_widget())

    def _grafico_status(self, figura):
        dados = db.dashboard_status_estoque()
        ax = figura.axes[0]
        labels = [d["status"] for d in dados]
        valores = [d["total"] for d in dados]
        ax.barh(labels, valores, color=[VERMELHO, COLORS["warning_dot"], VERDE_ESC, MUTED, COLORS["text_tertiary"]][: len(labels)])
        ax.tick_params(labelsize=8, colors=COLORS["text_secondary"])

    def _grafico_abc(self, figura):
        dados = db.dashboard_curva_abc()
        ax = figura.axes[0]
        valores = [d["total"] for d in dados if d["total"]]
        labels = [d["curva"] for d in dados if d["total"]]
        if valores:
            ax.pie(
                valores,
                labels=labels,
                autopct="%1.0f%%",
                textprops={"fontsize": 8, "color": COLORS["text_secondary"]},
                colors=[COLORS["success_dot"], COLORS["info_dot"], COLORS["warning_dot"]],
            )

    def _grafico_categorias(self, figura):
        dados = list(reversed(db.dashboard_valor_por_categoria()))
        ax = figura.axes[0]
        ax.barh([d["categoria"][:26] for d in dados], [d["valor"] for d in dados], color=AZUL)
        ax.tick_params(labelsize=8, colors=COLORS["text_secondary"])

    def _grafico_valor_parado(self, figura):
        dados = list(reversed(db.dashboard_top_valor_parado()))
        ax = figura.axes[0]
        ax.barh([d["nome"][:26] for d in dados], [d["valor"] for d in dados], color=VERDE_ESC)
        ax.tick_params(labelsize=8, colors=COLORS["text_secondary"])

    def _grafico_vendidos(self, figura):
        dados = list(reversed(db.dashboard_top_vendidos()))
        ax = figura.axes[0]
        ax.barh([d["nome"][:26] for d in dados], [d["quantidade"] for d in dados], color=AZUL)
        ax.tick_params(labelsize=8, colors=COLORS["text_secondary"])

    def _grafico_movimentos(self, figura):
        dados = db.dashboard_movimentacoes_periodo()
        ax = figura.axes[0]
        datas = [d["data_iso"][5:] for d in dados]
        ax.plot(datas, [d["entradas"] or 0 for d in dados], label="Entradas", color=VERDE_ESC, linewidth=2)
        ax.plot(datas, [d["vendas"] or 0 for d in dados], label="Vendas", color=AZUL, linewidth=2)
        ax.plot(datas, [d["perdas"] or 0 for d in dados], label="Perdas", color=VERMELHO, linewidth=2)
        ax.legend(fontsize=7, frameon=False)
        ax.tick_params(labelsize=7, rotation=45, colors=COLORS["text_secondary"])

    def _renderizar_acoes(self, produtos: list[dict]):
        if not self._acoes_tree:
            return
        for item in self._acoes_tree.get_children():
            self._acoes_tree.delete(item)
        for produto in produtos:
            tag = "row-critical" if (produto.get("status") or "") == "CRITICO" else ""
            self._acoes_tree.insert(
                "",
                "end",
                tags=(tag,) if tag else (),
                values=(
                    produto.get("codigo") or "",
                    produto.get("nome") or "",
                    (produto.get("status") or "").title(),
                    produto.get("estoque") or 0,
                    produto.get("estoque_minimo") or 0,
                    moeda(float(produto.get("valor_estoque") or 0)),
                ),
            )

    def _rolar(self, event):
        if self._canvas is not None:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

    def _rolar_linux(self, event):
        if self._canvas is None:
            return
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        return "break"

    def _bind_mousewheel_recursivo(self, widget):
        if not widget:
            return
        widget_id = str(widget)
        if widget_id in self._scroll_widgets:
            return
        self._scroll_widgets.add(widget_id)
        widget.bind("<MouseWheel>", self._rolar, add="+")
        widget.bind("<Button-4>", self._rolar_linux, add="+")
        widget.bind("<Button-5>", self._rolar_linux, add="+")
        for child in widget.winfo_children():
            self._bind_mousewheel_recursivo(child)
