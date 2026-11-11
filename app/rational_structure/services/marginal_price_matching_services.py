from collections import defaultdict

from sqlalchemy import select

from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.generation.models.station.station_model import Station


def _name_key(name):
    # Уточнения в скобках различают группы одной станции.
    return ' '.join((name or '').split()).casefold()


def match_marginal_price_tables(tables, version_id):
    if not tables:
        return {}
    by_name = defaultdict(list)
    for group_id, name in db.session.execute(select(EquipmentGroup.id, EquipmentGroup.name_ext).where(
        EquipmentGroup.database_version_id == version_id,
    )):
        key = _name_key(name)
        if key:
            by_name[key].append(group_id)
    matched_ids = {candidates[0] for table in tables.values() for row in table['rows']
                   if len(candidates := by_name.get(_name_key(row['values'].get('D')), [])) == 1}
    stations = defaultdict(dict)
    if matched_ids:
        statement = (select(EquipmentGroupSet.equipment_group_id, Station.id, Station.name)
                     .select_from(EquipmentGroupSet)
                     .join(EquipmentGroupSetStation,
                           EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id)
                     .join(Station, Station.id == EquipmentGroupSetStation.station_id)
                     .where(EquipmentGroupSet.equipment_group_id.in_(matched_ids),
                            EquipmentGroupSetStation.database_version_id == version_id,
                            Station.database_version_id == version_id)
                     .order_by(Station.name, Station.id))
        for group_id, station_id, name in db.session.execute(statement):
            stations[group_id][station_id] = {'id': station_id, 'name': name}
    result = {}
    for slug, table in tables.items():
        rows = []
        for row in table['rows']:
            candidates = by_name.get(_name_key(row['values'].get('D')), [])
            group_id = candidates[0] if len(candidates) == 1 else None
            rows.append({**row, 'equipment_group_id': group_id,
                         'match_status': 'matched' if group_id else 'ambiguous' if candidates else 'not_found',
                         'stations': list(stations[group_id].values()) if group_id else []})
        result[slug] = {**table, 'rows': rows}
    return result
