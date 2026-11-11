from sqlalchemy import select

from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db
from app.rational_structure.models import TerritoryDiscountRate
from app.rational_structure.services.territory_input_services import (
    TERRITORY_DISCOUNT_RATE_ROW_KEY, build_territory_input_context, parse_territory_value,
)
from app.refdata.models.years.year_model import Year


def populate_territory_discount_rate(context):
    if context["sheet"] != "years" or context["version_id"] is None or not context["rows"]:
        return
    record = db.session.get(TerritoryDiscountRate, context["version_id"])
    values = record.year_values if record else {}
    for row in context["rows"]:
        if row["key"] == TERRITORY_DISCOUNT_RATE_ROW_KEY:
            row.update(cells=[values.get(str(year), "") for year in context["years"]],
                       readonly=not context.get("is_ees", False), note_readonly=True,
                       shared_input=context.get("is_ees", False), note="",
                       formula="Общая ставка дисконтирования задается на вкладке «ЕЭС России». "
                               "Введенное значение применяется с выбранного года до конца строки.")


def save_territory_discount_rate(data, version_id, username):
    if (data.get("sheet") != "years" or data.get("row_key") != TERRITORY_DISCOUNT_RATE_ROW_KEY
            or data.get("field") != "value"):
        raise ValueError("На вкладке ЕЭС России можно изменять только ставку дисконтирования.")
    context = build_territory_input_context(version_id, 0)
    years = sorted(set(context["years"]) | set(db.session.scalars(select(Year.number).where(
        Year.database_version_id == version_id))))
    year = data.get("year")
    if type(year) is not int or year not in years:
        raise ValueError("Год отсутствует в таблице.")
    value = parse_territory_value(data["value"])
    # Блокируем версию, в том числе при первом сохранении, когда строки ставки еще нет.
    db.session.execute(select(DatabaseVersion.id).where(DatabaseVersion.id == version_id).with_for_update())
    record = db.session.get(TerritoryDiscountRate, version_id, populate_existing=True)
    if record is None:
        record = TerritoryDiscountRate(database_version_id=version_id, year_values={}, created_by=username)
        db.session.add(record)
    values = dict(record.year_values)
    old = values.get(str(year), "")
    prolonged = {str(number): value if value is not None else "" for number in years if number >= year}
    values.update(prolonged)
    record.year_values = values
    record.modified_by = username
    db.session.commit()
    return dict(value=value if value is not None else "", old_value=old,
                record_id=version_id, year_values=prolonged)
