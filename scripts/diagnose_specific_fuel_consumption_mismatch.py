#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностика расхождений между загруженными (y, btp, sntp, bk, snk)
и расчётными (y_calc, btp_calc, sntp_calc, bk_calc, snk_calc) значениями.

Запуск: python scripts/diagnose_specific_fuel_consumption_mismatch.py [year]
"""
import os
import sys

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal

Q6 = Decimal("0.000001")


def _reverse_k_for_btp(param, btp_loaded):
    """
    Обратный расчёт K: при каком K btp_calc = btp_loaded?
    btp = eurt - K*(1 - ewtp/e)*100  =>  K = (eurt - btp) / ((1 - ewtp/e)*100)
    """
    eurt = param.eurt
    ewtp = param.ewtp
    e = param.e
    if eurt is None or ewtp is None or e is None or e == 0:
        return None
    try:
        btp = Decimal(str(btp_loaded))
        eurt_d = Decimal(str(eurt))
        ewtp_d = Decimal(str(ewtp))
        e_d = Decimal(str(e))
        denom = (1 - ewtp_d / e_d) * 100
        if denom == 0:
            return None
        k = (eurt_d - btp) / denom
        return float(k.quantize(Q6))
    except Exception:
        return None


def main():
    from app import create_app
    from app.extensions import db
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
    from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
        EquipmentGroupSpecificFuelConsumption,
    )
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup
    from app.fuel.services.equipment_group_specific_fuel_consumption_calc_services import (
        calc_y_calc,
        calc_btp_calc,
        calc_sntp_calc,
        calc_bk_calc,
    )

    app = create_app()
    with app.app_context():
        year = int(sys.argv[1]) if len(sys.argv) > 1 else None
        version_id = get_current_db_version_id()

        # Consumption с загруженными значениями
        cq = EquipmentGroupSpecificFuelConsumption.query
        if year:
            cq = cq.filter(EquipmentGroupSpecificFuelConsumption.year_number == year)
        if version_id is not None:
            cq = cq.filter(
                EquipmentGroupSpecificFuelConsumption.database_version_id == version_id
            )
        else:
            cq = cq.filter(
                EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None)
            )
        consumptions = cq.all()

        # Fuel params для расчёта
        pq = EquipmentGroupFuelParam.query
        if year:
            pq = pq.filter(EquipmentGroupFuelParam.year_number == year)
        if version_id is not None:
            pq = pq.filter(EquipmentGroupFuelParam.database_version_id == version_id)
        else:
            pq = pq.filter(EquipmentGroupFuelParam.database_version_id.is_(None))
        params_by_key = {
            (p.equipment_group_id, p.year_number): p for p in pq.all()
        }

        def _diff(a, b):
            if a is None and b is None:
                return None
            if a is None or b is None:
                return "None vs value"
            try:
                da = Decimal(str(a))
                db = Decimal(str(b))
                if da == db:
                    return None
                return f"{a} vs {b} (diff={float(da - db):.6f})"
            except Exception:
                return f"{a} vs {b}"

        mismatch_count = 0
        no_param_count = 0

        for c in consumptions:
            key = (c.equipment_group_id, c.year_number)
            param = params_by_key.get(key)

            if param is None:
                no_param_count += 1
                if any(
                    getattr(c, attr) is not None
                    for attr in ("y", "btp", "sntp", "bk", "snk")
                ):
                    print(
                        f"[NO PARAM] eg_id={c.equipment_group_id} year={c.year_number}: "
                        f"consumption есть, fuel param нет"
                    )
                continue

            coeff_k = c.k
            y_calc = calc_y_calc(param)
            btp_calc = calc_btp_calc(param, coeff_k)
            sntp_calc = calc_sntp_calc(param)
            bk_calc = calc_bk_calc(param, btp_calc, sntp_calc)

            diffs = []
            if (d := _diff(c.y, y_calc)):
                diffs.append(("y", d))
            if (d := _diff(c.btp, btp_calc)):
                diffs.append(("btp", d))
            if (d := _diff(c.sntp, sntp_calc)):
                diffs.append(("sntp", d))
            if (d := _diff(c.bk, bk_calc)):
                diffs.append(("bk", d))
            if (d := _diff(c.snk, param.snk)):
                diffs.append(("snk", d))

            if diffs:
                mismatch_count += 1
                eg = EquipmentGroup.query.get(c.equipment_group_id)
                name = (eg.name or eg.name_ext or "?") if eg else "?"
                print(f"\n[MISMATCH] {name} (eg_id={c.equipment_group_id}) year={c.year_number}")
                for attr, d in diffs:
                    print(f"  {attr}: {d}")
                print("  Inputs (param):", {
                    "ved": param.ved,
                    "ewtp": param.ewtp,
                    "qotr": param.qotr,
                    "e": param.e,
                    "eurt": param.eurt,
                    "eotp": param.eotp,
                    "eust": param.eust,
                    "snk": param.snk,
                })
                print("  consumption.k:", coeff_k)
                print("  consumption.snk:", c.snk)
                # Обратный расчёт K для btp
                if c.btp is not None and (d := next((x for x in diffs if x[0] == "btp"), None)):
                    k_reverse = _reverse_k_for_btp(param, c.btp)
                    if k_reverse is not None:
                        print(f"  K для совпадения btp (обратный расчёт): {k_reverse:.4f}")

        print(
            f"\n--- Итого: consumption={len(consumptions)}, "
            f"расхождений={mismatch_count}, без fuel param={no_param_count}"
        )


if __name__ == "__main__":
    main()
