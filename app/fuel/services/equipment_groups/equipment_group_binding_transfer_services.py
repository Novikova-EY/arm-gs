"""Preview and atomic transfer of equipment-group bindings between database versions."""
from collections import Counter, defaultdict
import hashlib
import json

from sqlalchemy import insert, select, text, update, func

from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.generation.models.machine.machine_model import Machine
from app.generation.models.station.station_model import Station
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from app.logs.models.log_model import Log


TABLES = {
    "stations": Station.__table__, "machines": Machine.__table__,
    "types": EquipmentGroupType.__table__, "groups": EquipmentGroup.__table__,
    "params": MachineFuelParam.__table__, "station_links": EquipmentGroupSetStation.__table__,
    "sets": EquipmentGroupSet.__table__,
}
GROUP_REF_FIELDS = ("regional_district_id", "regional_energy_system_id", "energy_unit_id")


def _reference_tables():
    return {
        field: next(iter(TABLES["groups"].c[field].foreign_keys)).column.table
        for field in GROUP_REF_FIELDS
    }


def validate_transfer_versions(source, target):
    if any(type(version) is not int or version <= 0 for version in (source, target)):
        raise ValueError("Источник и цель должны быть именованными версиями БД. Перенос из или в NULL запрещен.")
    if source == target:
        raise ValueError("Источник и целевая версия должны различаться.")


def load_transfer_snapshot(source, target, *, lock=False):
    """Read a consistent snapshot; apply locks also prevent inserts between validation and write."""
    validate_transfer_versions(source, target)
    tables = {**TABLES, **_reference_tables()}
    if lock:
        # This admin-only operation is infrequent. Table locks protect absent rows and
        # shared station/type links as well as existing bindings; row locks cannot do that.
        preparer = db.engine.dialect.identifier_preparer
        names = sorted({preparer.format_table(t) for t in tables.values()})
        db.session.execute(text("SET LOCAL lock_timeout = '5s'"))
        db.session.execute(text("LOCK TABLE " + ", ".join(names) + " IN SHARE ROW EXCLUSIVE MODE"))
    snapshot = {}
    for name, table in tables.items():
        if name in ("params", "sets"):
            continue
        query = select(table).where(table.c.database_version_id.in_((source, target)))
        snapshot[name] = [dict(r) for r in db.session.execute(query.order_by(table.c.id)).mappings()]
    machine_ids = [r["id"] for r in snapshot["machines"]]
    group_ids = [r["id"] for r in snapshot["groups"]]
    link_ids = [r["id"] for r in snapshot["station_links"]]
    for name, criterion in (
        ("params", TABLES["params"].c.machine_id.in_(machine_ids)),
        ("sets", TABLES["sets"].c.equipment_group_id.in_(group_ids)
         | TABLES["sets"].c.equipment_group_set_station_id.in_(link_ids)),
    ):
        snapshot[name] = [dict(r) for r in db.session.execute(
            select(TABLES[name]).where(criterion).order_by(TABLES[name].c.id)
        ).mappings()]
    return snapshot


def snapshot_fingerprint(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()


def _index(rows, key):
    result = defaultdict(list)
    for row in rows:
        value = row.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value is not None and value != "":
            result[value].append(row)
    return result


def _one(rows, message):
    if len(rows) != 1:
        raise ValueError(message)
    return rows[0]


def _group_label(row):
    if row is None:
        return "Без явной привязки"
    return f"{row['numb'] if row['numb'] is not None else 'без кода'} – {row['name'] or row['name_ext'] or 'Группа #' + str(row['id'])}"


class TransferPlan:
    def __init__(self, snapshot, source, target, create_missing=False, group_id=None):
        validate_transfer_versions(source, target)
        self.snapshot, self.source, self.target = snapshot, source, target
        self.create_missing = create_missing
        self.group_id = group_id
        self.rows = []
        self.creations = {}
        self.resolved_groups = {}
        self.source_rows = {}
        self.target_rows = {}
        self.source_indexes = {}
        self.target_indexes = {}
        for name, rows in snapshot.items():
            self.source_rows[name] = [r for r in rows if r.get("database_version_id") == source]
            self.target_rows[name] = [r for r in rows if r.get("database_version_id") == target]
            key = "external_code" if name in ("stations", "machines", "groups") else "ref_uuid"
            self.source_indexes[name] = _index(self.source_rows[name], key)
            self.target_indexes[name] = _index(self.target_rows[name], key)
        self.by_id = {name: {r["id"]: r for r in rows} for name, rows in snapshot.items()}
        self.params = _index(snapshot["params"], "machine_id")
        self.source_numbs = _index(self.source_rows["groups"], "numb")
        self.target_numbs = _index(self.target_rows["groups"], "numb")
        self.link_sets = _index(snapshot["sets"], "equipment_group_set_station_id")
        self.station_links = defaultdict(list)
        for link in snapshot["station_links"]:
            self.station_links[(link["database_version_id"], link["station_id"], link["equipment_group_type_id"])].append(link)

    def counterpart(self, name, row_id):
        row = self.by_id[name].get(row_id)
        if row is None or row["database_version_id"] != self.source:
            raise ValueError("Исходная запись отсутствует или относится к другой версии.")
        field = "external_code" if name in ("stations", "machines", "groups") else "ref_uuid"
        code = (row.get(field) or "").strip()
        if not code or len(self.source_indexes[name].get(code, [])) != 1:
            raise ValueError("Пустой или неоднозначный идентификатор в исходной версии.")
        label = {"stations": "станция", "machines": "агрегат", "types": "тип группы",
                 "groups": "группа", "regional_district_id": "субъект РФ",
                 "regional_energy_system_id": "региональная энергосистема", "energy_unit_id": "энергоузел"}[name]
        return _one(self.target_indexes[name].get(code, []),
                    f"В текущей версии нет однозначного соответствия: {label}.")

    def group(self, group_id, visiting=()):
        if group_id in self.resolved_groups:
            return self.resolved_groups[group_id]
        if group_id in visiting:
            raise ValueError("Циклическая структура составной станции.")
        source = self.by_id["groups"].get(group_id)
        if source is None or source["database_version_id"] != self.source:
            raise ValueError("Группа источника относится к другой версии.")
        code = (source["external_code"] or "").strip()
        if not code or len(self.source_indexes["groups"].get(code, [])) != 1:
            raise ValueError("Неоднозначный внешний код исходной группы.")
        matches = self.target_indexes["groups"].get(code, [])
        if len(matches) > 1:
            raise ValueError("Несколько целевых групп с одним внешним кодом.")
        if matches:
            self.resolved_groups[group_id] = matches[0]
            return matches[0]
        parent = None
        if source["main"] not in (None, 0):
            parent_source = _one(self.source_numbs.get(source["main"], []),
                                 "Не найден однозначный родитель составной станции.")
            if parent_source["comp"] != 1:
                raise ValueError("Исходный родитель не является составной станцией.")
            parent = self.group(parent_source["id"], (*visiting, group_id))
            if parent["comp"] != 1:
                raise ValueError("Целевой родитель не является составной станцией. Создание дочерней группы запрещено.")
            if len(self.target_numbs.get(parent["numb"], [])) > 1:
                raise ValueError("Код родителя неоднозначен в текущей версии.")
            if parent["numb"] is None:
                raise ValueError("У целевого родителя отсутствует код группы.")
        if not self.create_missing:
            raise ValueError("Группа отсутствует в текущей версии. Можно разрешить создание отсутствующих групп.")
        if source["numb"] is not None and (
            len(self.source_numbs[source["numb"]]) != 1 or self.target_numbs.get(source["numb"])
        ):
            raise ValueError("Код группы занят или неоднозначен. Автоматическое создание запрещено.")
        values = {k: v for k, v in source.items() if k not in ("id", "created_at", "updated_at")}
        values["database_version_id"] = self.target
        values["main"] = parent["numb"] if parent else source["main"]
        for field in GROUP_REF_FIELDS:
            if source[field] is not None:
                values[field] = self.counterpart(field, source[field])["id"]
        target = {**values, "id": None}
        self.creations[group_id] = values
        self.resolved_groups[group_id] = target
        return target

    def station_link(self, station_id, type_id):
        matches = self.station_links.get((self.target, station_id, type_id), [])
        if len(matches) > 1:
            raise ValueError("Дублируется целевая связь станции и типа группы.")
        return matches[0] if matches else None

    def link(self, group_id, station_id, type_id):
        target = self.group(group_id)
        existing = self.station_link(station_id, type_id)
        return bool(existing and any(r["equipment_group_id"] == target["id"]
                                    for r in self.link_sets.get(existing["id"], [])))

    def _station_group_ids(self, station_id, type_id, version):
        if station_id is None:
            return set()
        return {relation["equipment_group_id"]
                for link in self.station_links.get((version, station_id, type_id), [])
                for relation in self.link_sets.get(link["id"], [])}

    def _comparison_details(self, station_id, type_id, group_ids, version):
        groups = self.by_id["groups"]
        group_codes = "\n".join(
            f"{groups[gid]['external_code'] or 'не указан'} (ID {gid})" if gid in groups
            else f"Группа не найдена (ID {gid})" for gid in sorted(group_ids)
        ) or "Без привязки"
        group_type = self.by_id["types"].get(type_id)
        type_uuid = (f"{group_type['ref_uuid'] or 'не указан'} (ID {type_id})" if group_type
                     else f"Тип не найден (ID {type_id})" if type_id is not None else "Тип не указан")
        station = self.by_id["stations"].get(station_id)
        if station is None:
            station_link = f"Станция не найдена (ID {station_id})" if station_id is not None else "Без станции"
        else:
            lines = [f"{station['name']} (external_code: {station['external_code'] or 'не указан'}; ID {station_id})"]
            links = self.station_links.get((version, station_id, type_id), [])
            for gid in sorted(group_ids):
                linked_ids = [link["id"] for link in links if any(
                    relation["equipment_group_id"] == gid for relation in self.link_sets.get(link["id"], []))]
                state = ", ".join(str(pk) for pk in linked_ids)
                lines.append(f"Группа ID {gid} → станция/тип: " + (f"есть (ID связи {state})" if state else "нет связи"))
            if not group_ids:
                lines.append("Нет группы для проверки связи со станцией и типом")
            station_link = "\n".join(lines)
        return group_codes, type_uuid, station_link

    def _add_comparison_details(self, row):
        if row["kind"] in ("machine", "type"):
            source_machine = self.by_id["machines"][row["source_machine_id"]]
            source_station_id, source_type_id = source_machine["id_station"], source_machine["id_equipment_group"]
            matches = self.target_indexes["machines"].get((source_machine["external_code"] or "").strip(), [])
            target_machine = matches[0] if len(matches) == 1 else None
            target_station_id = target_machine["id_station"] if target_machine else None
            target_type_id = target_machine["id_equipment_group"] if target_machine else None
            target_group_ids = {p["equipment_group_id"] for p in self.params.get(target_machine["id"], [])
                                if p["equipment_group_id"] is not None} if target_machine else set()
        else:
            source_link = self.by_id["station_links"][row["source_link_id"]]
            source_station_id, source_type_id = source_link["station_id"], source_link["equipment_group_type_id"]
            source_station = self.by_id["stations"].get(source_station_id)
            source_type = self.by_id["types"].get(source_type_id)
            stations = self.target_indexes["stations"].get((source_station["external_code"] or "").strip(), []) if source_station else []
            types = self.target_indexes["types"].get((source_type["ref_uuid"] or "").strip(), []) if source_type else []
            target_station_id = stations[0]["id"] if len(stations) == 1 else None
            target_type_id = types[0]["id"] if len(types) == 1 else None
            target_group_ids = set()
        if not target_group_ids:
            target_group_ids = self._station_group_ids(target_station_id, target_type_id, self.target)
        source_group_ids = ({row["source_group_id"]} if row["source_group_id"] is not None
                            else self._station_group_ids(source_station_id, source_type_id, self.source))
        for prefix, station_id, type_id, group_ids, version in (
            ("source", source_station_id, source_type_id, source_group_ids, self.source),
            ("current", target_station_id, target_type_id, target_group_ids, self.target),
        ):
            codes, type_uuid, station_link = self._comparison_details(station_id, type_id, group_ids, version)
            row.update({f"{prefix}_group_external_code": codes, f"{prefix}_type_ref_uuid": type_uuid,
                        f"{prefix}_station_link": station_link})
        if row["kind"] in ("link", "station_link"):
            row["current_group"] = "\n".join(_group_label(self.by_id["groups"].get(gid)) for gid in sorted(target_group_ids)) or "Без привязки"

    def build(self):
        if self.group_id is not None:
            group = self.by_id["groups"].get(self.group_id)
            if group is None or group["database_version_id"] != self.source:
                raise ValueError("Выбранная группа отсутствует в исходной версии.")
        for param in self.snapshot["params"]:
            machine = self.by_id["machines"].get(param["machine_id"])
            if machine is None or machine["database_version_id"] != self.source or param["equipment_group_id"] is None:
                continue
            if self.group_id is not None and param["equipment_group_id"] != self.group_id:
                continue
            group = self.by_id["groups"].get(param["equipment_group_id"])
            station = self.by_id["stations"].get(machine["id_station"])
            row = dict(key=f"machine:{machine['id']}", kind="machine", source_machine_id=machine["id"],
                       source_group_id=param["equipment_group_id"], station=station["name"] if station else "Без станции",
                       equipment=f"{machine['machine_number']} {machine['machine_name']}".strip(),
                       source_group=_group_label(group), current_group="–", status="blocked", reason="")
            try:
                if param["database_version_id"] != self.source or len(self.params[machine["id"]]) != 1:
                    raise ValueError("Некорректная версия или дубликат топливной записи источника.")
                target_machine = self.counterpart("machines", machine["id"])
                target_station = self.counterpart("stations", machine["id_station"])
                if target_machine["id_station"] != target_station["id"]:
                    raise ValueError("Агрегат в текущей версии относится к другой станции.")
                target_type = self.counterpart("types", machine["id_equipment_group"])["id"] if machine["id_equipment_group"] else None
                target_group = self.group(param["equipment_group_id"])
                linked = self.link(param["equipment_group_id"], target_station["id"], target_type)
                target_params = self.params.get(target_machine["id"], [])
                if len(target_params) > 1 or any(p["database_version_id"] != self.target for p in target_params):
                    raise ValueError("Некорректная версия или дубликат топливной записи цели.")
                previous = target_params[0] if target_params else None
                previous_group_id = previous["equipment_group_id"] if previous else None
                previous_group = self.by_id["groups"].get(previous_group_id)
                row["current_group"] = (_group_label(previous_group) if previous_group_id is None or previous_group
                                        else f"Группа #{previous_group_id} вне выбранных версий")
                implicit_ids = set()
                if previous_group_id is None and target_machine["id_equipment_group"] is not None:
                    implicit_ids = self._station_group_ids(target_station["id"], target_machine["id_equipment_group"], self.target)
                    if implicit_ids:
                        row["current_group"] = "Вычисляется: " + "; ".join(
                            _group_label(self.by_id["groups"][gid]) if gid in self.by_id["groups"]
                            else f"Группа #{gid} вне выбранных версий" for gid in sorted(implicit_ids))
                source_type = self.by_id["types"].get(machine["id_equipment_group"])
                current_type = self.by_id["types"].get(target_machine["id_equipment_group"])
                row["current_group"] += "\nТип: " + (current_type["name"] if current_type else "не указан")
                row["source_group"] += "\nТип: " + (source_type["name"] if source_type else "не указан")
                row["target_group"] = _group_label(target_group)
                conflict = (previous_group_id is not None and previous_group_id != target_group["id"]) or bool(
                    implicit_ids - {target_group["id"]})
                binding_same = previous is not None and previous_group_id == target_group["id"]
                same = binding_same and linked
                reason = "Уже совпадает" if same else "Замена явной или вычисляемой группы" if conflict else "Можно перенести"
                if binding_same and not linked:
                    reason = "Явная группа совпадает; добавить недостающую связь группы со станцией и типом"
                row.update(status="same" if same else "conflict" if conflict else "ready", reason=reason,
                           target_machine_id=target_machine["id"], station_id=target_station["id"], type_id=target_type)
                if previous and previous["numb1120"] != target_group["numb"]:
                    row["reason"] += f". Служебный код в текущей версии: {previous['numb1120']}; код группы: {target_group['numb']}"
                    row["reason"] += "; не изменяется" if same else "; при переносе будет использован код целевой группы"
                if param["numb1120"] != (group["numb"] if group else None):
                    row["reason"] += f". Служебный код в источнике: {param['numb1120']}; код группы: {group['numb'] if group else None}"
                    row["reason"] += "; совпадающая привязка не изменяется" if same else "; при переносе будет использован код целевой группы"
            except ValueError as exc:
                row["reason"] = str(exc)
            self.rows.append(row)
        for machine in self.source_rows["machines"]:
            if self.group_id is not None:
                explicit = {p["equipment_group_id"] for p in self.params.get(machine["id"], [])
                            if p["equipment_group_id"] is not None}
                groups = explicit or self._station_group_ids(machine["id_station"], machine["id_equipment_group"], self.source)
                if self.group_id not in groups:
                    continue
            if machine["id_equipment_group"] is None:
                continue
            station = self.by_id["stations"].get(machine["id_station"])
            source_type = self.by_id["types"].get(machine["id_equipment_group"])
            row = dict(
                key=f"type:{machine['id']}", kind="type", source_machine_id=machine["id"], source_group_id=None,
                station=station["name"] if station else "Без станции",
                equipment="Тип агрегата: " + f"{machine['machine_number']} {machine['machine_name']}".strip(),
                source_group="Тип: " + (source_type["name"] if source_type else "не найден"), current_group="–",
                status="blocked", reason="",
            )
            try:
                target_machine = self.counterpart("machines", machine["id"])
                target_type = self.counterpart("types", machine["id_equipment_group"])
                current_type = self.by_id["types"].get(target_machine["id_equipment_group"])
                row["current_group"] = "Тип: " + (current_type["name"] if current_type else "не указан")
                same = target_machine["id_equipment_group"] == target_type["id"]
                if same:
                    reason = "Уже совпадает"
                elif target_machine["id_equipment_group"] is None:
                    reason = "Назначить тип агрегата"
                else:
                    reason = "Заменить тип агрегата типом из источника"
                row.update(status="same" if same else "ready", reason=reason,
                           target_machine_id=target_machine["id"], type_id=target_type["id"])
            except ValueError as exc:
                row["reason"] = str(exc)
            self.rows.append(row)
        for link in self.source_rows["station_links"]:
            if self.group_id is not None and not any(
                r["equipment_group_id"] == self.group_id for r in self.link_sets.get(link["id"], [])
            ):
                continue
            station = self.by_id["stations"].get(link["station_id"])
            link_type = self.by_id["types"].get(link["equipment_group_type_id"])
            row = dict(
                key=f"station_link:{link['id']}", kind="station_link", source_link_id=link["id"], source_group_id=None,
                station=station["name"] if station else "Без станции", equipment="Связь станции с типом",
                source_group="Тип: " + (link_type["name"] if link_type else "не указан"), current_group="–",
                status="blocked", reason="",
            )
            try:
                if link["station_id"] is None:
                    raise ValueError("Связь без станции не переносится автоматически.")
                source_links = self.station_links[(self.source, link["station_id"], link["equipment_group_type_id"])]
                if len(source_links) != 1:
                    raise ValueError("Дублируется исходная связь станции и типа группы.")
                target_station = self.counterpart("stations", link["station_id"])
                target_type = self.counterpart("types", link["equipment_group_type_id"])["id"] if link["equipment_group_type_id"] is not None else None
                existing = self.station_link(target_station["id"], target_type)
                row.update(status="same" if existing else "ready",
                           reason="Уже совпадает" if existing else "Добавить связь станции с типом",
                           station_id=target_station["id"], type_id=target_type)
            except ValueError as exc:
                row["reason"] = str(exc)
            self.rows.append(row)
            station_row = row
            for relation in self.link_sets.get(link["id"], []):
                if self.group_id is not None and relation["equipment_group_id"] != self.group_id:
                    continue
                group = self.by_id["groups"].get(relation["equipment_group_id"])
                row = dict(key=f"link:{relation['id']}", kind="link", source_link_id=link["id"], source_group_id=relation["equipment_group_id"],
                           station=station["name"] if station else "Без станции", equipment="Связь группы со станцией и типом",
                           source_group=_group_label(group) + "\nТип: " + (link_type["name"] if link_type else "не указан"),
                           current_group="–", status="blocked", reason="")
                try:
                    if station_row["status"] == "blocked":
                        raise ValueError(station_row["reason"])
                    target_station_id, target_type = station_row["station_id"], station_row["type_id"]
                    exists = self.link(relation["equipment_group_id"], target_station_id, target_type)
                    row.update(status="same" if exists else "ready", reason="Уже совпадает" if exists else "Добавить связь со станцией",
                               station_id=target_station_id, type_id=target_type)
                except ValueError as exc:
                    row["reason"] = str(exc)
                self.rows.append(row)
        for row in self.rows:
            self._add_comparison_details(row)
            if (row["status"] in ("ready", "conflict") and row["source_group_id"] is not None
                    and self.resolved_groups[row["source_group_id"]]["id"] is None):
                row["reason"] += ". Будет создана отсутствующая группа"
        return self

    def public(self):
        return {"rows": self.rows, "counts": dict(Counter(r["status"] for r in self.rows)),
                "new_groups": len(self.creations), "fingerprint": snapshot_fingerprint(self.snapshot)}


def apply_transfer_plan(plan, keys, username):
    validate_transfer_versions(plan.source, plan.target)
    by_key = {row["key"]: row for row in plan.rows}
    if not keys or len(keys) != len(set(keys)) or any(k not in by_key for k in keys):
        raise ValueError("Выберите строки из актуального предварительного плана.")
    selected = [by_key[k] for k in keys]
    if any(r["status"] not in ("ready", "conflict") for r in selected):
        raise ValueError("В выборке есть строки, которые нельзя перенести.")
    created_groups, created_links, audit, type_changes = {}, [], [], []

    def ensure_group(source_id):
        target = plan.resolved_groups[source_id]
        if target["id"] is not None:
            return target["id"]
        if source_id not in created_groups:
            source = plan.by_id["groups"][source_id]
            if source["main"] not in (None, 0):
                ensure_group(plan.source_numbs[source["main"]][0]["id"])
            result = db.session.execute(insert(TABLES["groups"]).values(**plan.creations[source_id]).returning(TABLES["groups"].c.id))
            created_groups[source_id] = result.scalar_one()
        return created_groups[source_id]

    links = {(r["station_id"], r["equipment_group_type_id"]): r["id"] for r in plan.target_rows["station_links"]}
    relations = {(r["equipment_group_id"], r["equipment_group_set_station_id"]) for r in plan.snapshot["sets"]}
    for row in selected:
        if row["kind"] == "type":
            machine_id = row["target_machine_id"]
            machine = plan.by_id["machines"][machine_id]
            changes = dict(id_equipment_group=row["type_id"], updated_at=func.now(),
                           version=TABLES["machines"].c.version + 1)
            result = db.session.execute(update(TABLES["machines"]).where(
                TABLES["machines"].c.id == machine_id,
                TABLES["machines"].c.database_version_id == plan.target,
            ).values(**changes))
            if result.rowcount != 1:
                raise ValueError("Агрегат отсутствует в целевой версии. Повторите анализ.")
            type_changes.append({"machine_id": machine_id, "before_type_id": machine["id_equipment_group"],
                                 "after_type_id": row["type_id"]})
            continue
        pair = (row["station_id"], row["type_id"])
        if pair not in links:
            links[pair] = db.session.execute(insert(TABLES["station_links"]).values(
                station_id=pair[0], equipment_group_type_id=pair[1], database_version_id=plan.target
            ).returning(TABLES["station_links"].c.id)).scalar_one()
            created_links.append({"station_link_id": links[pair]})
        if row["kind"] == "station_link":
            continue
        group_id = ensure_group(row["source_group_id"])
        relation = (group_id, links[pair])
        if relation not in relations:
            set_id = db.session.execute(insert(TABLES["sets"]).values(
                equipment_group_id=group_id, equipment_group_set_station_id=links[pair]
            ).returning(TABLES["sets"].c.id)).scalar_one()
            relations.add(relation)
            created_links.append({"set_id": set_id})
        if row["kind"] == "machine":
            machine_id = row["target_machine_id"]
            previous = plan.params.get(machine_id, [])
            values = dict(equipment_group_id=group_id, numb1120=plan.resolved_groups[row["source_group_id"]]["numb"])
            if previous:
                result = db.session.execute(update(TABLES["params"]).where(
                    TABLES["params"].c.id == previous[0]["id"],
                    TABLES["params"].c.machine_id == machine_id,
                    TABLES["params"].c.database_version_id == plan.target,
                ).values(**values, updated_at=func.now()))
                if result.rowcount != 1:
                    raise ValueError("Топливная запись отсутствует в целевой версии. Повторите анализ.")
            else:
                db.session.execute(insert(TABLES["params"]).values(**values, machine_id=machine_id, database_version_id=plan.target))
            audit.append({"machine_id": machine_id, "before_param": previous[0] if previous else None, **values})
    for row in selected:
        if row["kind"] == "type":
            machine_type = db.session.execute(select(TABLES["machines"].c.id_equipment_group).where(
                TABLES["machines"].c.id == row["target_machine_id"],
                TABLES["machines"].c.database_version_id == plan.target,
            )).scalar_one()
            if machine_type != row["type_id"]:
                raise ValueError("Проверка типов агрегатов не пройдена. Перенос отменен.")
            continue
        link_id = links[(row["station_id"], row["type_id"])]
        if row["kind"] == "station_link":
            stored = db.session.execute(select(TABLES["station_links"]).where(
                TABLES["station_links"].c.id == link_id
            )).mappings().one()
            if (stored["station_id"], stored["equipment_group_type_id"], stored["database_version_id"]) != (
                row["station_id"], row["type_id"], plan.target
            ):
                raise ValueError("Проверка связей станций с типами не пройдена. Перенос отменен.")
            continue
        group_id = ensure_group(row["source_group_id"])
        stored_link = db.session.execute(select(TABLES["sets"].c.id).where(
            TABLES["sets"].c.equipment_group_id == group_id,
            TABLES["sets"].c.equipment_group_set_station_id == link_id,
        )).scalar_one_or_none()
        if stored_link is None:
            raise ValueError("Проверка созданных связей не пройдена. Перенос отменен.")
        if row["kind"] == "machine":
            stored = db.session.execute(select(TABLES["params"]).where(
                TABLES["params"].c.machine_id == row["target_machine_id"]
            )).mappings().one()
            if (stored["equipment_group_id"] != group_id or stored["database_version_id"] != plan.target
                    or stored["numb1120"] != plan.resolved_groups[row["source_group_id"]]["numb"]):
                raise ValueError("Проверка привязок агрегатов не пройдена. Перенос отменен.")
    db.session.execute(insert(Log.__table__).values(
        username=username[:100], module="Топливо", action="Перенос связей из другой версии базы данных",
        entity_type="database_version", entity_id=plan.target, database_version_id=plan.target,
        details=json.dumps({"source_version_id": plan.source, "target_version_id": plan.target,
                            "selected_keys": keys, "bindings": audit, "type_changes": type_changes,
                            "created_groups": created_groups,
                            "created_links": created_links}, ensure_ascii=False, default=str),
    ))
    # No retry of commit: retrying a rolled-back transaction would report success without its writes.
    db.session.commit()
    return {"machines": len({r["machine_id"] for r in audit + type_changes}), "groups": len(created_groups),
            "links": len([r for r in created_links if "set_id" in r]),
            "station_links": len([r for r in created_links if "station_link_id" in r])}
