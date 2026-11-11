"""Столбцы таблицы наработки; буквенные ключи сохранены для совместимости экспорта."""

from app.rational_structure.services.technical_characteristic_columns import BASE_LABELS


RUNTIME_CHARACTERISTIC_FIELDS = {
    "M": "commissioning_year",
    "S": "standard_service_life",
    "T": "operating_hours_total",
    "U": "operating_hours_year",
    "V": "expected_service_life_year",
}

RUNTIME_COLUMNS = (
    ("A", "Энергозона"),
    ("B", "Субъект РФ"),
    ("C", "Код оборудования"),
    ("E", "Вид оборудования"),
    ("F", "Субъект ЭЭ"),
    ("G", "Объект ЭЭ"),
    ("H", "Станционный номер"),
    ("K", "Группа оборудования"),
    ("L", "Тип (марка) оборудования"),
    ("N", "Установленная электрическая мощность,  МВт"),
    ("AM", "Основной вид топлива"),
    *((key, BASE_LABELS[field]) for key, field in RUNTIME_CHARACTERISTIC_FIELDS.items()),
    ("AN", "Среднегодовая наработка за три года, ч"),
    ("AO", "Остаток до достижения двойного ресурса, ч/лет"),
    ("AP", "Расчетный год демонтажа по ресурсу"),
    ("AQ", "Год достижения первого нормативного ресурса"),
    ("AR", "Расчетный год модернизации до 2043 года"),
    ("AS", "Расчетный год модернизации с учетом СиПР"),
    ("planned_modernization_year", "Плановый год модернизации"),
    ("AT", "Плановый год окончательного вывода"),
    ("AU", "Плановый год ввода оборудования"),
    ("AV", "Плановый год вывода при замене"),
    ("AW", "Год демонтажа угольного оборудования"),
    ("AX", "Год демонтажа неугольного оборудования"),
    ("AY", "Базовый год демонтажа"),
    ("AZ", "Год демонтажа с учетом КОМ"),
    ("BA", "Год демонтажа с учетом СиПР"),
    ("BC", "Расчетный год демонтажа с учетом модернизации"),
    ("BD", "Достигнут 70-летний срок эксплуатации – уголь"),
    ("BF", "Достигнут двойной нормативный ресурс"),
)

CALCULATION_TOGGLE_COLUMNS = frozenset(RUNTIME_CHARACTERISTIC_FIELDS) | frozenset((
    "AN", "AO", "AP", "AQ", "AR", "planned_modernization_year", "AT", "AU", "AV", "AW", "AX", "AY", "AZ", "BA", "BD", "BF",
))

TEXT_COLUMNS = frozenset(("A", "B", "C", "E", "F", "G", "H", "K", "L", "AM", "S", "BD", "BF"))
NUMBER_COLUMNS = frozenset(("N", "T", "U", "AN", "AO"))
YEAR_COLUMNS = frozenset(("M", "V", "AP", "AQ", "AR", "AS", "planned_modernization_year", "AT", "AU", "AV", "AW", "AX", "AY", "AZ", "BA", "BC"))


def runtime_columns(general_scheme_end_year=None):
    modernization_year = general_scheme_end_year + 1 if general_scheme_end_year is not None else 2043
    return [{"key": key,
             "label": f"Расчетный год модернизации до {modernization_year} года" if key == "AR" else label,
             "highlight_color": {"AS": "C6E0B4", "BC": "FCE4D6"}.get(key),
             "calculation_toggle": key in CALCULATION_TOGGLE_COLUMNS,
             "text": key in TEXT_COLUMNS,
             "year": key in YEAR_COLUMNS,
             "integer": key not in TEXT_COLUMNS | NUMBER_COLUMNS}
            for key, label in RUNTIME_COLUMNS]
