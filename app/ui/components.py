"""Componentes visuais reutilizaveis da interface Tkinter."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from tema import (
    BORDER_COLOR,
    BRANCO,
    BUTTON_STYLES,
    CARD_PADDING,
    COLORS,
    FONTES,
    FUNDO,
    FUNDO2,
    MUTED,
    PGTO_BG,
    PGTO_FG,
    SHADOW,
    TEXTO,
    VERDE_ESC,
    status_badge_meta,
    tipo_badge_meta,
)


def configure_styles(root: tk.Misc):
    """Configura estilos ttk compartilhados."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TFrame", background=FUNDO)
    style.configure("TNotebook", background=FUNDO, borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", padding=(0, 0), background=FUNDO, borderwidth=0)
    style.layout("TNotebook.Tab", [])
    style.configure(
        "Treeview",
        background=BRANCO,
        fieldbackground=BRANCO,
        foreground=TEXTO,
        rowheight=38,
        bordercolor=COLORS["border_subtle"],
        lightcolor=COLORS["border_subtle"],
        darkcolor=COLORS["border_subtle"],
        borderwidth=0,
        relief="flat",
        font=FONTES["corpo"],
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["brand_green_light"])],
        foreground=[("selected", TEXTO)],
    )
    style.configure(
        "Treeview.Heading",
        background=BRANCO,
        foreground=COLORS["text_tertiary"],
        borderwidth=0,
        relief="flat",
        padding=(10, 8),
        font=FONTES["label_sm"],
    )
    style.configure(
        "TCombobox",
        padding=6,
        arrowsize=12,
        fieldbackground=BRANCO,
        background=BRANCO,
        bordercolor=COLORS["border_default"],
        lightcolor=COLORS["border_default"],
        darkcolor=COLORS["border_default"],
        foreground=TEXTO,
        relief="flat",
    )
    return style


def apply_button_style(button: tk.Button, variant: str = "secondary", *, disabled: bool = False):
    """Aplica o estilo visual padrao a um botao Tk."""
    palette = BUTTON_STYLES["ghost" if disabled else variant]
    button.configure(
        bg=palette["bg"],
        fg=palette["fg"],
        activebackground=palette["activebackground"],
        activeforeground=palette["activeforeground"],
        relief="flat",
        bd=0,
        cursor="arrow" if disabled else "hand2",
        highlightthickness=0,
    )


def styled_entry(parent: tk.Widget, textvariable: tk.StringVar | None = None, *, width: int | None = None):
    """Cria um campo de entrada com borda sutil e estado de foco consistente."""
    entry = tk.Entry(
        parent,
        textvariable=textvariable,
        bg=BRANCO,
        fg=TEXTO,
        insertbackground=VERDE_ESC,
        relief="flat",
        bd=0,
        width=width,
        font=FONTES["corpo"],
        highlightbackground=COLORS["border_default"],
        highlightcolor=COLORS["border_default"],
        highlightthickness=1,
    )

    def focus_in(_event=None):
        entry.configure(highlightbackground=VERDE_ESC, highlightcolor=VERDE_ESC)

    def focus_out(_event=None):
        entry.configure(highlightbackground=COLORS["border_default"], highlightcolor=COLORS["border_default"])

    entry.bind("<FocusIn>", focus_in)
    entry.bind("<FocusOut>", focus_out)
    return entry


def styled_checkbox(parent: tk.Widget, *, text: str, variable: tk.BooleanVar, command=None, bg: str = BRANCO):
    """Cria um checkbox sem a aparencia nativa do sistema."""
    checkbox = tk.Checkbutton(
        parent,
        text=text,
        variable=variable,
        command=command,
        indicatoron=False,
        onvalue=True,
        offvalue=False,
        bg=bg,
        fg=TEXTO,
        activebackground=COLORS["brand_green_light"],
        activeforeground=COLORS["brand_green"],
        selectcolor=COLORS["brand_green_light"],
        relief="flat",
        bd=0,
        padx=10,
        pady=6,
        font=FONTES["corpo"],
        cursor="hand2",
        highlightbackground=COLORS["border_default"],
        highlightcolor=COLORS["border_default"],
        highlightthickness=1,
    )
    return checkbox


class PageHeader(tk.Frame):
    """Cabecalho de pagina com titulo, subtitulo e acao opcional."""

    def __init__(self, parent, title: str, subtitle: str = "", action_text: str | None = None, action=None):
        super().__init__(parent, bg=FUNDO)
        left = tk.Frame(self, bg=FUNDO)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=title, bg=FUNDO, fg=TEXTO, font=FONTES["titulo"]).pack(anchor="w")
        if subtitle:
            tk.Label(left, text=subtitle, bg=FUNDO, fg=MUTED, font=FONTES["corpo"]).pack(anchor="w", pady=(3, 0))
        if action_text:
            action_button(self, text=action_text, command=action).pack(side="right")


class SectionHeader(tk.Frame):
    """Cabecalho curto de secao."""

    def __init__(self, parent, title: str, subtitle: str = "", action_text: str | None = None, action=None):
        super().__init__(parent, bg=FUNDO)
        left = tk.Frame(self, bg=FUNDO)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=title, bg=FUNDO, fg=TEXTO, font=FONTES["secao"]).pack(anchor="w")
        if subtitle:
            tk.Label(left, text=subtitle, bg=FUNDO, fg=MUTED, font=FONTES["corpo"]).pack(anchor="w", pady=(1, 0))
        if action_text:
            action_button(self, text=action_text, command=action).pack(side="right")


def action_button(
    parent: tk.Widget,
    *,
    text: str,
    command=None,
    variant: str = "secondary",
    font=None,
    padx: int = 14,
    pady: int = 8,
    **kwargs,
):
    """Cria um botao padronizado para a interface."""
    button = tk.Button(
        parent,
        text=text,
        command=command,
        font=font or FONTES["botao"],
        padx=padx,
        pady=pady,
        **kwargs,
    )
    apply_button_style(button, variant)
    return button


class LabeledField(tk.Frame):
    """Campo simples com rotulo e widget alinhados horizontalmente."""

    def __init__(
        self,
        parent,
        *,
        label: str,
        widget_factory,
        description: str = "",
        bg: str = BRANCO,
    ):
        super().__init__(parent, bg=bg)
        left = tk.Frame(self, bg=bg)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=label, bg=bg, fg=TEXTO, font=FONTES["corpo_bold"]).pack(anchor="w")
        if description:
            tk.Label(left, text=description, bg=bg, fg=MUTED, font=FONTES["corpo"]).pack(anchor="w", pady=(2, 0))
        self.widget = widget_factory(self)


class Card(tk.Frame):
    """Superficie branca com borda sutil."""

    def __init__(
        self,
        parent,
        padding: int = CARD_PADDING,
        bg: str = BRANCO,
        border: str | None = None,
        **kwargs,
    ):
        super().__init__(
            parent,
            bg=bg,
            highlightbackground=border or SHADOW["card_border"],
            highlightcolor=border or SHADOW["card_border"],
            highlightthickness=1,
            bd=0,
            padx=padding,
            pady=padding,
            **kwargs,
        )


class StatusBadge(tk.Frame):
    """Badge de status com ponto indicador."""

    VARIANTS = {
        "success": (COLORS["success_bg"], COLORS["success_text"], COLORS["success_dot"]),
        "danger": (COLORS["danger_bg"], COLORS["danger_text"], COLORS["danger_dot"]),
        "warning": (COLORS["warning_bg"], COLORS["warning_text"], COLORS["warning_dot"]),
        "info": (COLORS["info_bg"], COLORS["info_text"], COLORS["info_dot"]),
        "neutral": (COLORS["neutral_bg"], COLORS["neutral_text"], COLORS["neutral_dot"]),
    }

    def __init__(self, parent, text: str):
        label, variant = status_badge_meta(text)
        bg, fg, dot = self.VARIANTS[variant]
        super().__init__(parent, bg=bg, padx=8, pady=3)
        tk.Frame(self, bg=dot, width=5, height=5).pack(side="left", padx=(0, 5))
        self.winfo_children()[0].pack_propagate(False)
        tk.Label(self, text=label, bg=bg, fg=fg, font=FONTES["label_sm"]).pack(side="left")


class TipoBadge(tk.Label):
    """Badge retangular para tipo de movimentacao."""

    VARIANTS = {
        "venda": (COLORS["success_bg"], COLORS["success_dot"]),
        "ajuste": (COLORS["info_bg"], COLORS["info_dot"]),
        "entrada": (COLORS["warning_bg"], COLORS["warning_dot"]),
        "retorno": (COLORS["purple_bg"], COLORS["purple_text"]),
    }

    def __init__(self, parent, text: str):
        label, variant = tipo_badge_meta(text)
        bg, fg = self.VARIANTS[variant]
        super().__init__(parent, text=label.upper(), bg=bg, fg=fg, font=FONTES["label_sm"], padx=8, pady=2)


class EmptyState(tk.Frame):
    """Estado vazio com hierarquia textual central."""

    def __init__(self, parent, title: str, subtitle: str = "", icon: str = "◌"):
        super().__init__(parent, bg=BRANCO)
        tk.Label(self, text=icon, bg=BRANCO, fg=COLORS["text_tertiary"], font=(FONTES["titulo"][0], 24)).pack(pady=(24, 6))
        tk.Label(self, text=title, bg=BRANCO, fg=TEXTO, font=FONTES["subtitulo"]).pack()
        if subtitle:
            tk.Label(
                self,
                text=subtitle,
                bg=BRANCO,
                fg=COLORS["text_tertiary"],
                font=FONTES["corpo"],
                wraplength=420,
                justify="center",
            ).pack(pady=(4, 0))


class SearchInput(tk.Frame):
    """Caixa de busca com borda sutil e espaco para icone."""

    def __init__(self, parent, textvariable: tk.StringVar, placeholder: str = ""):
        super().__init__(
            parent,
            bg=BRANCO,
            highlightbackground=COLORS["border_default"],
            highlightcolor=COLORS["border_default"],
            highlightthickness=1,
            bd=0,
            padx=10,
            pady=8,
        )
        tk.Label(self, text="⌕", bg=BRANCO, fg=COLORS["text_tertiary"], font=(FONTES["titulo"][0], 11)).pack(side="left", padx=(2, 8))
        self.entry = styled_entry(self, textvariable)
        self.entry.pack(side="left", fill="x", expand=True, ipady=2)
        self._placeholder = placeholder
        if placeholder:
            self.entry.insert(0, placeholder)
            self.entry.config(fg=COLORS["text_tertiary"])
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_in(self, _event=None):
        if self.entry.get() == self._placeholder:
            self.entry.delete(0, "end")
            self.entry.config(fg=TEXTO)
        self.configure(highlightbackground=VERDE_ESC, highlightcolor=VERDE_ESC)

    def _on_focus_out(self, _event=None):
        if not self.entry.get():
            self.entry.insert(0, self._placeholder)
            self.entry.config(fg=COLORS["text_tertiary"])
        self.configure(highlightbackground=COLORS["border_default"], highlightcolor=COLORS["border_default"])


class DataTable(ttk.Treeview):
    """Treeview padronizada para tabelas administrativas."""

    def __init__(self, parent, columns, headings, widths=None, *, height: int = 12):
        super().__init__(parent, columns=columns, show="headings", height=height, style="Treeview")
        widths = widths or {}
        for col in columns:
            self.heading(col, text=headings.get(col, col))
            self.column(col, width=widths.get(col, 100), anchor="center")
        self.tag_configure("row-critical", background="#FEF8F8")


def payment_button(parent: tk.Widget, text: str, method: str, command):
    """Cria botao de pagamento no formato de card selecionavel."""
    button = tk.Button(
        parent,
        text=text,
        command=lambda: command(method),
        font=FONTES["corpo_bold"],
        padx=6,
        pady=10,
        justify="center",
        wraplength=120,
    )
    button._default_payment_bg = BRANCO  # type: ignore[attr-defined]
    button._default_payment_fg = MUTED  # type: ignore[attr-defined]
    apply_button_style(button, "secondary")
    return button


def set_payment_button_selected(button: tk.Button, method: str, *, selected: bool):
    """Atualiza a aparencia de um botao de pagamento."""
    if selected:
        button.configure(
            bg=PGTO_BG[method],
            fg=PGTO_FG[method],
            activebackground=PGTO_BG[method],
            activeforeground=PGTO_FG[method],
            highlightbackground=VERDE_ESC,
            highlightcolor=VERDE_ESC,
            highlightthickness=1,
        )
    else:
        button.configure(
            bg=BRANCO,
            fg=MUTED,
            activebackground=COLORS["bg_secondary"],
            activeforeground=TEXTO,
            highlightbackground=SHADOW["card_border"],
            highlightcolor=SHADOW["card_border"],
            highlightthickness=1,
        )


def add_scrollbars(table: ttk.Treeview, parent: tk.Widget, x: bool = True, y: bool = True):
    """Adiciona barras de rolagem opcionais a uma tabela ttk."""
    if y:
        scroll_y = ttk.Scrollbar(parent, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll_y.set)
    else:
        scroll_y = None
    if x:
        scroll_x = ttk.Scrollbar(parent, orient="horizontal", command=table.xview)
        table.configure(xscrollcommand=scroll_x.set)
    else:
        scroll_x = None
    return scroll_x, scroll_y
