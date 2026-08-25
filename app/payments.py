"""Modelo compartilhado para pagamentos da Venda no caixa."""

from __future__ import annotations

from dataclasses import dataclass

from app.formatting import moeda


CARD_BRANDS = ("Visa", "Mastercard", "Elo", "American Express", "Hipercard")
CARD_INSTALLMENTS = tuple(str(number) for number in range(1, 13))
MIXED_PAYMENT_METHODS = ("Dinheiro", "Debito", "Credito", "Pix")
PAYMENT_METHODS = (*MIXED_PAYMENT_METHODS, "Mais de uma forma")
PAYMENT_LABELS = {
    "Dinheiro": "Dinheiro",
    "Debito": "Débito",
    "Credito": "Crédito",
    "Pix": "Pix",
}


@dataclass(frozen=True)
class PaymentDetails:
    detail: str = ""
    received: float | None = None
    change: float | None = None


def parse_currency(text: str) -> float:
    """Interpreta valores como `10`, `10,50` ou `R$ 10,50`."""
    normalized = text.strip().replace("R$", "").replace(" ", "")
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    return float(normalized)


def summarize_payment(
    method: str | None,
    details: PaymentDetails,
) -> str:
    if not method:
        return "Nao selecionado"
    if method in ("Debito", "Credito") and details.detail:
        return f"{method} | {details.detail}"
    if method == "Dinheiro" and details.received is not None and details.change is not None:
        return (
            f"Dinheiro | Recebido {moeda(details.received)}"
            f" | Troco {moeda(details.change)}"
        )
    if method == "Mais de uma forma" and details.detail:
        return details.detail
    return method
