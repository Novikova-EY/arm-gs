from app.fuel.services.fuel_imports.excel_import_helpers import normalize_import_column_name
from app.rational_structure.equipment_types import SHEET_TYPES


TURBINE_TYPES = {"steam": "Паровые турбины", "gas": "Газовые турбины"}

COLUMNS = (
    ("equipment_code", "Код оборудования", "text"),
    ("report_year", "Год предоставления отчетности", "integer"),
    ("equipment_kind", "Вид оборудования", "text"),
    ("subject_name", "Субъект ЭЭ", "text"),
    ("station_name", "Объект ЭЭ", "text"),
    ("station_number", "Станционный номер", "text"),
    ("equipment_subclass", "Подкласс оборудования", "text"),
    ("equipment_brand", "Тип (марка) оборудования", "text"),
    ("commissioning_year", "Год ввода оборудования в эксплуатацию", "integer"),
    ("installed_electric_power", "Установленная электрическая мощность, МВт", "number"),
    ("nominal_active_power", "Номинальная активная мощность, МВт", "number"),
    ("technical_min_power", "Технический минимум мощности, МВт", "number"),
    ("technical_max_power", "Технический максимум мощности, МВт", "number"),
    ("total_heat_power", "Установленная тепловая мощность, Гкал/ч / всего отборы", "number"),
    ("district_heat_power", "Установленная тепловая мощность, Гкал/ч / теплофикационные отборы", "number"),
    ("electricity_generation", "Выработка электрической энергии за отчетный год, тыс. кВт*ч", "number"),
    ("heat_output", "Отпуск тепла из отборов турбин за отчетный год, Гкал", "number"),
    ("standard_service_life", "Нормативный срок службы (парковый ресурс), лет (ч)", "text"),
    ("operating_hours_total", "Наработка с начала эксплуатации, ч", "number"),
    ("operating_hours_year", "Наработка за отчетный год, ч", "number"),
    ("expected_service_life_year", "Ожидаемый год достижения нормативного/назначенного срока службы (ресурса)", "integer"),
    ("standard_start_count", "Норматив количества пусков, шт.", "number"),
    ("start_count_total", "Количество пусков с начала эксплуатации, шт.", "number"),
    ("start_count_year", "Количество пусков в отчетном году, шт.", "number"),
    ("standard_overhaul_hours", "Нормативный межремонтный ресурс, ч", "number"),
    ("last_overhaul_year", "Год проведения последнего капитального ремонта", "integer"),
    ("hours_since_overhaul", "Наработка с последнего капитального ремонта на конец отчетного года, ч", "number"),
    ("extension_count", "Продление паркового (назначенного) ресурса / количество продлений, шт.", "number"),
    ("extension_decision", "Продление паркового (назначенного) ресурса / номер и дата решения (эксплуатирующей организации) о продлении срока службы (ресурса)", "text"),
    ("assigned_service_life", "Продление паркового (назначенного) ресурса / Назначенный срок службы (ресурс) на конец отчетного года, лет (ч)", "text"),
    ("element_replacement_year", "Год замены ресурсоопределяющего элемента турбины", "integer"),
    ("replaced_element", "Наименование замененного ресурсоопределяющего элемента турбины", "text"),
    ("remarking_year", "Год перемаркировки", "integer"),
    ("remarking_reason", "Причина перемаркировки", "text"),
    ("decommissioning_year", "Год вывода из эксплуатации", "integer"),
    ("decommissioning_reason", "Причина вывода из эксплуатации", "text"),
    ("recommissioning", "Повторный ввод в эксплуатацию", "text"),
)

_SPECIFIC_COLUMNS = (
    ("design_head", "Расчетный напор, м", "number"),
    ("steam_capacity", "Паропроизводительность, т/ч", "number"),
    ("heat_power", "Тепловая мощность, Гкал/ч", "number"),
    ("fuel_project", "Топливо / проектное", "text"),
    ("fuel_main", "Топливо / основное", "text"),
    ("fuel_reserve", "Топливо / резервное", "text"),
    ("efficiency_gross", "КПД брутто, %", "number"),
    ("water_consumption", "Расход воды, т/ч", "number"),
    ("operation_mode", "Режим работы", "text"),
)
ALL_COLUMNS = COLUMNS + _SPECIFIC_COLUMNS
BASE_LABELS = {attr: label for attr, label, _ in ALL_COLUMNS}
_COMMON_FIELDS = (
    "equipment_code", "report_year", "equipment_kind", "subject_name", "station_name",
    "station_number", "equipment_subclass", "equipment_brand", "commissioning_year",
)
_RESOURCE_FIELDS = tuple(attr for attr, _, _ in COLUMNS[17:])
_COLUMNS_BY_FIELD = {attr: (attr, label, kind) for attr, label, kind in ALL_COLUMNS}
_KIND_FIELDS = {
    "hydro": ("installed_electric_power", "design_head", "electricity_generation"),
    "boiler_energy": ("steam_capacity", "fuel_project", "fuel_main", "fuel_reserve",
                      "efficiency_gross", "heat_output"),
    "boiler_water": ("heat_power", "water_consumption", "operation_mode", "fuel_project",
                     "fuel_main", "fuel_reserve", "efficiency_gross", "heat_output"),
}


def columns_for_equipment(equipment_type: str) -> tuple:
    if equipment_type in TURBINE_TYPES:
        return COLUMNS
    columns = tuple(_COLUMNS_BY_FIELD[attr] for attr in
                    _COMMON_FIELDS + _KIND_FIELDS[equipment_type] + _RESOURCE_FIELDS)
    if equipment_type == "hydro":
        columns = tuple((attr, "Установленная мощность, МВт" if attr == "installed_electric_power" else label, kind)
                        for attr, label, kind in columns)
    return columns


HEADER_FIELDS = {}
for attr, label, _ in ALL_COLUMNS:
    HEADER_FIELDS[normalize_import_column_name(label)] = attr
    if " / " in label:
        HEADER_FIELDS[normalize_import_column_name(label.split(" / ", 1)[1])] = attr
for label, attr in {
    "Установленная мощность, МВт": "installed_electric_power",
    "Расчетный напор, м": "design_head",
    "Проектное топливо": "fuel_project",
    "Основное топливо": "fuel_main",
    "Резервное топливо": "fuel_reserve",
    "Отпуск тепла за отчетный год, Гкал": "heat_output",
    "Нормативный срок службы, лет": "standard_service_life",
}.items():
    HEADER_FIELDS[normalize_import_column_name(label)] = attr
