from copy import deepcopy
from decimal import Decimal

from sqlalchemy import select
from werkzeug.exceptions import NotFound

from app.extensions import db
from app.rational_structure.models import TerritoryInput, TerritoryTechnology, TerritoryTransferSection
from app.rational_structure.services.territory_discount_rate_services import save_territory_discount_rate
from app.rational_structure.services.territory_input_services import (
    TERRITORY_DISCOUNT_RATE_ROW_KEY, TERRITORY_LINKED_ROW_KEYS, build_territory_input_context, parse_territory_value,
    territory_calculated_equipment_row_keys,
)
from app.rational_structure.services.territory_technology_columns import TECHNOLOGY_COLUMNS
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone


def save_territory_cell(kind, data, version_id, username):
    if version_id is None or type(data.get("database_version_id")) is not int or data.get("database_version_id") != version_id:
        raise ValueError("Версия БД изменилась. Обновите страницу.")
    raw = data.get("value")
    if not isinstance(raw, str):
        raise ValueError("Ожидается строковое значение ячейки.")
    field = data.get("field")
    if not isinstance(field, str) or not isinstance(data.get("sheet"), str):
        raise ValueError("Неизвестное поле или вкладка.")
    if kind == "inputs":
        zone_id = data.get("energy_zone_id")
        if type(zone_id) is not int:
            raise ValueError("Выберите энергозону.")
        if zone_id == 0:
            return save_territory_discount_rate(data, version_id, username)
        if data.get("row_key") == TERRITORY_DISCOUNT_RATE_ROW_KEY:
            raise ValueError("Ставка дисконтирования задается только на вкладке «ЕЭС России».")
        record = db.session.scalar(select(TerritoryInput).where(
            TerritoryInput.database_version_id == version_id, TerritoryInput.energy_zone_id == zone_id,
        ).with_for_update())
        context = build_territory_input_context(version_id, zone_id, sheet=data.get("sheet", "years"))
        row = next((row for row in context["rows"] if row["key"] == data.get("row_key")), None)
        if row is None or row["section"]:
            raise ValueError("Ячейка недоступна для редактирования.")
        if field == "value" and row["key"] in TERRITORY_LINKED_ROW_KEYS | territory_calculated_equipment_row_keys():
            raise ValueError("Показатель берется из исходной сводки или рассчитывается автоматически.")
        rows = deepcopy(record.rows if record else [
            {key: row[key] for key in ("number", "label", "unit", "note", "section", "values")}
            for row in context["all_rows"]
        ])
        target = rows[int(row["key"])]
        if field == "note":
            if len(raw) > 2000:
                raise ValueError("Примечание длиннее 2000 символов.")
            value = raw.strip()
            old = target["note"]
            target["note"] = value
        elif field == "value":
            year = data.get("year")
            if type(year) is not int or year not in context["years"]:
                raise ValueError("Год отсутствует в таблице.")
            index = context["years"].index(year)
            value = parse_territory_value(raw)
            old = target["values"][index]
            target["values"][index] = value
        else:
            raise ValueError("Неизвестное поле.")
        if record is None:
            record = TerritoryInput(database_version_id=version_id, energy_zone_id=zone_id,
                                    years=list(context["years"]), source_filename="Исходные данные по территориям.xlsx",
                                    created_by=username)
            db.session.add(record)
        record.rows = rows
    else:
        table = data.get("sheet")
        model = {"technologies": TerritoryTechnology, "transfers": TerritoryTransferSection}.get(table)
        if model is None or type(data.get("row_id")) is not int:
            raise ValueError("Неизвестная таблица или запись.")
        record = db.session.scalar(select(model).where(
            model.database_version_id == version_id, model.id == data["row_id"],
        ).with_for_update())
        if record is None:
            raise NotFound("Запись не найдена в текущей версии БД.")
        value = parse_territory_value(raw)
        number = Decimal(value) if value is not None else None
        matrix = table == "transfers" and field in ("zone_membership", "zone_paths")
        if matrix:
            zone = db.session.scalar(select(EnergyZone).where(
                EnergyZone.database_version_id == version_id, EnergyZone.number == data.get("zone_number")))
            if zone is None or zone.number not in getattr(record, field):
                raise ValueError("Энергозона отсутствует в матрице.")
            if number not in (Decimal(0), Decimal(1)):
                raise ValueError("В матрице допускаются только 0 и 1.")
            values = dict(getattr(record, field))
            old = values[zone.number]
            values[zone.number] = int(number)
            setattr(record, field, values)
        else:
            allowed = {key for key, _ in TECHNOLOGY_COLUMNS} | {"technology_number"} if table == "technologies" else {"forward_limit", "reverse_limit"}
            if field not in allowed:
                raise ValueError("Поле недоступно для редактирования.")
            if field == "technology_number" and (number is None or number != number.to_integral_value() or not 1 <= number <= 2147483647):
                raise ValueError("Номер типа должен быть положительным целым числом.")
            if table == "transfers" and number is None:
                raise ValueError("Предел перетока не может быть пустым.")
            old = getattr(record, field)
            setattr(record, field, int(number) if field == "technology_number" else float(number) if number is not None else None)
    record.modified_by = username
    db.session.commit()
    return {"value": value if value is not None else "", "old_value": old, "record_id": record.id}
