#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Однократное копирование параметров нагрузки (схема power_demand, gs_pd_*):

1) Все строки с заданным database_version_id (по умолчанию 20) копируются в каждую
   другую зарегистрированную версию БД. Существующие строки с тем же естественным ключом
   (версия + привязка к справочнику + исторический максимум/год) обновляются данными
   с источника. FK на справочники refdata пересчитываются через ref_uuid
   (fk_id_for_version).

2) Для каждой версии БД: для каждой РЭС, в которую входит ровно один субъект РФ,
   в соответствующую строку RegionalDistrictDemandParameter записываются те же
   показатели, что и в RegionalEnergySystemDemandParameter (совмещённый на ЭЗ с РЭС
   копируется в combined_on_es субъекта).

Запуск из корня репозитория:

  python scripts/copy_power_demand_params_from_version_to_all_others.py --dry-run
  python scripts/copy_power_demand_params_from_version_to_all_others.py --apply --yes

По умолчанию источник: --source-version 20 (id строки в gs_sys.gs_database_versions).

Дополнительно:
  --no-mirror   — только шаг 1, без дублирования РЭС -> субъект
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional, Type

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
    CentralizedZoneDemandParameter,
)
from app.power_demand.models.energy_systems.ees_demand_parameter_model import (
    EesDemandParameter,
)
from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
    EesRussiaDemandParameter,
)
from app.power_demand.models.energy_systems.ees_russia_with_nt_demand_parameter_model import (
)
from app.power_demand.models.energy_systems.energy_area_demand_parameter_model import (
    EnergyAreaDemandParameter,
)
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.power_demand.models.energy_systems.energy_unit_demand_parameter_model import (
    EnergyUnitDemandParameter,
)
from app.power_demand.models.energy_systems.energy_zone_demand_parameter_model import (
    EnergyZoneDemandParameter,
)
from app.power_demand.models.energy_systems.regional_energy_system_demand_parameter_model import (
    RegionalEnergySystemDemandParameter,
)
from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.power_demand.models.territories.federal_district_demand_parameter_model import (
    FederalDistrictDemandParameter,
)
from app.power_demand.models.territories.regional_district_demand_parameter_model import (
    RegionalDistrictDemandParameter,
)
from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
    RussiaFederationDemandParameter,
)
from app.power_demand.services.demand_parameter_services import (
    _single_regional_district_id_for_res,
)
from app.refdata.models.energy_systems.energy_area_model import EnergyArea
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.services.refdata_all_versions_common import fk_id_for_version
from app.common.services.tranzaction_services import _commit_with_retry, quick_fix_seq
from config import SCHEMA_POWER_DEMAND

SCRIPT_USER = "script:copy_power_demand_params_from_version"


def _align_gs_pd_id_sequences() -> None:
    """Подгоняет SERIAL/sequence для id под MAX(id) в каждой таблице gs_pd (иначе nextval даёт занятый id)."""
    seen: set[str] = set()
    for model, _ in MODEL_FK_SPECS:
        t = model.__tablename__
        if t in seen:
            continue
        seen.add(t)
        quick_fix_seq(SCHEMA_POWER_DEMAND, t, "id")

# Порядок не критичен; все таблицы независимы по FK друг на друга внутри gs_pd.
MODEL_FK_SPECS: list[tuple[Type[Any], tuple[tuple[str, Type[Any]], ...]]] = [
    (UnionEnergySystemDemandParameter, (("id_union_energy_system", UnionEnergySystem),)),
    (
        RegionalEnergySystemDemandParameter,
        (("id_regional_energy_system", RegionalEnergySystem),),
    ),
    (RegionalDistrictDemandParameter, (("id_regional_district", RegionalDistrict),)),
    (FederalDistrictDemandParameter, (("id_federal_district", FederalDistrict),)),
    (EnergyZoneDemandParameter, (("id_energy_zone", EnergyZone),)),
    (SynchronousAreaDemandParameter, (("id_synchronous_area", SynchronousArea),)),
    (EnergySystemTypeDemandParameter, (("id_energy_system_type", EnergySystemType),)),
    (EnergyUnitDemandParameter, (("id_energy_unit", EnergyUnit),)),
    (EnergyAreaDemandParameter, (("id_energy_area", EnergyArea),)),
    (EesDemandParameter, ()),
    (CentralizedZoneDemandParameter, ()),
    (EesRussiaDemandParameter, ()),
    (RussiaFederationDemandParameter, ()),
]


def _find_existing_demand_row(
    model: Type[Any],
    *,
    database_version_id: int,
    fk_values: dict[str, int],
    is_hist: bool,
    year_n: Optional[int],
    perimeter_variant_code: Optional[str] = None,
) -> Any:
    q = model.query.filter(model.database_version_id == database_version_id)
    q = q.filter(model.is_historical_maximum == is_hist)
    if is_hist:
        q = q.filter(model.year_number.is_(None))
    else:
        q = q.filter(model.year_number == year_n)
    for col, val in fk_values.items():
        q = q.filter(getattr(model, col) == val)
    if hasattr(model, "perimeter_variant_code"):
        pvc = perimeter_variant_code
        if pvc is None:
            q = q.filter(model.perimeter_variant_code.is_(None))
        else:
            q = q.filter(model.perimeter_variant_code == pvc)
    return q.first()


def _apply_src_onto_dst(
    src: Any,
    dst: Any,
    model: Type[Any],
    *,
    target_vid: int,
    mapped_fk: dict[str, int],
    script_user: str,
) -> None:
    skip = {"id", "created_at", "updated_at"}
    for col in model.__table__.columns:
        name = col.name
        if name in skip:
            continue
        if name == "database_version_id":
            dst.database_version_id = target_vid
            continue
        if name in mapped_fk:
            setattr(dst, name, mapped_fk[name])
            continue
        if name in ("created_by", "modified_by"):
            continue
        setattr(dst, name, getattr(src, name))
    dst.modified_by = script_user
    if getattr(dst, "id", None) is None:
        dst.created_by = script_user


def copy_from_source_to_other_versions(
    *,
    source_vid: int,
    target_vids: list[int],
    apply_changes: bool,
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    inserted = defaultdict(int)
    updated = defaultdict(int)
    skipped_fk = defaultdict(int)

    for model, fk_spec in MODEL_FK_SPECS:
        sources = (
            model.query.filter(model.database_version_id == source_vid)
            .order_by(model.id.asc())
            .all()
        )
        if not sources:
            continue
        mname = model.__name__
        for tgt in target_vids:
            for src in sources:
                mapped_fk: dict[str, int] = {}
                try:
                    # Иначе session.get() внутри fk_id_for_version вызывает autoflush и срывает INSERT при «битом» sequence.
                    with db.session.no_autoflush:
                        for fk_col, ref_cls in fk_spec:
                            mapped_fk[fk_col] = int(
                                fk_id_for_version(
                                    ref_cls,
                                    int(getattr(src, fk_col)),
                                    int(tgt),
                                )
                            )
                except ValueError as e:
                    skipped_fk[mname] += 1
                    print(
                        f"  [skip {mname}] версия {tgt} <- строка src id={src.id}: {e}",
                    )
                    continue

                existing = _find_existing_demand_row(
                    model,
                    database_version_id=tgt,
                    fk_values=mapped_fk,
                    is_hist=bool(src.is_historical_maximum),
                    year_n=None if src.is_historical_maximum else src.year_number,
                    perimeter_variant_code=getattr(src, "perimeter_variant_code", None),
                )
                if apply_changes:
                    if existing is None:
                        dst = model()
                        _apply_src_onto_dst(
                            src, dst, model, target_vid=tgt, mapped_fk=mapped_fk, script_user=SCRIPT_USER
                        )
                        db.session.add(dst)
                        inserted[mname] += 1
                    else:
                        _apply_src_onto_dst(
                            src,
                            existing,
                            model,
                            target_vid=tgt,
                            mapped_fk=mapped_fk,
                            script_user=SCRIPT_USER,
                        )
                        updated[mname] += 1
                else:
                    if existing is None:
                        inserted[mname] += 1
                    else:
                        updated[mname] += 1

    return dict(inserted), dict(updated), dict(skipped_fk)


def mirror_res_to_single_regional_district(*, apply_changes: bool) -> dict[str, int]:
    """
    Для каждой версии БД: РЭС с одним субъектом — копируем поля из RES в RD.
    """
    stats = defaultdict(int)
    vids = [
        int(v.id)
        for v in DatabaseVersion.query.order_by(DatabaseVersion.id.asc()).all()
        if v.id is not None
    ]
    rd_model = RegionalDistrictDemandParameter
    res_model = RegionalEnergySystemDemandParameter

    for vid in vids:
        res_rows = (
            res_model.query.filter(res_model.database_version_id == vid)
            .order_by(res_model.id.asc())
            .all()
        )
        for res_row in res_rows:
            rd_pk = _single_regional_district_id_for_res(
                int(res_row.id_regional_energy_system),
                database_version_id=int(vid),
            )
            if rd_pk is None:
                continue

            fk_map = {"id_regional_district": int(rd_pk)}
            rd_row = _find_existing_demand_row(
                rd_model,
                database_version_id=vid,
                fk_values=fk_map,
                is_hist=bool(res_row.is_historical_maximum),
                year_n=None if res_row.is_historical_maximum else res_row.year_number,
            )
            if apply_changes:
                if rd_row is None:
                    rd_row = rd_model()
                    rd_row.database_version_id = vid
                    rd_row.id_regional_district = int(rd_pk)
                    rd_row.is_historical_maximum = res_row.is_historical_maximum
                    rd_row.year_number = res_row.year_number
                    db.session.add(rd_row)

                rd_row.max_power_consumption_mw = res_row.max_power_consumption_mw
                rd_row.peak_datetime_msk = res_row.peak_datetime_msk
                rd_row.avg_daily_air_temp_c = res_row.avg_daily_air_temp_c
                rd_row.combined_on_oes = res_row.combined_on_oes
                rd_row.combined_on_ees = res_row.combined_on_ees
                rd_row.combined_on_es = res_row.combined_on_ez
                rd_row.note = res_row.note
                rd_row.modified_by = SCRIPT_USER
                if getattr(rd_row, "id", None) is None:
                    rd_row.created_by = SCRIPT_USER
                stats["mirror_upsert"] += 1
            else:
                stats["mirror_upsert"] += 1

    return dict(stats)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Скопировать параметры нагрузки из одной версии БД во все остальные; "
            "затем выровнять данные субъекта с РЭС при одном субъекте в РЭС."
        )
    )
    parser.add_argument(
        "--source-version",
        type=int,
        default=20,
        help="database_version_id источника (id из gs_sys.gs_database_versions), по умолчанию 20.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только отчёт, без записи (по умолчанию, если нет --apply).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить изменения и commit.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Без запроса подтверждения (для --apply).",
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="Не выполнять копирование РЭС -> субъект (один субъект в РЭС).",
    )
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    if not apply_changes:
        args.dry_run = True

    app = create_app()
    with app.app_context():
        src = int(args.source_version)
        src_row = db.session.get(DatabaseVersion, src)
        if src_row is None:
            raise SystemExit(
                f"В gs_sys.gs_database_versions нет id={src}. Проверьте --source-version."
            )

        other_versions = [
            v
            for v in DatabaseVersion.query.order_by(DatabaseVersion.id.asc()).all()
            if v.id is not None and int(v.id) != src
        ]
        target_ids = [int(v.id) for v in other_versions]

        print("=" * 72)
        print("Копирование параметров нагрузки (power_demand / gs_pd_*)")
        print("=" * 72)
        print(f"Старт:      {datetime.now().isoformat(timespec='seconds')}")
        print(f"Источник:   database_version_id = {src}")
        print(f"Цели:       {target_ids if target_ids else '(нет других версий)'}")
        print(f"Режим:      {'APPLY' if apply_changes else 'DRY-RUN (без commit)'}")
        print(f"Зеркало РЭС->Субъект: {'нет' if args.no_mirror else 'да'}")
        print()

        if not target_ids:
            print("Других версий нет — шаг 1 пропускается.")
        print()

        if apply_changes:
            print(
                "Выравнивание sequences id для таблиц gs_pd_* под MAX(id) "
                "(устраняет duplicate key при INSERT)..."
            )
            _align_gs_pd_id_sequences()
            print()

        if target_ids and apply_changes and not args.yes:
            q = input(
                f"Перезаписать/создать строки gs_pd по данным версии {src} "
                f"в версиях {target_ids}? [y/N]: "
            )
            if str(q).strip().lower() not in ("y", "yes", "д", "да"):
                print("Отмена.")
                return

        ins: dict[str, int] = {}
        upd: dict[str, int] = {}
        skipfk: dict[str, int] = {}

        if target_ids:
            ins, upd, skipfk = copy_from_source_to_other_versions(
                source_vid=src,
                target_vids=target_ids,
                apply_changes=apply_changes,
            )
            print("Шаг 1 — копирование в другие версии (по моделям, ~insert/update):")
            for name in sorted(set(ins) | set(upd)):
                print(f"  {name}: insert={ins.get(name, 0)}, update={upd.get(name, 0)}")
            if skipfk:
                print("  Пропуски (FK/ref_uuid):")
                for name, n in sorted(skipfk.items()):
                    print(f"    {name}: {n}")
            print()

        mir: dict[str, int] = {}
        if not args.no_mirror:
            mir = mirror_res_to_single_regional_district(apply_changes=apply_changes)
            print("Шаг 2 — РЭС с одним субъектом -> RegionalDistrictDemandParameter:")
            for k, v in sorted(mir.items()):
                print(f"  {k}: {v}")
            print()

        if apply_changes:
            try:
                _commit_with_retry()
                print("Commit выполнен.")
            except Exception as e:
                db.session.rollback()
                raise SystemExit(f"Ошибка commit: {e}") from e
        else:
            print("DRY-RUN: изменения не записывались.")

        print(f"Готово: {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
