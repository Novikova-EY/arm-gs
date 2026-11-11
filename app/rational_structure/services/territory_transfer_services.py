from decimal import Decimal

from sqlalchemy import select

from app.common.services.database_version_services import get_current_version
from app.energy_balance.services.ee_transfers_page_services import get_ee_transfers_page_data
from app.extensions import db
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict


TERRITORY_TRANSFER_ROW_KEYS = frozenset({"7", "9"})


def load_territory_transfer_rows(version_id, zone_id, years):
    if version_id != get_current_version():
        raise ValueError("Версия исходных перетоков не совпадает с выбранной версией БД.")
    district_ids = set(db.session.scalars(select(RegionalDistrict.id).where(
        RegionalDistrict.database_version_id == version_id, RegionalDistrict.id_energy_zone == zone_id,
    )))
    res_ids = set(db.session.scalars(select(RegionalEnergySystem.id).join(
        RegionalEnergySystem.regional_districts,
    ).where(RegionalEnergySystem.database_version_id == version_id,
            RegionalDistrict.database_version_id == version_id, RegionalDistrict.id.in_(district_ids))))
    source = get_ee_transfers_page_data(
        filters={}, page=1, per_page="all", rounding_digits=0,
        start_year=min(years), end_year=max(years),
    )
    result = {key: {"cells": [None] * len(years), "details": []} for key in TERRITORY_TRANSFER_ROW_KEYS}
    for transfer in source["all_rows"]:
        # Экспорт и импорт здесь – только связи РЭС энергозоны с зарубежными странами.
        if transfer.get("from_res_id") not in res_ids or transfer.get("to_country_id") is None:
            continue
        values = [transfer["periods"].get(year) for year in years]
        values = [Decimal(str(value)) if value is not None else None for value in values]
        for key in TERRITORY_TRANSFER_ROW_KEYS:
            cells = [value if value is None or (value < 0 if key == "7" else value > 0) else Decimal(0)
                     for value in values]
            total = result[key]["cells"]
            for index, value in enumerate(cells):
                if value is not None:
                    total[index] = (total[index] or Decimal(0)) + value
            result[key]["details"].append({
                "label": f"{transfer['from_name']} – {transfer['to_name']}",
                "cells": [str(value) if value is not None else "" for value in cells],
            })
    for group in result.values():
        group["cells"] = [str(value) if value is not None else "" for value in group["cells"]]
    return result


def populate_territory_transfer_rows(context):
    if context["sheet"] != "years" or context["selected_zone"] is None or not context["years"]:
        return
    groups = load_territory_transfer_rows(context["version_id"], context["selected_zone"].id, context["years"])
    context["transfer_source_empty"] = all(value == "" for group in groups.values() for value in group["cells"])
    rows = []
    for original in context["rows"]:
        key = original["key"]
        if key not in groups:
            rows.append(original)
            continue
        group = groups[key]
        rows.append(dict(original, cells=group["cells"], readonly=True, transfer_total=True,
                         collapsible=bool(group["details"])))
        for index, detail in enumerate(group["details"]):
            rows.append(dict(detail, key=f"{key}_transfer_{index}", parent_key=key, number="",
                             unit=original["unit"], note="", section=False, virtual=True, readonly=True))
    context["rows"] = rows
