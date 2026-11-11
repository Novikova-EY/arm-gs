from collections import defaultdict

from sqlalchemy import and_, func, or_, select

from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.fuel.services.equipment_groups.composite_station_semantics import is_main_empty
from app.generation.models.machine.machine_model import Machine
from app.rational_structure.models import TechnicalInspectionCode, TurbineTechnicalCharacteristic


def station_head_group_ids(rows, version_id: int | None) -> dict[str, int]:
    station_names = {row.station_name.strip() for row in rows if row.station_name and row.station_name.strip()}
    if version_id is None or not station_names:
        return {}

    turbine = TurbineTechnicalCharacteristic
    code = TechnicalInspectionCode
    # Сохраненный код из карточки имеет приоритет над результатом импорта.
    bindings = db.session.execute(
        select(func.trim(turbine.station_name), Machine.id)
        .select_from(turbine)
        .outerjoin(code, and_(code.equipment_code == turbine.equipment_code,
                             code.database_version_id == version_id))
        .join(Machine, and_(Machine.id == func.coalesce(code.machine_id, turbine.machine_id),
                            Machine.database_version_id == version_id))
        .where(turbine.database_version_id == version_id,
               turbine.equipment_type.in_(("steam", "gas")),
               func.trim(turbine.station_name).in_(station_names),
               or_(code.id.is_not(None), turbine.match_status == "matched"))
        .distinct()
    ).all()
    if not bindings:
        return {}

    machine_groups = dict(db.session.execute(
        select(MachineFuelParam.machine_id, MachineFuelParam.equipment_group_id)
        .where(MachineFuelParam.machine_id.in_({machine_id for _, machine_id in bindings}),
               MachineFuelParam.database_version_id == version_id)
    ).all())
    if not any(machine_groups.values()):
        return {}

    groups = db.session.execute(
        select(EquipmentGroup.id, EquipmentGroup.numb, EquipmentGroup.main,
               EquipmentGroup.database_version_id)
        .where(or_(EquipmentGroup.database_version_id == version_id,
                   EquipmentGroup.database_version_id.is_(None)))
        .order_by(EquipmentGroup.id)
    ).all()
    by_id = {group.id: group for group in groups}
    by_numb = defaultdict(list)
    for group in groups:
        by_numb[group.numb].append(group)

    heads = defaultdict(set)
    for station_name, machine_id in bindings:
        group = by_id.get(machine_groups.get(machine_id))
        if group is None:
            continue
        if is_main_empty(group.main):
            heads[station_name].add(group.id)
        else:
            parents = by_numb.get(group.main, [])
            current = [parent for parent in parents if parent.database_version_id == version_id]
            parents = current or parents
            if len(parents) == 1 and is_main_empty(parents[0].main):
                heads[station_name].add(parents[0].id)
    return {name: next(iter(ids)) for name, ids in heads.items() if len(ids) == 1}
