"""Названия и порядок территорий расчёта ТЭС из справочника текущей версии."""
from app.common.services.get_services.energy_systems import union_energy_system_get_services
from app.ecology.services.operating_tes_constants import TERRITORIES
from app.ecology.services.operating_tes_fuel_input_services import match_ues_slug


def get_territory_columns(territories=TERRITORIES):
    columns = [dict(item) for item in territories]
    oes_columns = [item for item in columns if item.get("group") == "territory" and item["slug"] != "vsego"]
    oes_by_slug = {item["slug"]: item for item in oes_columns}
    reference_order = {}
    for system in union_energy_system_get_services.get_union_energy_system_list_full():
        if system.name.casefold().startswith("титэс"):
            continue
        slug = match_ues_slug(system.name)
        if slug in oes_by_slug:
            oes_by_slug[slug]["sheet_name"] = system.name
            reference_order[slug] = len(reference_order)
    # Отсутствующие в справочнике ОЭС сохраняют данные и идут после найденных.
    oes_columns.sort(key=lambda item: reference_order.get(item["slug"], len(reference_order)))
    leading = [item for item in columns if item["slug"] in {"vsego", "minen", "prompred"}]
    trailing = [item for item in columns if item["slug"] not in oes_by_slug and item not in leading]
    return leading + oes_columns + trailing
