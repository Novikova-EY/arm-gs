# -*- coding: utf-8 -*-
"""Что именно рисует РАЗВЁРНУТЫЙ на сервере код (без новых фильтров) для станции 29462."""
import os
import sys

os.environ["DB_HOST"] = "10.31.205.27"
sys.stdout.reconfigure(encoding="utf-8")

from app import create_app

app = create_app()

from sqlalchemy import event
from app.extensions import db

with app.app_context():
    @event.listens_for(db.engine, "connect")
    def _read_only(dbapi_connection, _):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = on;")

    db.session.remove()
    db.engine.dispose()

    from app.fuel.services.stations import stations_equipment_groups_services as svc

    # Отключаем обе новые правки – получаем поведение кода, который сейчас на сервере
    svc.filter_redundant_standalone_equipment_group_ids = (
        lambda identity_rows, filtered_eg_ids, standalone_ids: set(filtered_eg_ids or ())
    )
    svc.drop_legacy_duplicate_group_cell_blocks = lambda blocks, version_id: (blocks, set())

    dup_ids = set()
    hierarchy, total, pages, page = svc.build_equipment_group_hierarchy_eg_first(
        filters={"station_type_filter": [265]},
        start_year=2020,
        end_year=2030,
        energy_system_type_names={},
        union_energy_system_names={},
        regional_energy_system_names={},
        page=1,
        per_page=100000,
        duplicate_numb_ids_out=dup_ids,
    )
    print(f"[старый код] всего групп: {total}, групп с дублем numb: {len(dup_ids)}")

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        for block in node.get("equipment_group_blocks") or node.get("blocks") or []:
            eg = block.get("equipment_group")
            station_ids = [
                getattr((se or {}).get("station"), "id", None)
                for se in (block.get("station_entries") or [])
            ]
            if 29462 not in station_ids and "Улан-Удэнская ТЭЦ-2" != (eg.name or ""):
                continue
            if eg.numb != 671 and 29462 not in station_ids:
                continue
            print(
                f"  eg={eg.id} numb={eg.numb} main={eg.main} comp={eg.comp} "
                f"ver={eg.database_version_id} '{eg.name}' stations={station_ids} "
                f"dup={eg.id in dup_ids} cluster={block.get('show_composite_cluster')}"
            )
        for value in node.values():
            walk(value)

    walk({"root": hierarchy})
