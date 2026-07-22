"""Dashboard gerencial do modulo de estoque."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import database as db
import tema as theme
from app.ui.components import Card, EmptyState, PageHeader
from tema import (
    ESPACOS,
    FONTES,
    moeda,
)

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except Exception:  # pragma: no cover - depende do ambiente grafico local
    Figure = None
    FigureCanvasTkAgg = None


def criar_figura(titulo: str, largura=4, altura=3):
    figura = Figure(figsize=(largura, altura), dpi=92)
    figura.patch.set_facecolor(theme.BRANCO)
    ax = figura.add_subplot(111)
    ax.set_title(titulo, fontsize=10, fontweight="bold", color=theme.TEXTO, pad=10)
    return figura


def renderizar_grafico(frame, figure):
    canvas = FigureCanvasTkAgg(figure, master=frame)
    widget = canvas.get_tk_widget()
    widget.pack(fill="both", expand=True)
    canvas.draw()
    return canvas


class DashboardEstoque(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=theme.FUNDO)
        self._cards: dict[str, tk.Label] = {}
        self._graficos_frame: tk.Frame | None = None
        self._acoes_tree: ttk.Treeview | None = None
        self._canvas: tk.Canvas | None = None
        self._scroll_widgets: set[str] = set()
        self._build_ui()
        self.atualizar()

    def _build_ui(self):
        PageHeader(self, "Dashboard de estoque", "Visao rapida de saldo, risco e giro dos produtos.", "Atualizar dashboard", self.atualizar).pack(
            fill="x", padx=ESPACOS["lg"], pady=ESPACOS["lg"]
        )

        self._canvas = tk.Canvas(self, bg=theme.FUNDO, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scroll.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._conteudo = tk.Frame(self._canvas, bg=theme.FUNDO, padx=ESPACOS["lg"], pady=0)
        self._window = self._canvas.create_window((0, 0), window=self._conteudo, anchor="nw")
        self._conteudo.bind("<Configure>", lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfigure(self._window, width=e.width))
        self._bind_mousewheel_recursivo(self._canvas)

        self._cards_frame = tk.Frame(self._conteudo, bg=theme.FUNDO)
        self._cards_frame.pack(fill="x", pady=(0, ESPACOS["md"]))
        for idx, (chave, titulo, subtitulo, cor) in enumerate(
            (
                ("skus_ativos", "SKUs ativos", "Produtos ativos cadastrados", theme.VERDE_ESC),
                ("produtos_criticos", "Criticos", "Estoque no minimo ou abaixo", theme.VERMELHO),
                ("produtos_alerta", "Em alerta", "Abaixo do ponto de pedido", theme.AZUL),
                ("produtos_sem_giro", "Sem giro", "Sem movimento recente", theme.MUTED),
                ("valor_total_custo", "Valor a custo", "Custo estimado do estoque", theme.VERDE_ESC),
                ("valor_total_venda", "Valor a venda", "Potencial bruto de venda", theme.AZUL),
                ("sem_custo", "Sem custo", "Produtos sem custo cadastrado", theme.VERMELHO),
                ("sem_estoque_minimo", "Sem minimo", "Minimo nao configurado", theme.MUTED),
            )
        ):
            self._criar_card(self._cards_frame, chave, titulo, subtitulo, cor, idx)

        self._graficos_frame = tk.Frame(self._conteudo, bg=theme.FUNDO)
        self._graficos_frame.pack(fill="both", expand=True)

        tk.Label(
            self._conteudo,
            text="Produtos que exigem acao",
            bg=theme.FUNDO,
            fg=theme.TEXTO,
            font=FONTES["secao"],
        ).pack(anchor="w", pady=(ESPACOS["md"], 6))
        colunas = ("codigo", "produto", "status", "estoque", "minimo", "valor")
        self._acoes_tree = ttk.Treeview(self._conteudo, columns=colunas, show="headings", height=8)
        titulos = {
            "codigo": "Cod.",
            "produto": "Produto",
            "status": "Status",
            "estoque": "Estoque",
            "minimo": "Min.",
            "valor": "Valor a custo",
        }
        for coluna in colunas:
            self._acoes_tree.heading(coluna, text=titulos[coluna])
            self._acoes_tree.column(coluna, width=110, anchor="center")
        self._acoes_tree.column("produto", width=420, anchor="w")
        self._acoes_tree.pack(fill="x", pady=(0, ESPACOS["lg"]))
        self._bind_mousewheel_recursivo(self._conteudo)

    def _criar_card(self, parent, chave: str, titulo: str, subtitulo: str, cor: str, idx: int):
        card = tk.Frame(parent, bg=theme.BRANCO, padx=14, pady=12, highlightbackground=theme.BORDA, highlightthickness=1)
        card.grid(row=idx // 4, column=idx % 4, sticky="nsew", padx=(0, ESPACOS["sm"]), pady=(0, ESPACOS["sm"]))
        parent.columnconfigure(idx % 4, weight=1)
        faixa = tk.Frame(card, bg=cor, height=4)
        faixa.pack(fill="x", pady=(0, ESPACOS["sm"]))
        tk.Label(card, text=titulo, bg=theme.BRANCO, fg=theme.MUTED, font=FONTES["label_sm"]).pack(anchor="w")
        valor = tk.Label(card, text="0", bg=theme.BRANCO, fg=cor, font=FONTES["numero_card"])
        valor.pack(anchor="w", pady=(6, 2))
        tk.Label(card, text=subtitulo, bg=theme.BRANCO, fg=theme.MUTED, font=FONTES["corpo"], wraplength=180, justify="left").pack(anchor="w")
        self._cards[chave] = valor

    def atualizar(self):
        resumo = db.dashboard_resumo_estoque()
        for chave, label in self._cards.items():
            valor = resumo.get(chave, 0)
            label.config(text=moeda(valor) if chave.startswith("valor_") else str(valor))
        self._renderizar_graficos()
        self._renderizar_acoes(resumo.get("produtos_acao", []))

    def _limpar_frame(self, frame: tk.Frame):
        for child in frame.winfo_children():
            child.destroy()

    def _card_grafico(self, parent: tk.Frame, titulo: str):
        frame = Card(parent, padding=8)
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
            (
                ("Distribuicao por status", self._grafico_status),
                ("Curva ABC", self._grafico_abc),
            ),
            (
                ("Valor por categoria", self._grafico_categorias),
                ("Top valor a custo", self._grafico_valor_parado),
            ),
            (
                ("Top vendidos 30 dias", self._grafico_vendidos),
                ("Entradas x saidas", self._grafico_movimentos),
            ),
        ]
        for linha in linhas:
            linha_frame = tk.Frame(self._graficos_frame, bg=theme.FUNDO)
            linha_frame.pack(fill="x")
            for titulo, funcao in linha:
                card, figura = self._card_grafico(linha_frame, titulo)
                if figura is not None:
                    funcao(figura)
                    grafico = renderizar_grafico(card, figura)
                    self._bind_mousewheel_recursivo(grafico.get_tk_widget())
        self._bind_mousewheel_recursivo(self._graficos_frame)

    def _grafico_status(self, figura):
        dados = db.dashboard_status_estoque()
        ax = figura.axes[0]
        labels = [d["status"] for d in dados]
        valores = [d["total"] for d in dados]
        ax.barh(labels, valores, color=[theme.VERMELHO, theme.AZUL, theme.VERDE_ESC, theme.MUTED, theme.FUNDO2])
        ax.tick_params(labelsize=8)

    def _grafico_abc(self, figura):
        dados = db.dashboard_curva_abc()
        ax = figura.axes[0]
        valores = [d["total"] for d in dados if d["total"]]
        labels = [d["curva"] for d in dados if d["total"]]
        if valores:
            ax.pie(valores, labels=labels, autopct="%1.0f%%", textprops={"fontsize": 8})

    def _grafico_categorias(self, figura):
        dados = list(reversed(db.dashboard_valor_por_categoria()))
        ax = figura.axes[0]
        ax.barh([d["categoria"][:28] for d in dados], [d["valor"] for d in dados], color=theme.AZUL)
        ax.tick_params(labelsize=8)

    def _grafico_valor_parado(self, figura):
        dados = list(reversed(db.dashboard_top_valor_parado()))
        ax = figura.axes[0]
        ax.barh([d["nome"][:28] for d in dados], [d["valor"] for d in dados], color=theme.VERDE_ESC)
        ax.tick_params(labelsize=8)

    def _grafico_vendidos(self, figura):
        dados = list(reversed(db.dashboard_top_vendidos()))
        ax = figura.axes[0]
        ax.barh([d["nome"][:28] for d in dados], [d["quantidade"] for d in dados], color=theme.AZUL)
        ax.tick_params(labelsize=8)

    def _grafico_movimentos(self, figura):
        dados = db.dashboard_movimentacoes_periodo()
        ax = figura.axes[0]
        datas = [d["data_iso"][5:] for d in dados]
        ax.plot(datas, [d["entradas"] or 0 for d in dados], label="Entradas", color=theme.VERDE_ESC)
        ax.plot(datas, [d["vendas"] or 0 for d in dados], label="Vendas", color=theme.AZUL)
        ax.plot(datas, [d["perdas"] or 0 for d in dados], label="Perdas", color=theme.VERMELHO)
        ax.legend(fontsize=7)
        ax.tick_params(labelsize=7, rotation=45)

    def _renderizar_acoes(self, produtos: list[dict]):
        if not self._acoes_tree:
            return
        for item in self._acoes_tree.get_children():
            self._acoes_tree.delete(item)
        for produto in produtos:
            self._acoes_tree.insert(
                "",
                "end",
                values=(
                    produto.get("codigo") or "",
                    produto.get("nome") or "",
                    produto.get("status") or "",
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
