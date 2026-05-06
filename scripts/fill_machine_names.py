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
from app.generation.services.machine_services.machine_name_sync_services import (
    sync_missing_machine_names_from_tes_types,
)


def fill_machine_names():
    """Заполняет таблицу machine_names по данным из machine_tes_types."""
    created = sync_missing_machine_names_from_tes_types()
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
