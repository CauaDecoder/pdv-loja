"""Tema visual compartilhado da aplicacao."""

COLORS = {
    "bg": "#F5F3EE",
    "surface": "#FFFFFF",
    "surface_muted": "#ECEAE3",
    "header": "#1B1B1A",
    "header_hover": "#2A2825",
    "border": "#D3D1C7",
    "border_soft": "#E4E1D8",
    "text": "#1A1A1A",
    "text_on_dark": "#F6F4EF",
    "text_muted": "#767570",
    "text_muted_on_dark": "#B9B4A9",
    "primary": "#0F6E56",
    "primary_soft": "#E1F5EE",
    "danger": "#A32D2D",
    "danger_soft": "#FCEBEB",
    "warning": "#A66A00",
    "warning_soft": "#FFF5DC",
    "info": "#185FA5",
    "info_soft": "#E6F1FB",
    "success": "#2F7D4A",
    "success_soft": "#E8F5EC",
    "gold": "#D5A33B",
    "gold_soft": "#F8EFD0",
    "neutral_soft": "#EBEBEB",
    "neutral_2": "#F8F7F3",
}

FONT_FAMILY = "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 16, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 14, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_LABEL = (FONT_FAMILY, 9, "bold")
FONT_VALUE = (FONT_FAMILY, 15, "bold")
FONT_MONO = ("Consolas", 10)

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
BORDER_COLOR = COLORS["border"]
BORDER_LIGHT = "#E4E1D8"
CARD_PADDING = 14
INPUT_HEIGHT = 7
BUTTON_HEIGHT = 9
BUTTON_STYLES = {
    "primary": {"bg": COLORS["primary"], "fg": COLORS["text_on_dark"], "activebackground": COLORS["header_hover"], "activeforeground": COLORS["text_on_dark"]},
    "secondary": {"bg": COLORS["surface"], "fg": COLORS["text"], "activebackground": COLORS["neutral_2"], "activeforeground": COLORS["text"]},
    "ghost": {"bg": COLORS["bg"], "fg": COLORS["text_muted"], "activebackground": COLORS["surface_muted"], "activeforeground": COLORS["text"]},
    "danger": {"bg": COLORS["danger_soft"], "fg": COLORS["danger"], "activebackground": COLORS["danger"], "activeforeground": COLORS["text_on_dark"]},
}
INPUT_STYLES = {"bg": COLORS["surface"], "fg": COLORS["text"], "border": BORDER_COLOR}
TABLE_STYLES = {"header_bg": COLORS["surface"], "header_fg": COLORS["text"], "row_height": 30}

TEMA_CLARO = {
    "primaria": COLORS["primary"],
    "primaria_media": "#1D9E75",
    "primaria_suave": COLORS["primary_soft"],
    "fundo": COLORS["bg"],
    "fundo_secundario": COLORS["surface_muted"],
    "surface": COLORS["surface"],
    "surface_hover": COLORS["neutral_2"],
    "texto": COLORS["text"],
    "texto_suave": COLORS["text_muted"],
    "borda": COLORS["border"],
    "perigo": COLORS["danger"],
    "perigo_suave": COLORS["danger_soft"],
    "azul": COLORS["info"],
    "azul_suave": COLORS["info_soft"],
    "amarelo": COLORS["warning"],
    "amarelo_suave": COLORS["warning_soft"],
    "roxo_suave": "#EEEDFE",
    "neutro_suave": COLORS["neutral_soft"],
}

TEMA_ESCURO = {
    "primaria": "#38B68B",
    "primaria_media": "#55CAA1",
    "primaria_suave": "#183C31",
    "fundo": "#111315",
    "fundo_secundario": "#1A1D20",
    "surface": "#202428",
    "surface_hover": "#262C31",
    "texto": "#F2F2F2",
    "texto_suave": "#A8ADB2",
    "borda": "#343A40",
    "perigo": "#E06464",
    "perigo_suave": "#442627",
    "azul": "#6EA8FE",
    "azul_suave": "#1D3557",
    "amarelo": "#E0A84F",
    "amarelo_suave": "#4A3A1B",
    "roxo_suave": "#372A4A",
    "neutro_suave": "#2A2F34",
}

FONTES = {
    "titulo": FONT_TITLE,
    "subtitulo": FONT_SUBTITLE,
    "secao": (FONT_FAMILY, 12, "bold"),
    "corpo": FONT_BODY,
    "corpo_bold": (FONT_FAMILY, 10, "bold"),
    "label": FONT_LABEL,
    "label_sm": (FONT_FAMILY, 8, "bold"),
    "botao": (FONT_FAMILY, 10, "bold"),
    "numero_card": FONT_VALUE,
}

ESPACOS = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 18,
    "xl": 24,
}


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
    "CRITICO": TEMA_ATUAL["perigo_suave"],
    "ALERTA": TEMA_ATUAL["amarelo_suave"],
    "MORTO": TEMA_ATUAL["neutro_suave"],
    "OK": TEMA_ATUAL["surface"],
    "INATIVO": TEMA_ATUAL["neutro_suave"],
}

PGTO_BG = {
    "Debito": TEMA_ATUAL["azul_suave"],
    "Credito": TEMA_ATUAL["roxo_suave"],
    "Pix": TEMA_ATUAL["primaria_suave"],
    "Dinheiro": "#FAEEDA",
    "Mais de uma forma": "#F4E8FF",
}

PGTO_FG = {
    "Debito": TEMA_ATUAL["azul"],
    "Credito": "#3C3489",
    "Pix": TEMA_ATUAL["primaria"],
    "Dinheiro": "#854F0B",
    "Mais de uma forma": "#6B2A8F",
}


def moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
