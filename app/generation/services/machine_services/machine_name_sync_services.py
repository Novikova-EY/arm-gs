from __future__ import annotations

from collections.abc import Iterable

from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_name_model import MachineName
from app.generation.models.machine.machine_tes_type_model import MachineTesType


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
