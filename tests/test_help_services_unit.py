import pytest

from app.common.services.help_services import (
    _clean_name,
    apply_thousand_grouping_to_display,
    format_decimal_for_display,
    parse_decimal_from_display,
)
from decimal import Decimal, InvalidOperation


@pytest.mark.parametrize(
    "source, expected",
    [
        (
            'ГПС РНГ ("Обустройство Восточных блоков Среднеботуобинского НГКМ. Энергокомплекс")',
            'ГПС РНГ («Обустройство Восточных блоков Среднеботуобинского НГКМ. Энергокомплекс»)',
        ),
        ('("Тест")', '(«Тест»)'),
        ('"Тест"', '«Тест»'),
    ],
)
def test_clean_name_quotes(source, expected):
    assert _clean_name(source) == expected


@pytest.mark.parametrize(
    "source, expected",
    [
        ("—", "—"),
        ("", ""),
        ("123", "123"),
        ("1234", "1 234"),
        ("1234567,89", "1 234 567,89"),
        ("-1234567,89", "-1 234 567,89"),
        ("0,5", "0,5"),
        ("1,234567", "1,234567"),
    ],
)
def test_apply_thousand_grouping_to_display(source, expected):
    assert apply_thousand_grouping_to_display(source) == expected


def test_format_decimal_for_display_applies_thousand_grouping():
    assert format_decimal_for_display(Decimal("1234567.89"), digits=2) == "1 234 567,89"
    assert format_decimal_for_display(Decimal("1234"), digits=-1) == "1 234"


@pytest.mark.parametrize(
    "source, expected",
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("—", None),
        ("1 234", Decimal("1234")),
        ("1 234,5", Decimal("1234.5")),
        ("1\u00a0234,56", Decimal("1234.56")),
        ("1234.5", Decimal("1234.5")),
        ("-1 234,5", Decimal("-1234.5")),
        (Decimal("10.5"), Decimal("10.5")),
        (1234, Decimal("1234")),
    ],
)
def test_parse_decimal_from_display(source, expected):
    assert parse_decimal_from_display(source) == expected


def test_parse_decimal_from_display_invalid():
    with pytest.raises(InvalidOperation):
        parse_decimal_from_display("12 34abc")

