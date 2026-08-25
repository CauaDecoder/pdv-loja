"""Formatadores compartilhados, sem dependencia da interface grafica."""


def moeda(valor: float) -> str:
    """Formata um valor numerico como real brasileiro."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
