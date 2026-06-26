"""Tema visual compartilhado da aplicacao."""

from __future__ import annotations


COLORS = {
    "brand_green": "#1F5C3A",
    "brand_green_hover": "#174D30",
    "brand_green_light": "#EAF3DE",
    "brand_gold": "#C9973A",
    "bg_page": "#F5F3EE",
    "bg_card": "#FFFFFF",
    "bg_secondary": "#F0EEE9",
    "bg_topbar": "#1C1C1A",
    "bg_statusbar": "#1C1C1A",
    "text_primary": "#1A1917",
    "text_secondary": "#5A5955",
    "text_tertiary": "#9A9890",
    "text_on_dark": "#E8E6DF",
    "text_on_dark_muted": "#7A7872",
    "text_on_dark_soft": "#C4C2BA",
    "border_subtle": "#E5E1D8",
    "border_default": "#D8D2C7",
    "success_bg": "#EAF3DE",
    "success_text": "#27500A",
    "success_dot": "#3B6D11",
    "danger_bg": "#FCEBEB",
    "danger_text": "#791F1F",
    "danger_dot": "#A32D2D",
    "warning_bg": "#FAEEDA",
    "warning_text": "#633806",
    "warning_dot": "#854F0B",
    "info_bg": "#E6F1FB",
    "info_text": "#0C447C",
    "info_dot": "#185FA5",
    "neutral_bg": "#EBE8E1",
    "neutral_text": "#6C675F",
    "neutral_dot": "#9A9890",
    "purple_bg": "#EEEDFE",
    "purple_text": "#3C3489",
}

RADII = {"sm": 6, "md": 9, "lg": 12, "xl": 14}
SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 20, "xxl": 24}

FONT_SANS = "Inter"
FONT_MONO_FAMILY = "JetBrains Mono"

FONT_TITLE = (FONT_SANS, 20, "bold")
FONT_SUBTITLE = (FONT_SANS, 16, "bold")
FONT_SECTION = (FONT_SANS, 13, "bold")
FONT_BODY = (FONT_SANS, 10)
FONT_BODY_BOLD = (FONT_SANS, 10, "bold")
FONT_SMALL = (FONT_SANS, 9)
FONT_TINY = (FONT_SANS, 8)
FONT_LABEL = (FONT_SANS, 9, "bold")
FONT_LABEL_SM = (FONT_SANS, 8, "bold")
FONT_VALUE = (FONT_MONO_FAMILY, 18, "bold")
FONT_VALUE_LG = (FONT_MONO_FAMILY, 22, "bold")
FONT_MONO = (FONT_MONO_FAMILY, 10)
FONT_MONO_SM = (FONT_MONO_FAMILY, 9)

SHADOW = {
    "card_border": COLORS["border_subtle"],
    "card_border_strong": COLORS["border_default"],
}

CARD_PADDING = 14
BORDER_COLOR = COLORS["border_default"]
BORDER_LIGHT = COLORS["border_subtle"]
INPUT_HEIGHT = 7
BUTTON_HEIGHT = 9

BUTTON_STYLES = {
    "primary": {
        "bg": COLORS["brand_green"],
        "fg": "#FFFFFF",
        "activebackground": COLORS["brand_green_hover"],
        "activeforeground": "#FFFFFF",
    },
    "secondary": {
        "bg": COLORS["bg_card"],
        "fg": COLORS["text_primary"],
        "activebackground": COLORS["bg_secondary"],
        "activeforeground": COLORS["text_primary"],
    },
    "ghost": {
        "bg": COLORS["bg_page"],
        "fg": COLORS["text_secondary"],
        "activebackground": COLORS["bg_secondary"],
        "activeforeground": COLORS["text_primary"],
    },
    "danger": {
        "bg": COLORS["danger_bg"],
        "fg": COLORS["danger_dot"],
        "activebackground": COLORS["danger_dot"],
        "activeforeground": "#FFFFFF",
    },
}

INPUT_STYLES = {
    "bg": COLORS["bg_card"],
    "fg": COLORS["text_primary"],
    "border": COLORS["border_default"],
}
TABLE_STYLES = {
    "header_bg": COLORS["bg_card"],
    "header_fg": COLORS["text_tertiary"],
    "row_height": 34,
}

TEMA_CLARO = {
    "primaria": COLORS["brand_green"],
    "primaria_media": COLORS["brand_green_hover"],
    "primaria_suave": COLORS["brand_green_light"],
    "fundo": COLORS["bg_page"],
    "fundo_secundario": COLORS["bg_secondary"],
    "surface": COLORS["bg_card"],
    "surface_hover": "#F8F6F1",
    "texto": COLORS["text_primary"],
    "texto_suave": COLORS["text_secondary"],
    "borda": COLORS["border_default"],
    "perigo": COLORS["danger_dot"],
    "perigo_suave": COLORS["danger_bg"],
    "azul": COLORS["info_dot"],
    "azul_suave": COLORS["info_bg"],
    "amarelo": COLORS["warning_dot"],
    "amarelo_suave": COLORS["warning_bg"],
    "roxo_suave": COLORS["purple_bg"],
    "neutro_suave": COLORS["neutral_bg"],
}

TEMA_ESCURO = TEMA_CLARO.copy()

FONTES = {
    "titulo": FONT_TITLE,
    "subtitulo": FONT_SUBTITLE,
    "secao": FONT_SECTION,
    "corpo": FONT_BODY,
    "corpo_bold": FONT_BODY_BOLD,
    "label": FONT_LABEL,
    "label_sm": FONT_LABEL_SM,
    "botao": FONT_BODY_BOLD,
    "numero_card": FONT_VALUE,
    "numero_card_lg": FONT_VALUE_LG,
    "mono": FONT_MONO,
    "mono_sm": FONT_MONO_SM,
}

ESPACOS = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 20, "xxl": 24}


def obter_tema(nome: str = "claro") -> dict[str, str]:
    return TEMA_ESCURO if nome == "escuro" else TEMA_CLARO


TEMA_ATUAL = obter_tema()

VERDE_ESC = TEMA_ATUAL["primaria"]
VERDE_MED = TEMA_ATUAL["primaria_media"]
VERDE_CLAR = TEMA_ATUAL["primaria_suave"]
FUNDO = TEMA_ATUAL["fundo"]
FUNDO2 = TEMA_ATUAL["fundo_secundario"]
BRANCO = TEMA_ATUAL["surface"]
TEXTO = TEMA_ATUAL["texto"]
MUTED = TEMA_ATUAL["texto_suave"]
BORDA = TEMA_ATUAL["borda"]
VERMELHO = TEMA_ATUAL["perigo"]
AZUL = TEMA_ATUAL["azul"]
AMARELO = TEMA_ATUAL["amarelo"]

STATUS_BG = {
    "CRITICO": COLORS["danger_bg"],
    "ALERTA": COLORS["warning_bg"],
    "MORTO": COLORS["neutral_bg"],
    "OK": COLORS["success_bg"],
    "INATIVO": COLORS["neutral_bg"],
}

PGTO_BG = {
    "Debito": COLORS["info_bg"],
    "Credito": COLORS["purple_bg"],
    "Pix": COLORS["success_bg"],
    "Dinheiro": COLORS["warning_bg"],
    "Mais de uma forma": "#F4E8FF",
}

PGTO_FG = {
    "Debito": COLORS["info_dot"],
    "Credito": COLORS["purple_text"],
    "Pix": COLORS["brand_green"],
    "Dinheiro": COLORS["warning_dot"],
    "Mais de uma forma": "#6B2A8F",
}

STATUS_BADGE_MAP = {
    "CRITICO": ("Crítico", "danger"),
    "CRITICAL": ("Crítico", "danger"),
    "ALERTA": ("Alerta", "warning"),
    "LOW": ("Alerta", "warning"),
    "OK": ("Normal", "success"),
    "NORMAL": ("Normal", "success"),
    "ACTIVE": ("Normal", "success"),
    "MORTO": ("Sem giro", "neutral"),
    "OUT OF STOCK": ("Sem estoque", "danger"),
    "SEM ESTOQUE": ("Sem estoque", "danger"),
    "INATIVO": ("Inativo", "neutral"),
}

TIPO_BADGE_MAP = {
    "VENDA": ("Venda", "venda"),
    "AJUSTE": ("Ajuste", "ajuste"),
    "ENTRADA": ("Entrada", "entrada"),
    "RETORNO": ("Retorno", "retorno"),
    "PERDA": ("Perda", "ajuste"),
    "INVENTARIO": ("Ajuste", "ajuste"),
    "IMPORTACAO": ("Entrada", "entrada"),
}


def status_badge_meta(status: str) -> tuple[str, str]:
    """Retorna texto e variante visual para um status."""
    return STATUS_BADGE_MAP.get(status, (status.title(), "neutral"))


def tipo_badge_meta(tipo: str) -> tuple[str, str]:
    """Retorna texto e variante visual para um tipo de movimentacao."""
    return TIPO_BADGE_MAP.get(tipo.upper(), (tipo.title(), "ajuste"))


def moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
