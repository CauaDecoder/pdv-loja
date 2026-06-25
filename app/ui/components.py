"""Componentes visuais reutilizaveis da interface Tkinter."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from tema import (
    AZUL,
    BORDA,
    BRANCO,
    BORDER_COLOR,
    CARD_PADDING,
    COLORS,
    ESPACOS,
    FONTES,
    FUNDO,
    FUNDO2,
    MUTED,
    TEXTO,
    VERDE_CLAR,
    VERDE_ESC,
    VERMELHO,
)


def configure_styles(root: tk.Misc):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TNotebook", background=FUNDO, borderwidth=0, tabmargins=(10, 2, 10, 0))
    style.configure(
        "TNotebook.Tab",
        font=FONTES["botao"],
        padding=(18, 11),
        background=FUNDO2,
        foreground=TEXTO,
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", BRANCO), ("active", COLORS["neutral_2"])],
        foreground=[("selected", TEXTO), ("active", TEXTO)],
        padding=[("selected", (18, 11)), ("active", (18, 11))],
    )
    style.configure(
        "Treeview",
        background=BRANCO,
        fieldbackground=BRANCO,
        foreground=TEXTO,
        rowheight=36,
        bordercolor=COLORS["border_soft"],
        borderwidth=0,
        font=FONTES["corpo"],
    )
    style.configure("Treeview.Heading", font=FONTES["label"], padding=(8, 6), background=BRANCO, foreground=TEXTO)
    style.map("Treeview", background=[("selected", COLORS["primary_soft"])], foreground=[("selected", TEXTO)])
    style.configure(
        "TCombobox",
        padding=5,
        arrowsize=12,
        fieldbackground=BRANCO,
        bordercolor=COLORS["border_soft"],
        lightcolor=COLORS["border_soft"],
        darkcolor=COLORS["border_soft"],
        foreground=TEXTO,
    )
    return style


class PageHeader(tk.Frame):
    def __init__(self, parent, title: str, subtitle: str = "", action_text: str | None = None, action=None):
        super().__init__(parent, bg=FUNDO)
        left = tk.Frame(self, bg=FUNDO)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=title, bg=FUNDO, fg=TEXTO, font=FONTES["titulo"]).pack(anchor="w")
        if subtitle:
            tk.Label(left, text=subtitle, bg=FUNDO, fg=MUTED, font=FONTES["corpo"]).pack(anchor="w", pady=(2, 0))
        if action_text:
            tk.Button(
                self,
                text=action_text,
                bg=BRANCO,
                fg=VERDE_ESC,
                relief="flat",
                font=FONTES["botao"],
                cursor="hand2",
                padx=14,
                pady=8,
                command=action,
            ).pack(side="right")


class SectionHeader(tk.Frame):
    def __init__(self, parent, title: str, subtitle: str = "", action_text: str | None = None, action=None):
        super().__init__(parent, bg=FUNDO)
        tk.Label(self, text=title, bg=FUNDO, fg=TEXTO, font=FONTES["secao"]).pack(anchor="w")
        if subtitle:
            tk.Label(self, text=subtitle, bg=FUNDO, fg=MUTED, font=FONTES["corpo"]).pack(anchor="w", pady=(1, 0))
        if action_text:
            tk.Button(self, text=action_text, bg=BRANCO, fg=VERDE_ESC, relief="flat", font=FONTES["botao"], command=action).pack(
                side="right"
            )


def action_button(
    parent: tk.Widget,
    *,
    text: str,
    command=None,
    bg: str = BRANCO,
    fg: str = VERDE_ESC,
    font=None,
    padx: int = 14,
    pady: int = 8,
    **kwargs,
):
    """Cria um botao padronizado para a interface."""
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        relief="flat",
        font=font or FONTES["botao"],
        cursor="hand2",
        padx=padx,
        pady=pady,
        **kwargs,
    )


class LabeledField(tk.Frame):
    """Campo simples com rotulo e widget alinhados verticalmente."""

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
        tk.Label(left, text=label, bg=bg, fg=TEXTO, font=FONTES["label"]).pack(anchor="w")
        if description:
            tk.Label(left, text=description, bg=bg, fg=MUTED, font=FONTES["corpo"]).pack(anchor="w", pady=(1, 0))
        self.widget = widget_factory(self)


class Card(tk.Frame):
    def __init__(self, parent, padding: int = CARD_PADDING, bg: str = BRANCO, **kwargs):
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, padx=padding, pady=padding, **kwargs)


class StatusBadge(tk.Label):
    COLORS = {
        "CRITICO": (VERMELHO, "#FCEBEB"),
        "ALERTA": ("#A66A00", "#FFF5DC"),
        "OK": (VERDE_ESC, VERDE_CLAR),
        "MORTO": (MUTED, "#EBEBEB"),
        "INATIVO": (MUTED, "#EBEBEB"),
        "Entrada": ("#A66A00", "#FFF5DC"),
        "Venda": (VERDE_ESC, VERDE_CLAR),
        "Ajuste": (AZUL, "#E6F1FB"),
        "Perda": (VERMELHO, "#FCEBEB"),
        "Importacao": (AZUL, "#E6F1FB"),
    }

    def __init__(self, parent, text: str):
        fg, bg = self.COLORS.get(text, (TEXTO, FUNDO2))
        super().__init__(parent, text=text, bg=bg, fg=fg, font=FONTES["label_sm"], padx=8, pady=3)


class EmptyState(tk.Frame):
    def __init__(self, parent, title: str, subtitle: str = ""):
        super().__init__(parent, bg=BRANCO)
        tk.Label(self, text=title, bg=BRANCO, fg=TEXTO, font=FONTES["subtitulo"]).pack(pady=(18, 4))
        if subtitle:
            tk.Label(self, text=subtitle, bg=BRANCO, fg=MUTED, font=FONTES["corpo"], wraplength=420, justify="center").pack()


class SearchInput(tk.Frame):
    def __init__(self, parent, textvariable: tk.StringVar, placeholder: str = ""):
        super().__init__(parent, bg=FUNDO2)
        tk.Label(self, text="⌕", bg=FUNDO2, fg=MUTED, font=("Segoe UI Symbol", 11)).pack(side="left", padx=(10, 6))
        self.entry = tk.Entry(self, textvariable=textvariable, bg=FUNDO2, fg=TEXTO, relief="flat", bd=0, font=FONTES["corpo"])
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        if placeholder:
            self.entry.insert(0, placeholder)
            self.entry.config(fg=MUTED)
        self.entry.bind("<FocusIn>", lambda _e: self._on_focus_in(placeholder))
        self.entry.bind("<FocusOut>", lambda _e: self._on_focus_out(placeholder))

    def _on_focus_in(self, placeholder: str):
        if self.entry.get() == placeholder:
            self.entry.delete(0, "end")
            self.entry.config(fg=TEXTO)

    def _on_focus_out(self, placeholder: str):
        if not self.entry.get():
            self.entry.insert(0, placeholder)
            self.entry.config(fg=MUTED)


class DataTable(ttk.Treeview):
    def __init__(self, parent, columns, headings, widths=None, *, height: int = 12):
        super().__init__(parent, columns=columns, show="headings", height=height)
        widths = widths or {}
        for col in columns:
            self.heading(col, text=headings.get(col, col))
            self.column(col, width=widths.get(col, 100), anchor="center")
        self.tag_configure("odd", background="#FAF9F6")


def add_scrollbars(table: ttk.Treeview, parent: tk.Widget, x: bool = True, y: bool = True):
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

