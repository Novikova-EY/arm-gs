#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор формулы «Первая СЗ с/без НТ с/без заряда ГАЭС» за указанный год."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
ROUNDING = int(sys.argv[2]) if len(sys.argv) > 2 else 1


def _fmt(v) -> str:
    if v is None:
        return "—"
    q = Decimal(str(v)).quantize(Decimal("0.1") if ROUNDING == 1 else Decimal("0.01"))
    s = f"{q:,.1f}".replace(",", " ").replace(".", ",")
    return s


def _used_variant_code(ues_id: int, variant_codes: tuple, year: int) -> str | None:
    from app.energy_consumption.services import energy_consumption_parameter_services as dps
    from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
        UnionEnergySystemEnergyConsumptionParameter,
    )

    for code in variant_codes:
        rows = dps.get_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            int(ues_id),
            perimeter_variant_code=code,
        )
        for row in rows:
            if getattr(row, "year_number", None) == year:
                if getattr(row, "energy_consumption_mln_kvt_ch", None) is not None:
                    return code or "(default)"
    return None


def main() -> None:
    from sqlalchemy import func

    from app import create_app
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.energy_consumption.services import energy_consumption_parameter_services as dps
    from app.energy_consumption.models.energy_systems.synchronous_area_energy_consumption_parameter_model import (
        SynchronousAreaEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
        UnionEnergySystemEnergyConsumptionParameter,
    )
    from app.generation.models.station.station_gaes_charge_consumption_model import (
        StationGaesChargeConsumption,
    )
    from app.energy_consumption.services import energy_consumption_summary_services as svc
    from app.extensions import db
    from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem

    app = create_app()
    with app.app_context():
        version_id = get_current_db_version_id()
        years = [YEAR]
        first_sa_id = svc._resolve_first_synchronous_area_id()
        if first_sa_id is None:
            print("Первая СЗ не найдена в справочнике.")
            return

        south_ues_id = svc._resolve_union_energy_system_id_by_name_cf(svc.SOUTH_UES_NAME_CF)

        print(f"Версия БД: {version_id}")
        print(f"Первая СЗ id: {first_sa_id}")
        print(f"ОЭС Юга id: {south_ues_id}")
        print(f"Год: {YEAR}, округление на экране: {ROUNDING} знак(ов)")
        print()

        print("=" * 72)
        print("1. Первая СЗ с НТ с зарядом ГАЭС")
        print("   Формула: Σ потреблений ОЭС 1-й СЗ (без ОЭС Востока и ОЭС «Новые территории»);")
        print("   ОЭС Юга → with_nt_with_gaes; остальные ОЭС → with_nt")
        print("=" * 72)

        ues_ids = svc._union_energy_system_ids_for_synchronous_area(first_sa_id)
        exclude = svc._first_sa_with_nt_with_gaes_ues_exclude_ids()

        for ues_id in ues_ids:
            ues = UnionEnergySystem.query.get(int(ues_id))
            ues_name = ues.name if ues else str(ues_id)
            if int(ues_id) in exclude:
                print(f"  [исключён] {ues_name}")
                continue

            variant_codes = svc._first_sa_with_nt_with_gaes_ues_variant_codes_for_ues_id(
                int(ues_id)
            )
            values = svc._year_values_from_ues_demand_first_variant_with_data(
                int(ues_id),
                years,
                "energy_consumption_mln_kvt_ch",
                variant_codes,
            )
            val = values.get(YEAR)
            used = _used_variant_code(int(ues_id), variant_codes, YEAR)
            south_mark = " ← ОЭС Юга" if south_ues_id == int(ues_id) else ""
            print(
                f"  + {ues_name}{south_mark}: {_fmt(val)} "
                f"(вариант периметра: {used or '—'})"
            )

        summed = svc._year_values_sum_ues_in_first_sa_with_nt_with_gaes_with_kaliningrad_es(
            first_sa_id,
            years,
            "energy_consumption_mln_kvt_ch",
        )
        with_gaes_raw = summed.get(YEAR)
        with_gaes_rounded = (
            Decimal(str(with_gaes_raw)).quantize(Decimal("0.1"))
            if with_gaes_raw is not None
            else None
        )
        print(
            f"\n  ИТОГО Σ ОЭС: {_fmt(with_gaes_raw)} "
            f"→ на экране после округления: {_fmt(with_gaes_rounded)}"
        )
        print()

        print("=" * 72)
        print("2. Заряд ГАЭС 1-й СЗ (с НТ) — для строки «без заряда»")
        print("   Формула: строка «всего» в блоке «Первая СЗ с НТ (заряд ГАЭС)»")
        print("=" * 72)

        gaes_rows: list[dict] = []
        gaes_sum_stations = Decimal(0)
        for ues_id in ues_ids:
            stations = svc._gaes_stations_for_entity_query(
                UnionEnergySystemEnergyConsumptionParameter.__name__,
                int(ues_id),
            )
            if stations is None:
                continue
            ues = UnionEnergySystem.query.get(int(ues_id))
            ues_name = ues.name if ues else str(ues_id)
            for station_id, station_name in stations.all():
                cq = (
                    db.session.query(
                        func.sum(StationGaesChargeConsumption.charge_consumption)
                    )
                    .filter(StationGaesChargeConsumption.id_station == int(station_id))
                    .filter(StationGaesChargeConsumption.year_number == YEAR)
                )
                cq = dps.filter_parents_by_version(cq, StationGaesChargeConsumption)
                charge_val = cq.scalar()
                if charge_val is None:
                    continue
                charge_dec = Decimal(str(charge_val))
                gaes_sum_stations += charge_dec
                gaes_rows.append(
                    {
                        "demand_model_name": SynchronousAreaEnergyConsumptionParameter.__name__,
                        "parent_id": first_sa_id,
                        "entity_label": "Первая синхронная зона с НТ (заряд ГАЭС)",
                        "parameter_key": svc.GAES_CHARGE_PARAMETER_KEY,
                        "gaes_charge_row_station_name": station_name,
                        "gaes_station_id": int(station_id),
                        "year_values": [str(charge_dec)],
                        "year_numeric_tooltips": [str(charge_dec)],
                    }
                )
                print(f"  + {station_name} ({ues_name}): {_fmt(charge_dec)}")

        gaes_rows.append(
            {
                "demand_model_name": SynchronousAreaEnergyConsumptionParameter.__name__,
                "parent_id": first_sa_id,
                "entity_label": "Первая синхронная зона с НТ (заряд ГАЭС)",
                "parameter_key": svc.GAES_CHARGE_PARAMETER_KEY,
                "gaes_charge_row_station_name": "всего",
                "year_values": [str(gaes_sum_stations)],
                "year_numeric_tooltips": [str(gaes_sum_stations)],
            }
        )
        gaes_by_year = svc._gaes_charge_year_values_for_first_sa_with_nt(
            gaes_rows, years, first_sa_id=first_sa_id
        )
        gaes_val = gaes_by_year.get(YEAR)
        print(f"\n  ИТОГО заряд (всего): {_fmt(gaes_val)}")
        print()

        print("=" * 72)
        print("3. Первая СЗ с НТ без заряда ГАЭС")
        print("   Формула: [п.1 «с зарядом»] − [п.2 «заряд ГАЭС всего»]")
        print("=" * 72)
        if with_gaes_raw is not None and gaes_val is not None:
            diff_raw = Decimal(str(with_gaes_raw)) - Decimal(str(gaes_val))
            diff_rounded = diff_raw.quantize(Decimal("0.1"))
            print(f"  {_fmt(with_gaes_raw)} − {_fmt(gaes_val)} = {_fmt(diff_raw)}")
            print(f"  → на экране: {_fmt(diff_rounded)}")
        print()

        print("=" * 72)
        print("4. Значения, сохранённые в БД (если есть)")
        print("=" * 72)
        for code, label in (
            ("with_nt_with_gaes_kaliningrad", "с НТ с зарядом ГАЭС"),
            ("with_nt_without_gaes_kaliningrad", "с НТ без заряда ГАЭС"),
        ):
            rows = dps.get_demand_rows(
                SynchronousAreaEnergyConsumptionParameter,
                "id_synchronous_area",
                first_sa_id,
                perimeter_variant_code=code,
            )
            found = False
            for row in rows:
                if getattr(row, "year_number", None) != YEAR:
                    continue
                val = getattr(row, "energy_consumption_mln_kvt_ch", None)
                print(f"  {label} [{code}]: {_fmt(val)}")
                found = True
            if not found:
                print(f"  {label} [{code}]: — (нет строки в БД)")

        print()
        print("Сравнение с Excel (ожидание):")
        print("  с НТ с зарядом ГАЭС:  1 108 709,99")
        print("  с НТ без заряда ГАЭС: 1 085 496,00")
        if with_gaes_raw is not None:
            excel_with = Decimal("1108709.99")
            diff = Decimal(str(with_gaes_raw)) - excel_with
            print(f"\n  Δ Σ ОЭС vs Excel: {_fmt(diff)} млн кВт·ч")


if __name__ == "__main__":
    main()
