from collections import defaultdict

from sqlalchemy import and_, select

from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.station.station_model import Station
from app.rational_structure.equipment_types import MATCHABLE_TYPES
from app.rational_structure.models import TechnicalInspectionCode, EquipmentTechnicalCharacteristic
from app.rational_structure.services.technical_characteristic_matching import _normalize_text


class TechnicalInspectionCodes:
    def __init__(self):
        machines = db.session.execute(
            select(Machine.id, Machine.database_version_id, Machine.external_code,
                   Machine.machine_number, Machine.machine_name, Station.id.label("station_id"),
                   Station.name.label("station_name"))
            .join(Station, and_(Station.id == Machine.id_station,
                               Station.database_version_id == Machine.database_version_id))
            .where(Machine.database_version_id.is_not(None))
        ).mappings()
        self._machines = {row["id"]: dict(row) for row in machines}
        self._machines_by_code = defaultdict(list)
        for machine in self._machines.values():
            if machine["external_code"]:
                self._machines_by_code[machine["external_code"]].append(machine)
        self._parts = {}
        self._parts_by_parent = defaultdict(list)
        for part in db.session.execute(select(
            PGUMachine.id, PGUMachine.id_parent_machine, PGUMachine.database_version_id,
            PGUMachine.id_ti, PGUMachine.machine_number, PGUMachine.machine_name,
        )).mappings():
            parent = self._machines.get(part["id_parent_machine"])
            if parent and parent["database_version_id"] == part["database_version_id"]:
                self._parts[part["id"]] = dict(part)
                self._parts_by_parent[part["id_parent_machine"]].append(dict(part))
        self._counterpart_cache = {}
        self._skipped = []
        self._conflicts = []
        self._linked_rows = 0
        self._known = defaultdict(set)
        stored = list(db.session.scalars(select(TechnicalInspectionCode)))
        self._stored = {(row.database_version_id, row.equipment_code): row for row in stored}
        legacy = db.session.execute(select(
            EquipmentTechnicalCharacteristic.database_version_id,
            EquipmentTechnicalCharacteristic.equipment_code,
            EquipmentTechnicalCharacteristic.machine_id,
            EquipmentTechnicalCharacteristic.pgu_machine_id,
        ).where(
            EquipmentTechnicalCharacteristic.match_status == "matched",
            EquipmentTechnicalCharacteristic.equipment_type.in_(MATCHABLE_TYPES),
        ))
        projected = defaultdict(set)
        for row in [*stored, *legacy]:
            machine = self._machines.get(row.machine_id)
            part = self._parts.get(row.pgu_machine_id) if row.pgu_machine_id is not None else None
            if not machine or machine["database_version_id"] != row.database_version_id:
                continue
            if row.pgu_machine_id is not None and (not part or part["id_parent_machine"] != row.machine_id):
                continue
            code = row.equipment_code.strip()
            if code:
                self._known[row.database_version_id, code].add((row.machine_id, row.pgu_machine_id))
                for version, target in self._counterparts(row.machine_id, row.pgu_machine_id):
                    projected[version, code].add(target)
        # Явная связь в версии имеет приоритет над переносом из другой версии.
        for key, targets in projected.items():
            if key not in self._known:
                self._known[key].update(targets)
            elif targets - self._known[key]:
                self._conflicts.append({"version_id": key[0], "equipment_code": key[1],
                                        "reason": "Связь в версии отличается от связи по external_code"})

    def _counterparts(self, machine_id: int, pgu_machine_id: int | None) -> list:
        key = (machine_id, pgu_machine_id)
        if key in self._counterpart_cache:
            return self._counterpart_cache[key]
        source = self._machines[machine_id]
        source_part = self._parts[pgu_machine_id] if pgu_machine_id is not None else None
        if not source["external_code"]:
            self._skipped.append({"machine_id": machine_id, "pgu_machine_id": pgu_machine_id,
                                  "reason": "Не заполнен external_code"})
        by_version = defaultdict(list)
        for machine in self._machines_by_code.get(source["external_code"], []):
            by_version[machine["database_version_id"]].append(machine)
        targets = [(source["database_version_id"], key)]
        for version, machines in by_version.items():
            if version == source["database_version_id"]:
                continue
            if len(machines) != 1:
                self._skipped.append({"machine_id": machine_id, "version_id": version,
                                      "reason": "Несколько агрегатов с одним external_code"})
                continue
            target = machines[0]
            if source_part is None:
                targets.append((version, (target["id"], None)))
                continue
            number = _normalize_text(source_part["machine_number"], "station_number")
            parts = []
            for part in self._parts_by_parent[target["id"]]:
                if source_part["id_ti"] is not None and part["id_ti"] is not None:
                    equivalent = source_part["id_ti"] == part["id_ti"]
                else:
                    equivalent = bool(number) and number == _normalize_text(part["machine_number"], "station_number")
                if equivalent:
                    parts.append(part)
            if len(parts) == 1:
                targets.append((version, (target["id"], parts[0]["id"])))
            else:
                self._skipped.append({"machine_id": machine_id, "pgu_machine_id": pgu_machine_id,
                                      "version_id": version,
                                      "reason": "Не найдено однозначное соответствие составляющей ПГУ"})
        self._counterpart_cache[key] = targets
        return targets

    def match(self, equipment_code: str, version_id: int) -> dict | None:
        targets = self._known.get((version_id, equipment_code.strip()), set())
        if not targets:
            return None
        selected = []
        for machine_id, pgu_machine_id in sorted(targets, key=lambda target: (target[0], target[1] or 0)):
            machine = self._machines[machine_id]
            equipment = self._parts[pgu_machine_id] if pgu_machine_id is not None else machine
            selected.append({
                "machine_id": machine_id, "pgu_machine_id": pgu_machine_id,
                "station_id": machine["station_id"], "station_name": machine["station_name"],
                "station_number": equipment["machine_number"], "equipment_brand": equipment["machine_name"],
                "installed_electric_power": "", "score": 100, "differences": [],
            })
        unique = len(targets) == 1
        return {
            "machine_id": selected[0]["machine_id"] if unique else None,
            "pgu_machine_id": selected[0]["pgu_machine_id"] if unique else None,
            "match_status": "matched" if unique else "ambiguous",
            "match_details": {
                "reason": ("Агрегат найден по ранее сохраненному коду Техинспекции." if unique else
                           "Код Техинспекции связан с несколькими агрегатами; требуется выбор."),
                "differing_fields": [], "candidates": selected[:3],
            },
        }

    def remember(self, equipment_code: str, machine_id: int, pgu_machine_id: int | None, username: str,
                 *, replace: bool = False, sync_characteristics: bool = False):
        code = equipment_code.strip()
        created = []
        for version, target in self._counterparts(machine_id, pgu_machine_id):
            key = (version, code)
            # Ручной выбор меняет источник; конфликты в других версиях сохраняем для проверки.
            override = replace and version == self._machines[machine_id]["database_version_id"]
            if self._known[key] - {target} and not override:
                continue
            self._known[key] = {target}
            if key not in self._stored:
                row = TechnicalInspectionCode(
                    database_version_id=version, equipment_code=code,
                    machine_id=target[0], pgu_machine_id=target[1], created_by=username,
                )
                db.session.add(row)
                created.append(row)
                self._stored[key] = row
            elif override:
                row = self._stored[key]
                row.machine_id, row.pgu_machine_id = target
                row.modified_by = username
            if sync_characteristics:
                rows = db.session.scalars(select(EquipmentTechnicalCharacteristic).where(
                    EquipmentTechnicalCharacteristic.database_version_id == version,
                    EquipmentTechnicalCharacteristic.equipment_code == code,
                    EquipmentTechnicalCharacteristic.equipment_type.in_(MATCHABLE_TYPES),
                ))
                for row in rows:
                    if (row.machine_id, row.pgu_machine_id, row.match_status) == (*target, "matched"):
                        continue
                    self._linked_rows += 1
                    row.machine_id, row.pgu_machine_id = target
                    row.match_status = "matched"
                    row.match_details = self.match(code, version)["match_details"]
                    row.modified_by = username
        return created

    def change_code(self, old_code: str | None, new_code: str, machine_id: int,
                    pgu_machine_id: int | None, username: str):
        if old_code and old_code != new_code:
            for version, target in self._counterparts(machine_id, pgu_machine_id):
                key = (version, old_code)
                stored = self._stored.get(key)
                if stored and (stored.machine_id, stored.pgu_machine_id) == target:
                    db.session.delete(stored)
                    del self._stored[key]
                self._known[key].discard(target)
                rows = db.session.scalars(select(EquipmentTechnicalCharacteristic).where(
                    EquipmentTechnicalCharacteristic.database_version_id == version,
                    EquipmentTechnicalCharacteristic.equipment_code == old_code,
                    EquipmentTechnicalCharacteristic.machine_id == target[0],
                    EquipmentTechnicalCharacteristic.pgu_machine_id == target[1],
                    EquipmentTechnicalCharacteristic.equipment_type.in_(MATCHABLE_TYPES),
                ))
                for row in rows:
                    # Код в исходной строке Excel сохраняется, снимается только старая связь.
                    row.machine_id = row.pgu_machine_id = None
                    row.match_status = "not_checked"
                    row.match_details = {}
                    row.modified_by = username
        if new_code:
            self.remember(new_code, machine_id, pgu_machine_id, username,
                          replace=True, sync_characteristics=True)

    def backfill(self, username: str) -> dict:
        report = {"created": 0, "conflicts": list(self._conflicts)}
        processed = set()
        for (version, code), targets in list(self._known.items()):
            if (version, code) in processed:
                continue
            if len(targets) != 1:
                report["conflicts"].append({"version_id": version, "equipment_code": code,
                                            "targets": sorted(targets, key=lambda item: (item[0], item[1] or 0))})
                continue
            machine_id, part_id = next(iter(targets))
            report["created"] += len(self.remember(code, machine_id, part_id, username,
                                                    sync_characteristics=True))
            processed.update((target_version, code) for target_version, target in self._counterparts(machine_id, part_id)
                             if self._known[target_version, code] == {target})
        report["linked_rows"] = self._linked_rows
        report["skipped"] = self._skipped
        return report
