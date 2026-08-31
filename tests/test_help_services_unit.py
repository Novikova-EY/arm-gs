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


def test_display_precision_keeps_full_k_when_cell_shows_one_digit():
    """Ячейка «1» при 1 знаке — не правка; 1.0296 вместо 1.045 — правка."""
    from app.common.services.help_services import (
        coalesce_posted_numeric_with_stored,
        format_decimal_trim_for_display,
        values_equal_by_display_precision,
    )

    stored = Decimal("1.04500427233594")
    access_k = Decimal("1.02963561999219")
    shown = format_decimal_trim_for_display(stored, digits=1)
    posted_untouched = parse_decimal_from_display(shown)

    assert values_equal_by_display_precision(stored, posted_untouched, 1)
    assert coalesce_posted_numeric_with_stored(stored, posted_untouched, 1) == stored
    assert not values_equal_by_display_precision(stored, access_k, 1)
    assert coalesce_posted_numeric_with_stored(stored, access_k, 1) == access_k


def test_display_precision_legacy_one_decimal_cell_not_a_change():
    from app.common.services.help_services import values_equal_by_display_precision

    assert values_equal_by_display_precision(
        Decimal("1683.738997"), Decimal("1683.7"), 1
    )
    assert not values_equal_by_display_precision(
        Decimal("1683.738997"), Decimal("1683.8"), 1
    )

