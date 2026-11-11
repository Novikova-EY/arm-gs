import re
import unicodedata

from sqlalchemy import select

from app.extensions import db
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType


FUEL_CATEGORIES = {"gas": "Газ", "coal": "Уголь", "other": "Прочее"}


def technology_references(version_id):
    return {
        "technology_types": list(db.session.scalars(select(TechnologyType).where(
            TechnologyType.database_version_id == version_id).order_by(TechnologyType.name))),
        "equipment_group_types": list(db.session.scalars(select(EquipmentGroupType).where(
            EquipmentGroupType.database_version_id == version_id).order_by(EquipmentGroupType.name))),
        "fuel_categories": FUEL_CATEGORIES,
    }


def _tokens(name):
    text = unicodedata.normalize("NFKC", name or "").casefold().replace("\u0451", "е")
    text = re.sub(r"\bблоки\b", "блок", text)
    return re.findall(r"[а-яa-z]+|\d+|<=|>=|<|>", text)


def _unique_match(tokens, references):
    matches = []
    for item in references:
        if (item.name or "").strip().casefold() in ("прочее", "прочие", "не указано", "без группы оборудования"):
            continue
        parts = _tokens(item.name)
        if parts and all(part in tokens for part in parts):
            matches.append((len(parts), item))
    if not matches:
        return None
    best = max(score for score, _ in matches)
    winners = [item for score, item in matches if score == best]
    return winners[0] if len(winners) == 1 else None


def match_technology_name(name, references):
    tokens = _tokens(name)
    fuels = {category for token, category in (("газ", "gas"), ("уголь", "coal"),
                                              ("прочее", "other"), ("прочие", "other")) if token in tokens}
    group = _unique_match(tokens, references["equipment_group_types"])
    technology = _unique_match(tokens, references["technology_types"])
    if technology is None:
        inferred_type = None
        if any(token in tokens for token in ("тэц", "кэс", "пгу", "гту", "гпа", "блок")):
            inferred_type = "ТЭС"
        elif "бн" in tokens:
            inferred_type = "АЭС"
        elif "гаэс" in tokens:
            inferred_type = "накопитель (ГАЭС)"
        technology = next((item for item in references["technology_types"] if item.name == inferred_type), None)
    if group is not None:
        technology = next((item for item in references["technology_types"]
                           if item.id == group.id_technology_type), technology)
    if not fuels:
        if any(token in tokens for token in ("пгу", "гту", "гпа")):
            fuels = {"gas"}
        elif any(token in tokens for token in ("аэс", "бн", "гэс", "гаэс", "виэ", "вэс", "сэс")):
            fuels = {"other"}
    return {
        "technology_type_id": technology.id if technology else None,
        "equipment_group_type_id": group.id if group else None,
        "fuel_category": next(iter(fuels)) if len(fuels) == 1 else None,
    }


def set_technology_references(record, data, version_id):
    references = technology_references(version_id)
    selected = {}
    for field, key in (("technology_type_id", "technology_types"),
                       ("equipment_group_type_id", "equipment_group_types")):
        raw = data.get(field, "")
        item = next((item for item in references[key] if str(item.id) == raw), None)
        if raw and item is None:
            raise ValueError("Значение отсутствует в справочнике выбранной версии БД.")
        selected[field] = item
    technology = selected["technology_type_id"]
    group = selected["equipment_group_type_id"]
    if group and group.id_technology_type is not None:
        if technology and technology.id != group.id_technology_type:
            raise ValueError("Тип технологии не соответствует группе оборудования.")
        technology = next((item for item in references["technology_types"]
                           if item.id == group.id_technology_type), None)
        if technology is None:
            raise ValueError("Тип технологии группы отсутствует в выбранной версии БД.")
    fuel = data.get("fuel_category", "")
    if fuel and fuel not in FUEL_CATEGORIES:
        raise ValueError("Неизвестный вид топлива.")
    record.technology_type_id = technology.id if technology else None
    record.equipment_group_type_id = group.id if group else None
    record.fuel_category = fuel or None
