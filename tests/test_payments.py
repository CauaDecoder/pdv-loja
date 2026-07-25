import pytest

from app.payments import PaymentDetails, parse_currency, summarize_payment


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10", 10.0),
        ("10,50", 10.5),
        ("R$ 1.234,56", 1234.56),
    ],
)
def test_parse_currency_accepts_operational_formats(text, expected):
    assert parse_currency(text) == expected


def test_summarize_cash_payment():
    summary = summarize_payment(
        "Dinheiro",
        PaymentDetails(received=50, change=7.5),
    )

    assert summary == "Dinheiro | Recebido R$ 50,00 | Troco R$ 7,50"


def test_summarize_mixed_payment_uses_recorded_detail():
    summary = summarize_payment(
        "Mais de uma forma",
        PaymentDetails(detail="Pix + Dinheiro (Recebido R$ 20,00)"),
    )

    assert summary == "Pix + Dinheiro (Recebido R$ 20,00)"
