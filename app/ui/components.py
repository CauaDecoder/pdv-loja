"""Componentes visuais reutilizaveis da interface Tkinter (Variante A - Command Center)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence

from tema import (
    CARD_PADDING,
    FONTES,
    obter_nome_tema_atual,
    obter_tema_atual,
)


def configure_styles(root: tk.Misc, theme_name: str | None = None) -> ttk.Style:
    """Configura e aplica os estilos ttk de acordo com o tema atual."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    tema = obter_tema_atual() if theme_name is None else (
        obter_tema_atual() if theme_name == obter_nome_tema_atual() else (
            __import__("tema").obter_tema(theme_name)
        )
    )

    style.configure(
        "TNotebook",
        background=tema["bg"],
        borderwidth=0,
        tabmargins=(18, 8, 18, 0),
    )
    style.configure(
        "TNotebook.Tab",
        font=FONTES["botao"],
        padding=(18, 11),
        background=tema["surface_2"],
        foreground=tema["text"],
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", tema["surface"]), ("active", tema["surface_hover"])],
        foreground=[("selected", tema["text"]), ("active", tema["text"])],
        padding=[("selected", (18, 11)), ("active", (18, 11))],
    )

    style.configure(
        "Treeview",
        background=tema["surface"],
        fieldbackground=tema["surface"],
        foreground=tema["text"],
        rowheight=38,
        bordercolor=tema["surface"],
        lightcolor=tema["surface"],
        darkcolor=tema["surface"],
        relief="flat",
        borderwidth=0,
        font=FONTES["corpo"],
    )
    style.configure(
        "Treeview.Heading",
        font=FONTES["label"],
        padding=(8, 6),
        background=tema["surface_2"],
        foreground=tema["text"],
        bordercolor=tema["surface_2"],
        lightcolor=tema["surface_2"],
        darkcolor=tema["surface_2"],
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", tema["primary_soft"])],
        foreground=[("selected", tema["text"])],
    )

    style.configure(
        "TCombobox",
        padding=6,
        arrowsize=12,
        fieldbackground=tema["surface_3"],
        background=tema["surface_2"],
        bordercolor=tema["border"],
        lightcolor=tema["border_soft"],
        darkcolor=tema["border_soft"],
        foreground=tema["text"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", tema["surface_3"]), ("disabled", tema["surface_2"])],
        background=[("readonly", tema["surface_2"]), ("active", tema["surface_hover"])],
        foreground=[("readonly", tema["text"]), ("disabled", tema["text_muted"])],
        selectbackground=[("readonly", tema["primary_soft"])],
        selectforeground=[("readonly", tema["text"])],
    )
    root.option_add("*TCombobox*Listbox.background", tema["surface_3"])
    root.option_add("*TCombobox*Listbox.foreground", tema["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", tema["primary_soft"])
    root.option_add("*TCombobox*Listbox.selectForeground", tema["text"])

    style.configure(
        "TScrollbar",
        background=tema["surface_2"],
        troughcolor=tema["bg"],
        bordercolor=tema["border_soft"],
        arrowcolor=tema["text_muted"],
    )

    return style


def bind_escape_to_close(dialog: tk.Toplevel) -> None:
    """Padroniza o cancelamento por Escape em modais Tkinter."""
    dialog.bind("<Escape>", lambda _event: dialog.destroy())


_BACKGROUND_COLOR_KEYS = (
    "bg",
    "surface",
    "surface_2",
    "surface_3",
    "surface_hover",
    "border",
    "border_soft",
    "primary",
    "primary_hover",
    "primary_soft",
    "gold",
    "gold_soft",
    "danger",
    "danger_soft",
    "warning",
    "warning_soft",
    "info",
    "info_soft",
    "purple_soft",
    "neutral_soft",
    "focus_ring",
)
_FOREGROUND_COLOR_KEYS = (
    "text",
    "text_muted",
    "text_on_primary",
    "text_on_dark",
    "primary",
    "primary_hover",
    "gold",
    "danger",
    "warning",
    "info",
    "purple_fg",
    "border",
)
_FOREGROUND_OPTIONS = {
    "foreground",
    "activeforeground",
    "disabledforeground",
    "insertbackground",
    "selectforeground",
}
_COLOR_OPTIONS = _FOREGROUND_OPTIONS | {
    "background",
    "activebackground",
    "highlightbackground",
    "highlightcolor",
    "readonlybackground",
    "selectbackground",
    "selectcolor",
    "troughcolor",
}


def _theme_color(
    value: str,
    option: str,
    previous_theme: dict[str, str],
    current_theme: dict[str, str],
) -> str:
    """Traduz uma cor do tema anterior preservando o papel semantico."""
    keys = _FOREGROUND_COLOR_KEYS if option in _FOREGROUND_OPTIONS else _BACKGROUND_COLOR_KEYS
    normalized = str(value).lower()
    for key in keys:
        if str(previous_theme.get(key, "")).lower() == normalized:
            return current_theme.get(key, value)
    return value


def apply_theme_to_widget_tree(
    widget: tk.Misc,
    previous_theme: dict[str, str],
) -> None:
    """Reaplica tokens de tema aos widgets ja montados em todas as telas."""
    current_theme = obter_tema_atual()
    updates = {}
    try:
        configuration = widget.configure()
    except tk.TclError:
        configuration = {}

    for option in _COLOR_OPTIONS.intersection(configuration):
        try:
            current_value = widget.cget(option)
            translated = _theme_color(current_value, option, previous_theme, current_theme)
            if translated != current_value:
                updates[option] = translated
        except tk.TclError:
            continue
    if updates:
        try:
            widget.configure(**updates)
        except tk.TclError:
            pass

    if isinstance(widget, tk.Canvas):
        for item_id in widget.find_all():
            item_updates = {}
            for option in ("fill", "outline", "activefill", "activeoutline"):
                try:
                    current_value = widget.itemcget(item_id, option)
                except tk.TclError:
                    continue
                role = "foreground" if "fill" in option else "background"
                translated = _theme_color(current_value, role, previous_theme, current_theme)
                if translated != current_value:
                    item_updates[option] = translated
            if item_updates:
                try:
                    widget.itemconfigure(item_id, **item_updates)
                except tk.TclError:
                    pass

    if isinstance(widget, ttk.Treeview):
        try:
            tags = widget.tk.splitlist(widget.tk.call(widget._w, "tag", "names"))
        except tk.TclError:
            tags = ()
        for tag in tags:
            tag_updates = {}
            for option in ("background", "foreground"):
                try:
                    current_value = widget.tag_configure(tag, option)
                except tk.TclError:
                    continue
                translated = _theme_color(current_value, option, previous_theme, current_theme)
                if translated != current_value:
                    tag_updates[option] = translated
            if tag_updates:
                widget.tag_configure(tag, **tag_updates)

    for child in widget.winfo_children():
        apply_theme_to_widget_tree(child, previous_theme)


class FocusHelper:
    """Helper para aplicar anel de foco evidente via teclado (Variante A - Dourado)."""

    @staticmethod
    def attach(
        widget: tk.Widget,
        normal_bg: str | None = None,
        focus_color: str | None = None,
        normal_border: str | None = None,
    ):
        tema = obter_tema_atual()
        ring = focus_color or tema["focus_ring"]
        norm_b = normal_border or tema["border"]

        def _theme_key(color: str) -> str | None:
            normalized = str(color).lower()
            return next(
                (key for key, value in tema.items() if str(value).lower() == normalized),
                None,
            )

        ring_key = _theme_key(ring)
        normal_key = _theme_key(norm_b)

        def _current_color(key: str | None, fallback: str) -> str:
            return obter_tema_atual().get(key, fallback) if key else fallback

        widget.config(
            highlightthickness=tema["focus_ring_width"],
            highlightbackground=norm_b,
            highlightcolor=ring,
        )

        def _on_focus_in(_e):
            try:
                widget.config(
                    highlightbackground=_current_color(ring_key, ring),
                    highlightcolor=_current_color(ring_key, ring),
                )
            except tk.TclError:
                pass

        def _on_focus_out(_e):
            try:
                widget.config(highlightbackground=_current_color(normal_key, norm_b))
            except tk.TclError:
                pass

        widget.bind("<FocusIn>", _on_focus_in, add="+")
        widget.bind("<FocusOut>", _on_focus_out, add="+")


class ActionButton(tk.Button):
    """Botão padronizado do sistema visual compartilhado."""

    VARIANTS = {
        "primary": lambda t: (t["primary"], t["text_on_primary"], t["primary_hover"], t["text_on_primary"]),
        "secondary": lambda t: (t["surface_2"], t["text"], t["surface_hover"], t["text"]),
        "ghost": lambda t: (t["bg"], t["text_muted"], t["surface_2"], t["text"]),
        "danger": lambda t: (t["danger_soft"], t["danger"], t["danger"], "#FFFFFF"),
        "gold": lambda t: (t["gold"], "#FFFFFF", "#A87A1E", "#FFFFFF"),
    }

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable | None = None,
        variant: str = "secondary",
        font=None,
        padx: int = 14,
        pady: int = 8,
        **kwargs,
    ):
        tema = obter_tema_atual()
        bg, fg, active_bg, active_fg = self.VARIANTS.get(variant, self.VARIANTS["secondary"])(tema)

        super().__init__(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=active_fg,
            relief="flat",
            font=font or FONTES["botao"],
            cursor="hand2",
            padx=padx,
            pady=pady,
            bd=0,
            **kwargs,
        )
        FocusHelper.attach(self, normal_border=bg if variant != "ghost" else tema["border"])


def action_button(
    parent: tk.Widget,
    *,
    text: str,
    command=None,
    variant: str = "secondary",
    bg: str | None = None,
    fg: str | None = None,
    font=None,
    padx: int = 14,
    pady: int = 8,
    **kwargs,
) -> tk.Button:
    """Cria um botão padronizado com foco de teclado garantido."""
    if bg or fg:
        tema = obter_tema_atual()
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg or tema["surface_2"],
            fg=fg or tema["text"],
            activebackground=tema["surface_hover"],
            activeforeground=fg or tema["text"],
            relief="flat",
            font=font or FONTES["botao"],
            cursor="hand2",
            padx=padx,
            pady=pady,
            bd=0,
            **kwargs,
        )
        FocusHelper.attach(btn, normal_border=bg or tema["border"])
        return btn
    return ActionButton(parent, text=text, command=command, variant=variant, font=font, padx=padx, pady=pady, **kwargs)


class StyledEntry(tk.Entry):
    """Campo de entrada individual com borda e anel de foco integrados."""

    def __init__(self, parent: tk.Widget, font=None, **kwargs):
        tema = obter_tema_atual()
        bg = kwargs.pop("bg", tema["surface_3"])
        fg = kwargs.pop("fg", tema["text"])
        font = font or FONTES["corpo"]

        super().__init__(
            parent,
            bg=bg,
            fg=fg,
            relief="flat",
            bd=0,
            font=font,
            insertbackground=fg,
            **kwargs,
        )
        FocusHelper.attach(self, normal_border=tema["border"])


class LabeledField(tk.Frame):
    """Campo padronizado contendo rótulo, descrição e widget alinhados."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        label: str,
        widget_factory: Callable[[tk.Widget], tk.Widget],
        description: str = "",
        bg: str | None = None,
    ):
        tema = obter_tema_atual()
        bg_color = bg or tema["surface"]
        super().__init__(parent, bg=bg_color)

        left = tk.Frame(self, bg=bg_color)
        left.pack(side="left", fill="x", expand=True)

        tk.Label(left, text=label, bg=bg_color, fg=tema["text"], font=FONTES["label"]).pack(anchor="w")
        if description:
            tk.Label(left, text=description, bg=bg_color, fg=tema["text_muted"], font=FONTES["corpo"]).pack(
                anchor="w", pady=(1, 0)
            )
        self.widget = widget_factory(self)


class Card(tk.Frame):
    """Container em cartão com superfície clara e borda suave."""

    def __init__(self, parent: tk.Widget, padding: int = CARD_PADDING, bg: str | None = None, **kwargs):
        tema = obter_tema_atual()
        bg_color = bg or tema["surface"]
        super().__init__(
            parent,
            bg=bg_color,
            highlightthickness=1,
            highlightbackground=tema["border_soft"],
            bd=0,
            padx=padding,
            pady=padding,
            **kwargs,
        )


class Panel(Card):
    """Painel de seção secundário."""

    def __init__(self, parent: tk.Widget, padding: int = CARD_PADDING, **kwargs):
        tema = obter_tema_atual()
        super().__init__(parent, padding=padding, bg=tema["surface_2"], **kwargs)


class StatusBadge(tk.Label):
    """Badge em formato de pílula para status operacionais e de pagamentos."""

    def __init__(self, parent: tk.Widget, text: str, bg: str | None = None, fg: str | None = None):
        tema = obter_tema_atual()
        badge_map = {
            "CRITICO": (tema["danger"], tema["danger_soft"]),
            "ALERTA": (tema["warning"], tema["warning_soft"]),
            "OK": (tema["primary"], tema["primary_soft"]),
            "Ativo": (tema["primary"], tema["primary_soft"]),
            "Padrão": (tema["info"], tema["info_soft"]),
            "SENSIVEL": (tema["danger"], tema["danger_soft"]),
            "MORTO": (tema["text_muted"], tema["neutral_soft"]),
            "INATIVO": (tema["text_muted"], tema["neutral_soft"]),
            "Entrada": (tema["warning"], tema["warning_soft"]),
            "Venda": (tema["primary"], tema["primary_soft"]),
            "Ajuste": (tema["info"], tema["info_soft"]),
            "Perda": (tema["danger"], tema["danger_soft"]),
            "Importacao": (tema["info"], tema["info_soft"]),
            "Debito": (tema["info"], tema["info_soft"]),
            "Credito": (tema["purple_fg"], tema["purple_soft"]),
            "Pix": (tema["primary"], tema["primary_soft"]),
            "Dinheiro": (tema["gold"], tema["gold_soft"]),
            "Mais de uma forma": (tema["purple_fg"], tema["purple_soft"]),
            "CANCELADA": (tema["danger"], tema["danger_soft"]),
            "CORRIGIDA": (tema["warning"], tema["warning_soft"]),
            "VALIDA": (tema["primary"], tema["primary_soft"]),
        }
        default_fg, default_bg = badge_map.get(text, (tema["text"], tema["surface_2"]))
        final_fg = fg or default_fg
        final_bg = bg or default_bg
        super().__init__(parent, text=text, bg=final_bg, fg=final_fg, font=FONTES["label_sm"], padx=8, pady=3)


class PageHeader(tk.Frame):
    """Cabeçalho de página padronizado."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        subtitle: str = "",
        action_text: str | None = None,
        action: Callable | None = None,
        badge_text: str | None = None,
    ):
        tema = obter_tema_atual()
        super().__init__(parent, bg=tema["bg"])

        left = tk.Frame(self, bg=tema["bg"])
        left.pack(side="left", fill="x", expand=True)

        title_row = tk.Frame(left, bg=tema["bg"])
        title_row.pack(anchor="w")
        tk.Label(title_row, text=title, bg=tema["bg"], fg=tema["text"], font=FONTES["titulo"]).pack(side="left")

        if badge_text:
            badge = StatusBadge(title_row, badge_text)
            badge.pack(side="left", padx=(10, 0))

        if subtitle:
            tk.Label(left, text=subtitle, bg=tema["bg"], fg=tema["text_muted"], font=FONTES["corpo"]).pack(
                anchor="w", pady=(2, 0)
            )

        if action_text:
            action_button(
                self,
                text=action_text,
                command=action,
                variant="secondary",
            ).pack(side="right")


class SectionHeader(tk.Frame):
    """Cabeçalho de seção padronizado."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        subtitle: str = "",
        action_text: str | None = None,
        action: Callable | None = None,
    ):
        tema = obter_tema_atual()
        super().__init__(parent, bg=tema["bg"])

        left = tk.Frame(self, bg=tema["bg"])
        left.pack(side="left", fill="x", expand=True)

        tk.Label(left, text=title, bg=tema["bg"], fg=tema["text"], font=FONTES["secao"]).pack(anchor="w")
        if subtitle:
            tk.Label(left, text=subtitle, bg=tema["bg"], fg=tema["text_muted"], font=FONTES["corpo"]).pack(
                anchor="w", pady=(1, 0)
            )

        if action_text:
            action_button(
                self,
                text=action_text,
                command=action,
                variant="secondary",
                padx=10,
                pady=5,
            ).pack(side="right")


class SearchInput(tk.Frame):
    """Campo de busca operacional de destaque (Command Center)."""

    def __init__(
        self,
        parent: tk.Widget,
        textvariable: tk.StringVar,
        placeholder: str = "",
        on_return: Callable | None = None,
        on_arrow_down: Callable | None = None,
        on_arrow_up: Callable | None = None,
    ):
        tema = obter_tema_atual()
        super().__init__(parent, bg=tema["surface_3"], highlightthickness=1, highlightbackground=tema["border"])

        FocusHelper.attach(self, normal_border=tema["border"])

        tk.Label(self, text="⌕", bg=tema["surface_3"], fg=tema["text_muted"], font=("Segoe UI Symbol", 13, "bold")).pack(
            side="left", padx=(12, 6)
        )

        self.entry = tk.Entry(
            self,
            textvariable=textvariable,
            bg=tema["surface_3"],
            fg=tema["text"],
            relief="flat",
            bd=0,
            font=("Segoe UI", 12, "bold"),
            insertbackground=tema["text"],
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 10))

        self.placeholder = placeholder
        if placeholder:
            if not textvariable.get():
                self.entry.insert(0, placeholder)
                self.entry.config(fg=tema["text_muted"])

        self.entry.bind("<FocusIn>", lambda _e: self._on_focus_in())
        self.entry.bind("<FocusOut>", lambda _e: self._on_focus_out())

        if on_return:
            self.entry.bind("<Return>", lambda _e: on_return())
        if on_arrow_down:
            self.entry.bind("<Down>", lambda _e: on_arrow_down())
        if on_arrow_up:
            self.entry.bind("<Up>", lambda _e: on_arrow_up())

    def _on_focus_in(self):
        tema = obter_tema_atual()
        try:
            self.config(highlightbackground=tema["focus_ring"])
        except tk.TclError:
            pass
        if self.placeholder and self.entry.get() == self.placeholder:
            self.entry.delete(0, "end")
            self.entry.config(fg=tema["text"])

    def _on_focus_out(self):
        tema = obter_tema_atual()
        try:
            self.config(highlightbackground=tema["border"])
        except tk.TclError:
            pass
        if self.placeholder and not self.entry.get():
            self.entry.insert(0, self.placeholder)
            self.entry.config(fg=tema["text_muted"])


class DataTable(ttk.Treeview):
    """Tabela de dados customizada padronizada com o tema."""

    def __init__(
        self,
        parent: tk.Widget,
        columns: Sequence[str],
        headings: dict[str, str],
        widths: dict[str, int] | None = None,
        *,
        height: int = 12,
    ):
        super().__init__(parent, columns=columns, show="headings", height=height)
        widths = widths or {}
        for col in columns:
            self.heading(col, text=headings.get(col, col))
            self.column(col, width=widths.get(col, 100), anchor="center")

        tema = obter_tema_atual()
        self.tag_configure("odd", background=tema["surface"])
        self.tag_configure("even", background=tema["surface"])


def add_scrollbars(table: ttk.Treeview, parent: tk.Widget, x: bool = True, y: bool = True):
    """Adiciona barras de rolagem para a tabela."""
    scroll_y = None
    scroll_x = None
    if y:
        scroll_y = ttk.Scrollbar(parent, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll_y.set)
    if x:
        scroll_x = ttk.Scrollbar(parent, orient="horizontal", command=table.xview)
        table.configure(xscrollcommand=scroll_x.set)
    return scroll_x, scroll_y


class EmptyState(tk.Frame):
    """Componente para estados vazios ou sem dados."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        subtitle: str = "",
        icon_symbol: str = "ℹ",
        action_text: str | None = None,
        action: Callable | None = None,
    ):
        tema = obter_tema_atual()
        super().__init__(parent, bg=tema["surface"], pady=24, padx=18)

        tk.Label(self, text=icon_symbol, bg=tema["surface"], fg=tema["text_muted"], font=("Segoe UI", 24)).pack(pady=(0, 6))
        tk.Label(self, text=title, bg=tema["surface"], fg=tema["text"], font=FONTES["subtitulo"]).pack(pady=(0, 4))
        if subtitle:
            tk.Label(
                self,
                text=subtitle,
                bg=tema["surface"],
                fg=tema["text_muted"],
                font=FONTES["corpo"],
                wraplength=420,
                justify="center",
            ).pack(pady=(0, 12))

        if action_text and action:
            action_button(self, text=action_text, command=action, variant="primary").pack()


class BaseModal(tk.Toplevel):
    """Janela modal base padronizada (Toplevel)."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        subtitle: str = "",
        width: int = 540,
        height: int = 420,
    ):
        super().__init__(parent)
        self.parent = parent
        tema = obter_tema_atual()

        self.title(title)
        self.configure(bg=tema["bg"])
        self.transient(parent)
        self.grab_set()

        # Centralizar na janela principal
        parent.update_idletasks()
        p_x = parent.winfo_rootx()
        p_y = parent.winfo_rooty()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()

        x = p_x + max(0, (p_w - width) // 2)
        y = p_y + max(0, (p_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(width, height)

        # Header do modal
        self.header_frame = tk.Frame(self, bg=tema["surface"], padx=18, pady=14)
        self.header_frame.pack(fill="x")

        tk.Label(self.header_frame, text=title, bg=tema["surface"], fg=tema["text"], font=FONTES["titulo"]).pack(anchor="w")
        if subtitle:
            tk.Label(
                self.header_frame,
                text=subtitle,
                bg=tema["surface"],
                fg=tema["text_muted"],
                font=FONTES["corpo"],
            ).pack(anchor="w", pady=(2, 0))

        tk.Frame(self, bg=tema["border"], height=1).pack(fill="x")

        # Body container
        self.body_frame = tk.Frame(self, bg=tema["bg"], padx=18, pady=16)
        self.body_frame.pack(fill="both", expand=True)

        # Footer container
        tk.Frame(self, bg=tema["border_soft"], height=1).pack(fill="x")
        self.footer_frame = tk.Frame(self, bg=tema["surface"], padx=18, pady=12)
        self.footer_frame.pack(fill="x")

        self.bind("<Escape>", lambda _e: self.close())

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


class SensitiveConfirmationModal(BaseModal):
    """Modal de confirmação sensível para ações arriscadas (Cancelar Venda, Restaurar Backup)."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        risk_description: str,
        confirm_label: str = "Confirmar Ação Sensível",
        cancel_label: str = "Cancelar",
        require_input_text: str | None = None,
        on_confirm: Callable[[], None] | None = None,
        badge_type: str = "ALERTA",
    ):
        super().__init__(parent, title=title, subtitle="Confirmação de ação sensível", width=520, height=360)
        self.on_confirm_callback = on_confirm
        self.require_input_text = require_input_text
        tema = obter_tema_atual()

        # Body
        body = Card(self.body_frame, padding=16)
        body.pack(fill="both", expand=True)

        top_bar = tk.Frame(body, bg=tema["surface"])
        top_bar.pack(fill="x", pady=(0, 10))

        StatusBadge(top_bar, badge_type).pack(side="left")
        tk.Label(
            top_bar,
            text="Ação Sensível",
            bg=tema["surface"],
            fg=tema["danger"] if badge_type == "CRITICO" else tema["warning"],
            font=FONTES["secao"],
        ).pack(side="left", padx=(8, 0))

        tk.Label(
            body,
            text=risk_description,
            bg=tema["surface"],
            fg=tema["text"],
            font=FONTES["corpo"],
            wraplength=440,
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        self.input_var = tk.StringVar()
        if require_input_text:
            tk.Label(
                body,
                text=f"Para confirmar, digite exatamente: {require_input_text}",
                bg=tema["surface"],
                fg=tema["text_muted"],
                font=FONTES["label"],
            ).pack(anchor="w", pady=(4, 4))
            self.input_entry = StyledEntry(body, textvariable=self.input_var)
            self.input_entry.pack(fill="x", ipady=6)

        # Footer
        action_button(
            self.footer_frame,
            text=cancel_label,
            command=self.close,
            variant="ghost",
        ).pack(side="right", padx=(8, 0))

        self.btn_confirm = action_button(
            self.footer_frame,
            text=confirm_label,
            command=self._handle_confirm,
            variant="danger" if badge_type in ("CRITICO", "CANCELADA") else "gold",
        )
        self.btn_confirm.pack(side="right")

    def _handle_confirm(self):
        if self.require_input_text:
            if self.input_var.get().strip() != self.require_input_text:
                return
        if self.on_confirm_callback:
            self.on_confirm_callback()
        self.close()


def confirmar_acao_sensivel(
    parent: tk.Widget,
    title: str,
    risk_description: str,
    confirm_label: str = "Confirmar Ação Sensível",
    on_confirm: Callable[[], None] | None = None,
    badge_type: str = "ALERTA",
    require_input_text: str | None = None,
) -> SensitiveConfirmationModal:
    """Helper para disparar um modal de confirmação sensível."""
    return SensitiveConfirmationModal(
        parent=parent,
        title=title,
        risk_description=risk_description,
        confirm_label=confirm_label,
        on_confirm=on_confirm,
        badge_type=badge_type,
        require_input_text=require_input_text,
    )


