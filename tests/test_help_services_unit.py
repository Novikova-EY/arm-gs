import pytest

from app.common.services.help_services import _clean_name


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
