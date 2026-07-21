"""Tema visual compartilhado da aplicacao (Variante A - Command Center)."""

from __future__ import annotations

# Tokens base inspirados na Variante A "Command Center"
TEMA_CLARO = {
    # Cores de superficie e fundo
    "bg": "#F6F3EC",
    "surface": "#FFFFFF",
    "surface_2": "#F0ECE2",
    "surface_3": "#FBFAF6",
    "surface_hover": "#EBE7DC",
    # Cores de texto
    "text": "#1D1B18",
    "text_muted": "#706B62",
    "text_on_primary": "#FFFFFF",
    "text_on_dark": "#F6F4EF",
    # Bordas
    "border": "#DED7CA",
    "border_soft": "#EBE5D8",
    # Identidade (Verde / Dourado)
    "primary": "#0F6E56",
    "primary_hover": "#198262",
    "primary_soft": "#E3F4EC",
    "gold": "#C9972C",
    "gold_soft": "#F8ECD0",
    # Semantica
    "danger": "#A83333",
    "danger_soft": "#FCE9E9",
    "warning": "#9B6500",
    "warning_soft": "#FFF2D2",
    "info": "#1F638F",
    "info_soft": "#E7F0F7",
    "purple_soft": "#F4E8FF",
    "purple_fg": "#6B2A8F",
    "neutral_soft": "#EAE7DF",
    # Foco de teclado
    "focus_ring": "#C9972C",
    "focus_ring_width": 2,
    # Aliases legados para retrocompatibilidade
    "primaria": "#0F6E56",
    "primaria_media": "#198262",
    "primaria_suave": "#E3F4EC",
    "fundo": "#F6F3EC",
    "fundo_secundario": "#F0ECE2",
    "texto": "#1D1B18",
    "texto_suave": "#706B62",
    "borda": "#DED7CA",
    "perigo": "#A83333",
    "perigo_suave": "#FCE9E9",
    "azul": "#1F638F",
    "azul_suave": "#E7F0F7",
    "amarelo": "#9B6500",
    "amarelo_suave": "#FFF2D2",
    "roxo_suave": "#F4E8FF",
    "neutro_suave": "#EAE7DF",
}

TEMA_ESCURO = {
    # Cores de superficie e fundo
    "bg": "#121416",
    "surface": "#1D2224",
    "surface_2": "#252B2E",
    "surface_3": "#171A1C",
    "surface_hover": "#2C3335",
    # Cores de texto
    "text": "#F5F2EA",
    "text_muted": "#ADB2AD",
    "text_on_primary": "#121416",
    "text_on_dark": "#F5F2EA",
    # Bordas
    "border": "#373F40",
    "border_soft": "#2C3335",
    # Identidade (Verde / Dourado)
    "primary": "#4BC096",
    "primary_hover": "#66D0A9",
    "primary_soft": "#17372D",
    "gold": "#DDB04B",
    "gold_soft": "#3B3017",
    # Semantica
    "danger": "#F06F6F",
    "danger_soft": "#3D2324",
    "warning": "#E1AD4A",
    "warning_soft": "#3C3018",
    "info": "#7BB8E8",
    "info_soft": "#183040",
    "purple_soft": "#372A4A",
    "purple_fg": "#D2A8FF",
    "neutral_soft": "#2A2F34",
    # Foco de teclado
    "focus_ring": "#DDB04B",
    "focus_ring_width": 2,
    # Aliases legados para retrocompatibilidade
    "primaria": "#4BC096",
    "primaria_media": "#66D0A9",
    "primaria_suave": "#17372D",
    "fundo": "#121416",
    "fundo_secundario": "#252B2E",
    "texto": "#F5F2EA",
    "texto_suave": "#ADB2AD",
    "borda": "#373F40",
    "perigo": "#F06F6F",
    "perigo_suave": "#3D2324",
    "azul": "#7BB8E8",
    "azul_suave": "#183040",
    "amarelo": "#E1AD4A",
    "amarelo_suave": "#3C3018",
    "roxo_suave": "#372A4A",
    "neutro_suave": "#2A2F34",
}

COLORS = TEMA_CLARO

FONT_FAMILY = "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 16, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 13, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_LABEL = (FONT_FAMILY, 9, "bold")
FONT_VALUE = (FONT_FAMILY, 15, "bold")
FONT_MONO = ("Consolas", 10)

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

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
ESPACOS = SPACING

BORDER_COLOR = TEMA_CLARO["border"]
BORDER_LIGHT = TEMA_CLARO["border_soft"]
CARD_PADDING = 14
INPUT_HEIGHT = 7
BUTTON_HEIGHT = 9

BUTTON_STYLES = {
    "primary": {
        "bg": TEMA_CLARO["primary"],
        "fg": TEMA_CLARO["text_on_primary"],
        "activebackground": TEMA_CLARO["primary_hover"],
        "activeforeground": TEMA_CLARO["text_on_primary"],
    },
    "secondary": {
        "bg": TEMA_CLARO["surface_2"],
        "fg": TEMA_CLARO["text"],
        "activebackground": TEMA_CLARO["surface_hover"],
        "activeforeground": TEMA_CLARO["text"],
    },
    "ghost": {
        "bg": TEMA_CLARO["bg"],
        "fg": TEMA_CLARO["text_muted"],
        "activebackground": TEMA_CLARO["surface_2"],
        "activeforeground": TEMA_CLARO["text"],
    },
    "danger": {
        "bg": TEMA_CLARO["danger_soft"],
        "fg": TEMA_CLARO["danger"],
        "activebackground": TEMA_CLARO["danger"],
        "activeforeground": "#FFFFFF",
    },
    "gold": {
        "bg": TEMA_CLARO["gold"],
        "fg": "#FFFFFF",
        "activebackground": "#A87A1E",
        "activeforeground": "#FFFFFF",
    },
}

INPUT_STYLES = {"bg": TEMA_CLARO["surface_3"], "fg": TEMA_CLARO["text"], "border": BORDER_COLOR}
TABLE_STYLES = {"header_bg": TEMA_CLARO["surface_2"], "header_fg": TEMA_CLARO["text"], "row_height": 34}

NOME_TEMA_ATUAL = "claro"
TEMA_ATUAL = dict(TEMA_CLARO)
_THEME_LISTENERS = []


def obter_tema(nome: str = "claro") -> dict[str, str]:
    return TEMA_ESCURO if nome == "escuro" else TEMA_CLARO


def obter_tema_atual() -> dict[str, str]:
    return TEMA_ATUAL


def obter_nome_tema_atual() -> str:
    return NOME_TEMA_ATUAL


def registrar_listener_tema(listener):
    if listener not in _THEME_LISTENERS:
        _THEME_LISTENERS.append(listener)


def remover_listener_tema(listener):
    if listener in _THEME_LISTENERS:
        _THEME_LISTENERS.remove(listener)


def definir_tema_atual(nome: str) -> dict[str, str]:
    global NOME_TEMA_ATUAL, VERDE_ESC, VERDE_MED, VERDE_CLAR
    global FUNDO, FUNDO2, BRANCO, TEXTO, MUTED, BORDA, VERMELHO, AZUL, AMARELO
    global STATUS_BG, PGTO_BG, PGTO_FG, COLORS, BORDER_COLOR, BORDER_LIGHT

    NOME_TEMA_ATUAL = "escuro" if nome == "escuro" else "claro"
    novo_tema = TEMA_ESCURO if NOME_TEMA_ATUAL == "escuro" else TEMA_CLARO
    TEMA_ATUAL.clear()
    TEMA_ATUAL.update(novo_tema)
    COLORS = TEMA_ATUAL

    VERDE_ESC = TEMA_ATUAL["primary"]
    VERDE_MED = TEMA_ATUAL["primary_hover"]
    VERDE_CLAR = TEMA_ATUAL["primary_soft"]
    FUNDO = TEMA_ATUAL["bg"]
    FUNDO2 = TEMA_ATUAL["surface_2"]
    BRANCO = TEMA_ATUAL["surface"]
    TEXTO = TEMA_ATUAL["text"]
    MUTED = TEMA_ATUAL["text_muted"]
    BORDA = TEMA_ATUAL["border"]
    BORDER_COLOR = TEMA_ATUAL["border"]
    BORDER_LIGHT = TEMA_ATUAL["border_soft"]
    VERMELHO = TEMA_ATUAL["danger"]
    AZUL = TEMA_ATUAL["info"]
    AMARELO = TEMA_ATUAL["warning"]

    STATUS_BG = {
        "CRITICO": TEMA_ATUAL["danger_soft"],
        "ALERTA": TEMA_ATUAL["warning_soft"],
        "MORTO": TEMA_ATUAL["neutral_soft"],
        "OK": TEMA_ATUAL["primary_soft"],
        "INATIVO": TEMA_ATUAL["neutral_soft"],
    }

    PGTO_BG = {
        "Debito": TEMA_ATUAL["info_soft"],
        "Credito": TEMA_ATUAL["purple_soft"],
        "Pix": TEMA_ATUAL["primary_soft"],
        "Dinheiro": TEMA_ATUAL["gold_soft"],
        "Mais de uma forma": TEMA_ATUAL["purple_soft"],
    }

    PGTO_FG = {
        "Debito": TEMA_ATUAL["info"],
        "Credito": TEMA_ATUAL["purple_fg"],
        "Pix": TEMA_ATUAL["primary"],
        "Dinheiro": TEMA_ATUAL["gold"],
        "Mais de uma forma": TEMA_ATUAL["purple_fg"],
    }

    for listener in list(_THEME_LISTENERS):
        try:
            listener(TEMA_ATUAL, NOME_TEMA_ATUAL)
        except Exception:
            pass

    return TEMA_ATUAL


# Inicializacao das variaveis no escopo global do modulo
VERDE_ESC = TEMA_ATUAL["primary"]
VERDE_MED = TEMA_ATUAL["primary_hover"]
VERDE_CLAR = TEMA_ATUAL["primary_soft"]
FUNDO = TEMA_ATUAL["bg"]
FUNDO2 = TEMA_ATUAL["surface_2"]
BRANCO = TEMA_ATUAL["surface"]
TEXTO = TEMA_ATUAL["text"]
MUTED = TEMA_ATUAL["text_muted"]
BORDA = TEMA_ATUAL["border"]
VERMELHO = TEMA_ATUAL["danger"]
AZUL = TEMA_ATUAL["info"]
AMARELO = TEMA_ATUAL["warning"]

STATUS_BG = {
    "CRITICO": TEMA_ATUAL["danger_soft"],
    "ALERTA": TEMA_ATUAL["warning_soft"],
    "MORTO": TEMA_ATUAL["neutral_soft"],
    "OK": TEMA_ATUAL["primary_soft"],
    "INATIVO": TEMA_ATUAL["neutral_soft"],
}

PGTO_BG = {
    "Debito": TEMA_ATUAL["info_soft"],
    "Credito": TEMA_ATUAL["purple_soft"],
    "Pix": TEMA_ATUAL["primary_soft"],
    "Dinheiro": TEMA_ATUAL["gold_soft"],
    "Mais de uma forma": TEMA_ATUAL["purple_soft"],
}

PGTO_FG = {
    "Debito": TEMA_ATUAL["info"],
    "Credito": TEMA_ATUAL["purple_fg"],
    "Pix": TEMA_ATUAL["primary"],
    "Dinheiro": TEMA_ATUAL["gold"],
    "Mais de uma forma": TEMA_ATUAL["purple_fg"],
}


def moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

