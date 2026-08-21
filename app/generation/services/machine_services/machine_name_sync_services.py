from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_name_model import MachineName
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_tes_type_model import MachineTesType


def _is_blank_name(value: str | None) -> bool:
    return value is None or not str(value).strip()


def _version_rank(version_id: int | None) -> int:
    """Для выбора донора: больше = предпочтительнее; None ниже любых id."""
    return -1 if version_id is None else int(version_id)


def _pick_name_from_year_map(
    year_map: dict[int, tuple[int, str]],
    year: int | None,
    fallback: str | None,
) -> str | None:
    """
    year_map: year -> (version_rank, name).
    """
    if year is not None and year in year_map:
        return year_map[year][1]
    if year is not None and year_map:
        lower = [y for y in year_map if y <= year]
        if lower:
            return year_map[max(lower)][1]
        return year_map[min(year_map)][1]
    if year_map:
        best_year = max(year_map.keys(), key=lambda y: (year_map[y][0], y))
        return year_map[best_year][1]
    fb = (fallback or "").strip()
    return fb or None


def _build_donor_names_by_external_code(
    external_codes: list[str],
) -> dict[str, dict[int, tuple[int, str]]]:
    """code -> year -> (version_rank, name)."""
    if not external_codes:
        return {}

    donor_machines = Machine.query.filter(Machine.external_code.in_(external_codes)).all()
    donors_by_code: dict[str, list[Machine]] = defaultdict(list)
    for donor in donor_machines:
        code = (donor.external_code or "").strip()
        if code:
            donors_by_code[code].append(donor)

    donor_ids = [d.id for d in donor_machines]
    donor_names_by_machine: dict[int, list[MachineName]] = defaultdict(list)
    if donor_ids:
        for row in MachineName.query.filter(MachineName.id_machine.in_(donor_ids)).all():
            if _is_blank_name(row.name):
                continue
            donor_names_by_machine[row.id_machine].append(row)

    best_by_code_year: dict[str, dict[int, tuple[int, str]]] = defaultdict(dict)
    for code, donors in donors_by_code.items():
        for donor in donors:
            rank = _version_rank(getattr(donor, "database_version_id", None))
            for row in donor_names_by_machine.get(donor.id, []):
                year = row.year_number
                if year is None:
                    continue
                name = str(row.name).strip()
                prev = best_by_code_year[code].get(year)
                if prev is None or rank >= prev[0]:
                    best_by_code_year[code][year] = (rank, name)
    return best_by_code_year


def restore_empty_machine_names_by_external_code(
    *,
    machine_ids: Iterable[int] | None = None,
    database_version_id: int | None = None,
    only_empty: bool = True,
    create_missing: bool = True,
) -> dict[str, int]:
    """
    Восстанавливает ``MachineName`` из других копий агрегата по ``external_code``.

    - заполняет пустые ``name`` у существующих строк;
    - при ``create_missing=True`` создаёт недостающие годы по ``MachineTesType`` /
      ``MachinePower`` (и годам донора), подставляя имя с донора.

    Существующие непустые имена не перезаписываются (при only_empty=True).
    """
    stats = {
        "machines": 0,
        "updated": 0,
        "created": 0,
        "skipped_no_donor": 0,
        "skipped_no_code": 0,
    }

    target_q = db.session.query(Machine)
    if database_version_id is not None:
        target_q = target_q.filter(Machine.database_version_id == database_version_id)
    if machine_ids is not None:
        ids = sorted({int(x) for x in machine_ids if x is not None})
        if not ids:
            return stats
        target_q = target_q.filter(Machine.id.in_(ids))

    targets = target_q.all()
    if not targets:
        return stats

    target_ids = [m.id for m in targets]
    names_by_machine: dict[int, dict[int, MachineName]] = defaultdict(dict)
    for row in MachineName.query.filter(MachineName.id_machine.in_(target_ids)).all():
        if row.year_number is None:
            continue
        names_by_machine[row.id_machine][int(row.year_number)] = row

    years_by_machine: dict[int, set[int]] = defaultdict(set)
    if create_missing and target_ids:
        for mid, year in (
            db.session.query(MachineTesType.id_machine, MachineTesType.year_number)
            .filter(
                MachineTesType.id_machine.in_(target_ids),
                MachineTesType.year_number.isnot(None),
            )
            .all()
        ):
            years_by_machine[mid].add(int(year))
        for mid, year in (
            db.session.query(MachinePower.id_machine, MachinePower.year_number)
            .filter(
                MachinePower.id_machine.in_(target_ids),
                MachinePower.year_number.isnot(None),
            )
            .all()
        ):
            years_by_machine[mid].add(int(year))

    machines_to_fix: list[Machine] = []
    for machine in targets:
        rows_map = names_by_machine.get(machine.id, {})
        has_empty = any(_is_blank_name(r.name) for r in rows_map.values())
        missing_years = years_by_machine.get(machine.id, set()) - set(rows_map.keys())
        if rows_map and (not only_empty or has_empty):
            machines_to_fix.append(machine)
        elif create_missing and (missing_years or not rows_map):
            # нет строк или не хватает годов — тоже чиним
            machines_to_fix.append(machine)

    if not machines_to_fix:
        return stats

    # Уникальный список (порядок сохранится)
    seen_ids: set[int] = set()
    unique_machines: list[Machine] = []
    for machine in machines_to_fix:
        if machine.id in seen_ids:
            continue
        seen_ids.add(machine.id)
        unique_machines.append(machine)
    machines_to_fix = unique_machines

    external_codes = sorted(
        {
            (m.external_code or "").strip()
            for m in machines_to_fix
            if (m.external_code or "").strip()
        }
    )
    if not external_codes:
        stats["skipped_no_code"] = len(machines_to_fix)
        return stats

    best_by_code_year = _build_donor_names_by_external_code(external_codes)

    # Если у цели нет годов из powers/tes — берём годы донора
    for machine in machines_to_fix:
        code = (machine.external_code or "").strip()
        if not years_by_machine.get(machine.id) and code in best_by_code_year:
            years_by_machine[machine.id].update(best_by_code_year[code].keys())

    for machine in machines_to_fix:
        stats["machines"] += 1
        code = (machine.external_code or "").strip()
        if not code:
            stats["skipped_no_code"] += 1
            continue

        year_map = best_by_code_year.get(code) or {}
        if not year_map and _is_blank_name(machine.machine_name):
            stats["skipped_no_donor"] += 1
            continue

        rows_map = names_by_machine.setdefault(machine.id, {})

        # 1) заполнить пустые существующие
        for year, row in list(rows_map.items()):
            if only_empty and not _is_blank_name(row.name):
                continue
            picked = _pick_name_from_year_map(year_map, year, machine.machine_name)
            if not picked:
                stats["skipped_no_donor"] += 1
                continue
            if _is_blank_name(row.name) or not only_empty:
                row.name = picked
                stats["updated"] += 1

        # 2) создать недостающие годы
        if create_missing:
            needed_years = set(years_by_machine.get(machine.id, set()))
            needed_years.update(rows_map.keys())
            for year in sorted(needed_years):
                if year in rows_map:
                    continue
                picked = _pick_name_from_year_map(year_map, year, machine.machine_name)
                if not picked:
                    stats["skipped_no_donor"] += 1
                    continue
                obj = MachineName(
                    id_machine=machine.id,
                    year_number=year,
                    name=picked,
                    database_version_id=machine.database_version_id,
                )
                db.session.add(obj)
                rows_map[year] = obj
                stats["created"] += 1

    return stats


def sync_missing_machine_names_from_tes_types(
    machine_ids: Iterable[int] | None = None,
) -> int:
    """
    Создает недостающие записи ``MachineName`` по комбинациям
    ``(id_machine, year_number, database_version_id)`` из ``MachineTesType``.

    Имена существующих записей не перезаписываются: логика совпадает
    с историческим скриптом `fill_machine_names.py`.
    """
    normalized_machine_ids = sorted(
        {
            int(machine_id)
            for machine_id in (machine_ids or [])
            if machine_id is not None
        }
    )
    if machine_ids is not None and not normalized_machine_ids:
        return 0

    existing_db_versions = {
        version_id
        for (version_id,) in db.session.query(DatabaseVersion.id).all()
    }

    machine_tes_type_query = (
        db.session.query(
            MachineTesType.id_machine,
            MachineTesType.year_number,
            MachineTesType.database_version_id,
        )
        .filter(
            MachineTesType.id_machine.isnot(None),
            MachineTesType.year_number.isnot(None),
        )
    )
    if normalized_machine_ids:
        machine_tes_type_query = machine_tes_type_query.filter(
            MachineTesType.id_machine.in_(normalized_machine_ids)
        )

    if existing_db_versions:
        machine_tes_type_query = machine_tes_type_query.filter(
            (MachineTesType.database_version_id.is_(None))
            | (MachineTesType.database_version_id.in_(existing_db_versions))
        )
    else:
        machine_tes_type_query = machine_tes_type_query.filter(
            MachineTesType.database_version_id.is_(None)
        )

    rows = machine_tes_type_query.distinct().all()
    if not rows:
        return 0

    row_machine_ids = sorted({row.id_machine for row in rows if row.id_machine})
    machines_map = {
        machine.id: machine
        for machine in Machine.query.filter(Machine.id.in_(row_machine_ids)).all()
    }

    existing_query = db.session.query(
        MachineName.id_machine,
        MachineName.year_number,
        MachineName.database_version_id,
    )
    if row_machine_ids:
        existing_query = existing_query.filter(MachineName.id_machine.in_(row_machine_ids))

    existing_keys = {
        (machine_id, year_number, database_version_id)
        for machine_id, year_number, database_version_id in existing_query.all()
    }

    created = 0
    for row in rows:
        key = (row.id_machine, row.year_number, row.database_version_id)
        if key in existing_keys:
            continue

        machine = machines_map.get(row.id_machine)
        if machine is None:
            continue

        db.session.add(
            MachineName(
                id_machine=row.id_machine,
                year_number=row.year_number,
                name=machine.machine_name or "",
                database_version_id=row.database_version_id,
            )
        )
        existing_keys.add(key)
        created += 1

    return created
