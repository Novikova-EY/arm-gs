#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Унификация external_code для EquipmentGroup: у всех групп с одинаковым numb
(для разных версий БД) должен быть одинаковый external_code.

Ключ для генерации: только numb (и name, name_ext, main для уникальности),
без regional_district_id и regional_energy_system_id, т.к. они зависят от версии.

Запуск: python scripts/unify_equipment_group_external_code_by_numb.py [--dry-run] [--yes]
"""

import argparse
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from config import SCHEMA_FUEL


def _stable_key(numb, name, name_ext, main) -> str:
    """
    Стабильный ключ для external_code: только поля из исходных данных,
    не зависящие от database_version (regional_district_id, regional_energy_system_id).
    """
    return (
        f"equipment_group|numb|{numb or ''}|name|{name or ''}"
        f"|name_ext|{name_ext or ''}|main|{main or ''}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Унификация external_code: одинаковый numb → одинаковый external_code для всех версий."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать, что будет сделано, без изменений",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Без подтверждения",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        eg_table = EquipmentGroup.__table__

        # Выбираем все EquipmentGroup
        stmt = select(
            eg_table.c.id,
            eg_table.c.numb,
            eg_table.c.name,
            eg_table.c.name_ext,
            eg_table.c.main,
            eg_table.c.external_code,
            eg_table.c.database_version_id,
        )
        rows = db.session.execute(stmt).all()

        # Группируем по стабильному ключу (numb, name, name_ext, main)
        key_to_rows: dict[str, list] = defaultdict(list)
        for row in rows:
            key = _stable_key(row.numb, row.name, row.name_ext, row.main)
            key_to_rows[key].append(row)

        # Для каждой группы вычисляем целевой external_code и собираем id для обновления
        id_to_code: dict[int, str] = {}
        for key, group_rows in key_to_rows.items():
            target_code = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
            for row in group_rows:
                if row.external_code != target_code:
                    id_to_code[row.id] = target_code

        if not id_to_code:
            print("Все EquipmentGroup уже имеют согласованный external_code по numb.")
            return

        print("=" * 80)
        print("Унификация external_code для EquipmentGroup по numb")
        print("=" * 80)
        print(f"Старт: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Записей к обновлению: {len(id_to_code)}")
        if args.dry_run:
            print("[DRY-RUN] Изменения не применяются")
        print()

        # Показываем примеры
        shown = 0
        for eg_id, new_code in list(id_to_code.items())[:10]:
            old_row = next(r for r in rows if r.id == eg_id)
            print(f"  id={eg_id} numb={old_row.numb} db_ver={old_row.database_version_id}")
            print(f"    old: {old_row.external_code}")
            print(f"    new: {new_code}")
            shown += 1
        if len(id_to_code) > 10:
            print(f"  ... и ещё {len(id_to_code) - 10} записей")

        if args.dry_run:
            print()
            print(f"[DRY-RUN] Будет обновлено записей: {len(id_to_code)}")
            return

        if not args.yes:
            confirm = input("\nПрименить изменения? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes"):
                print("Отменено.")
                return

        for eg_id, new_code in id_to_code.items():
            db.session.execute(
                update(eg_table).where(eg_table.c.id == eg_id).values(external_code=new_code)
            )

        db.session.commit()
        print()
        print(f"Обновлено записей: {len(id_to_code)}")
        print(f"Готово: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
