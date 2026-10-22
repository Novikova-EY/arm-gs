"""Передача по годам: отправка не изменяет принятые данные экологии."""
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import func

from app.common.services.database_version_filter import get_current_db_version_id
from app.ecology.models.fuel_exchange_model import EcologyFuelSnapshot, EcologyFuelSubmission
from app.ecology.models.operating_tes_input_model import OperatingTesInputValue
from app.ecology.services.operating_tes_constants import TOP_INPUT_ROWS
from app.ecology.services.fuel_summary_constants import FUEL_SUMMARY_LABELS, NEW_TES_SCOPE_CAPACITY
from app.ecology.services.operating_tes_fuel_input_services import (
    bucket_field_amount, bucket_top_input_amount, get_fuel_module_consumption_row_specs,
)
from app.ecology.services.operating_tes_territory_services import get_territory_columns
from app.extensions import db


def encode_inputs(inputs):
    return {slug: {field: str(value) for field, value in bucket.items()} for slug, bucket in inputs.items()}


def decode_inputs(payload):
    return {slug: {field: Decimal(value) for field, value in bucket.items()} for slug, bucket in payload.items()}


def _version_id():
    version_id = get_current_db_version_id()
    if version_id is None:
        raise ValueError("Не выбрана версия базы данных")
    return version_id


def load_accepted_fuel_inputs(years, scope="operating"):
    rows = EcologyFuelSnapshot.query.filter_by(database_version_id=_version_id(), scope=scope).filter(
        EcologyFuelSnapshot.year_number.in_(years)
    ).all()
    result = {year: {} for year in years}
    for row in rows:
        result[row.year_number] = decode_inputs(row.payload)
    return result


def load_accepted_new_tes_fuel_inputs(years):
    result = {year: {} for year in years}
    for scope, capacity_class in NEW_TES_SCOPE_CAPACITY.items():
        for year, territories in load_accepted_fuel_inputs(years, scope=scope).items():
            for slug, bucket in territories.items():
                result[year].setdefault(slug, {})[capacity_class] = bucket
    return result


def pending_submissions(years, scope="operating"):
    scopes = (scope,) if isinstance(scope, str) else scope
    return EcologyFuelSubmission.query.filter_by(
        database_version_id=_version_id(), status="pending",
    ).filter(
        EcologyFuelSubmission.year_number.in_(years), EcologyFuelSubmission.scope.in_(scopes),
    ).order_by(EcologyFuelSubmission.id.desc()).all()


def submit_fuel_year(year, scope="operating"):
    if scope not in FUEL_SUMMARY_LABELS:
        raise ValueError("Неизвестный раздел сводки")
    version_id = _version_id()
    from app.ecology.services.fuel_summary_services import load_fuel_summary

    inputs = load_fuel_summary([year], scope)
    # Один замок на раздел и год сериализует отправку и рассмотрение пакета.
    snapshot = EcologyFuelSnapshot.query.filter_by(
        database_version_id=version_id, year_number=year, scope=scope,
    ).with_for_update().first()
    if snapshot is None:
        db.session.execute(
            insert(EcologyFuelSnapshot).values(
                database_version_id=version_id, year_number=year, scope=scope, payload={},
            ).on_conflict_do_nothing(index_elements=["database_version_id", "year_number", "scope"])
        )
        snapshot = EcologyFuelSnapshot.query.filter_by(
            database_version_id=version_id, year_number=year, scope=scope,
        ).with_for_update().one()
    payload = encode_inputs(inputs.get(year, {}))
    for previous in pending_submissions([year], scope=scope):
        previous.status = "superseded"
    submission = EcologyFuelSubmission(database_version_id=version_id, year_number=year, scope=scope, payload=payload, status="pending")
    db.session.add(submission)
    db.session.commit()
    return submission


def get_submission(submission_id):
    return EcologyFuelSubmission.query.filter_by(id=submission_id, database_version_id=_version_id()).first()


def review_fuel_submission(submission_id, accept):
    submission = get_submission(submission_id)
    if submission is None:
        raise ValueError("Пакет не найден в текущей версии базы данных")
    snapshot = EcologyFuelSnapshot.query.filter_by(
        database_version_id=submission.database_version_id, year_number=submission.year_number, scope=submission.scope,
    ).with_for_update().one()
    db.session.refresh(submission)
    if submission.status != "pending":
        raise ValueError("Пакет уже рассмотрен или заменён новой отправкой. Обновите страницу.")
    if accept:
        snapshot.payload = submission.payload
        # Прежние ручные переопределения не должны перекрывать принятый пакет.
        if submission.scope == "operating":
            OperatingTesInputValue.query.filter_by(
                database_version_id=submission.database_version_id, year_number=submission.year_number,
            ).delete(synchronize_session=False)
    submission.status = "accepted" if accept else "rejected"
    submission.reviewed_at = func.now()
    db.session.commit()
    return submission


def submission_differences(submission):
    old = load_accepted_fuel_inputs([submission.year_number], scope=submission.scope)[submission.year_number]
    new = decode_inputs(submission.payload)
    differences = []
    specs = [(spec, bucket_top_input_amount) for spec in TOP_INPUT_ROWS]
    specs += [(spec, bucket_field_amount) for spec in get_fuel_module_consumption_row_specs()]
    territories = get_territory_columns()
    for spec, amount in specs:
        for territory in territories:
            slug = territory["slug"]
            before = amount(old.get(slug), spec["key"])
            after = amount(new.get(slug), spec["key"])
            if (before or Decimal(0)) != (after or Decimal(0)):
                differences.append({
                    "label": spec["label"], "territory": territory["sheet_name"],
                    "unit": spec.get("unit") or "тыс. т у.т.",
                    "before": before or Decimal(0), "after": after or Decimal(0),
                    "delta": (after or Decimal(0)) - (before or Decimal(0)),
                })
    return differences
