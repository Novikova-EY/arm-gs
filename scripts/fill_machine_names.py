#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт заполнения таблицы machine_names для всех агрегатов.

Для каждого агрегата (Machine) берет комбинации (year_number, database_version_id)
из таблицы machine_tes_types и создает соответствующие записи в machine_names,
где name = Machine.machine_name.

Т.е. если у агрегата в machine_tes_types есть записи для версии id=7 
для годов 2021-2031, то в machine_names создаются записи с 2021 по 2031 год,
где name = machine_name агрегата и database_version_id = 7.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.extensions import db
from app import create_app
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_name_model import MachineName
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.common.models.database_version_model import DatabaseVersion


def fill_machine_names():
    """Заполняет таблицу machine_names по данным из machine_tes_types."""
    # Получаем список существующих версий БД, чтобы не создавать "висячие" ссылки
    existing_db_versions = {
        v.id for v in db.session.query(DatabaseVersion.id).all()
    }

    # Получаем все уникальные (id_machine, year_number, database_version_id) из machine_tes_types
    subq = (
        db.session.query(
            MachineTesType.id_machine,
            MachineTesType.year_number,
            MachineTesType.database_version_id,
        )
        .filter(
            MachineTesType.id_machine.isnot(None),
            MachineTesType.year_number.isnot(None),
        )
        # Отбрасываем ссылки на версии БД, которых уже нет в gs_database_versions
        .filter(
            (MachineTesType.database_version_id.is_(None))
            | (MachineTesType.database_version_id.in_(existing_db_versions))
        )
        .distinct()
    )
    rows = subq.all()

    # Собираем id_machine для загрузки machine_name
    machine_ids = list({r.id_machine for r in rows if r.id_machine})
    machines_map = {m.id: m for m in Machine.query.filter(Machine.id.in_(machine_ids)).all()}

    # Проверяем существующие записи machine_names
    existing = set()
    for mn in db.session.query(
        MachineName.id_machine,
        MachineName.year_number,
        MachineName.database_version_id,
    ).all():
        key = (mn.id_machine, mn.year_number, mn.database_version_id)
        existing.add(key)

    created = 0
    for r in rows:
        if not r.id_machine or r.year_number is None:
            continue
        key = (r.id_machine, r.year_number, r.database_version_id)
        if key in existing:
            continue
        machine = machines_map.get(r.id_machine)
        if not machine:
            continue
        mn = MachineName(
            id_machine=r.id_machine,
            year_number=r.year_number,
            name=machine.machine_name or "",
            database_version_id=r.database_version_id,
        )
        db.session.add(mn)
        created += 1
        existing.add(key)

    db.session.commit()
    return created


def main():
    app = create_app()
    with app.app_context():
        print("Заполнение таблицы machine_names...")
        n = fill_machine_names()
        print(f"Создано записей: {n}")


if __name__ == "__main__":
    main()
