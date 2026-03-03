# -*- coding: utf-8 -*-
"""
Сервисы для создания исторических снимков справочников.
Покрываем территории, энергосистемы и типы станций/агрегатов.
"""
from contextlib import contextmanager
from typing import Any

from flask import current_app, has_request_context, session as flask_session

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.common.services.database_version_filter import get_current_db_version_id
from app.refdata.models.history.refdata_entity_model import (
    RefdataEntity,
    RefdataEntityYear,
)
from app.refdata.models.energy_systems.energy_area_model import EnergyArea
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.fuels.fuel_category_model import FuelCategory
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.machine.machine_type_model import MachineType
from app.refdata.models.refdata_for_stations.machine.pgu_tes_machine_type_model import (
    PGUTesMachineType,
)
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import (
    TesMachineType,
)
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroup,
)
from app.refdata.models.refdata_for_stations.technologies.technology_availability_model import (
    TechnologyAvailability,
)
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import (
    TechnologyType,
)
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_service_model import YearService


def _get_or_create_refdata_entity(
    entity_type: str,
    entity_id: int,
    database_version_id: int | None,
    ref_uuid: str | None,
) -> RefdataEntity:
    entity = None

    # Учитываем уже созданные (но не зафлашенные) записи в рамках текущей сессии,
    # чтобы избежать дублирования ref_uuid при no_autoflush (создание версии БД).
    for obj in db.session.new:
        if not isinstance(obj, RefdataEntity):
            continue
        if ref_uuid and obj.ref_uuid == ref_uuid:
            return obj
        if (
            obj.entity_type == entity_type
            and obj.entity_id == entity_id
            and obj.database_version_id == database_version_id
        ):
            return obj

    if ref_uuid:
        entity = RefdataEntity.query.filter_by(ref_uuid=ref_uuid).first()
    if not entity:
        entity = (
            RefdataEntity.query.filter_by(
                entity_type=entity_type,
                entity_id=entity_id,
                database_version_id=database_version_id,
            ).first()
        )
    if entity:
        return entity
    entity = RefdataEntity(
        entity_type=entity_type,
        entity_id=entity_id,
        database_version_id=database_version_id,
        ref_uuid=ref_uuid,
    )
    db.session.add(entity)
    return entity


def _upsert_refdata_entity_year(
    refdata_entity: RefdataEntity | int,
    year: int,
    database_version_id: int | None,
    payload: dict[str, Any],
) -> bool:
    entity = refdata_entity if isinstance(refdata_entity, RefdataEntity) else None
    entity_id = entity.id if entity is not None else int(refdata_entity)

    # Учитываем уже созданные (но не зафлашенные) записи в рамках текущей сессии,
    # чтобы не ловить дубликаты при no_autoflush.
    for obj in db.session.new:
        if not isinstance(obj, RefdataEntityYear):
            continue
        if (
            obj.refdata_entity_id == entity_id
            and obj.year == year
            and obj.database_version_id == database_version_id
        ):
            obj.payload = payload
            return False

    entity_year = None
    if entity_id is not None:
        entity_year = (
            RefdataEntityYear.query.filter_by(
                refdata_entity_id=entity_id,
                year=year,
                database_version_id=database_version_id,
            ).first()
        )
    if entity_year:
        entity_year.payload = payload
        return False
    if entity is not None and entity.id is None:
        entity_year = RefdataEntityYear(
            refdata_entity=entity,
            year=year,
            database_version_id=database_version_id,
            payload=payload,
        )
    else:
        entity_year = RefdataEntityYear(
            refdata_entity_id=entity_id,
            year=year,
            database_version_id=database_version_id,
            payload=payload,
        )
    db.session.add(entity_year)
    return True


@contextmanager
def _ensure_request_context(user):
    if has_request_context():
        yield
        return
    try:
        app = current_app._get_current_object()
    except Exception:
        app = None
    if app is None:
        yield
        return
    with app.test_request_context():
        if user:
            flask_session["username"] = str(user)
        yield


def _get_current_year_number(database_version_id: int, source_version_id: int | None = None) -> int:
    """
    Возвращает номер текущего года для версии.
    Если указан source_version_id, ищем признак года (Текущий, текущий год, текущий (оценка)) в исходной версии.
    """
    lookup_version_id = source_version_id or database_version_id

    # Единый поиск по подстроке — поддерживаем разные варианты названий в БД
    year_feature = (
        YearFeature.query.filter_by(database_version_id=lookup_version_id)
        .filter(YearFeature.name.ilike("%текущ%"))
        .order_by(YearFeature.id.asc())
        .first()
    )
    if not year_feature:
        raise ValueError("Не найден признак года с названием «Текущий» для выбранной версии.")
    current_year = Year.query.filter_by(
        database_version_id=lookup_version_id,
        id_year_feature=year_feature.id,
    ).first()
    if current_year:
        return current_year.number

    # Fallback 1: используем YearService (если есть) и выводим текущий год как year_sipr_start - 1
    year_service = (
        YearService.query.filter_by(database_version_id=lookup_version_id).first()
    )
    if year_service and year_service.year_sipr_start:
        try:
            return int(year_service.year_sipr_start) - 1
        except Exception:
            pass

    # Fallback 2: берем последний доступный год в версии
    last_year = (
        Year.query.filter_by(database_version_id=lookup_version_id)
        .order_by(Year.number.desc())
        .first()
    )
    if last_year:
        return last_year.number

    raise ValueError("Не найден текущий год для выбранной версии.")


def _federal_district_payload(district: FederalDistrict) -> dict[str, Any]:
    return {
        "name": district.name,
        "name_full": district.name_full,
        "name_abr": district.name_abr,
        "display_order": district.display_order,
    }


def _regional_district_payload(district: RegionalDistrict) -> dict[str, Any]:
    return {
        "name": district.name,
        "name_full": district.name_full,
        "name_rp": district.name_rp,
        "name_dp": district.name_dp,
        "region_number": district.region_number,
        "region_id": district.region_id,
        "id_federal_district": district.id_federal_district,
        "id_energy_zone": district.id_energy_zone,
        "id_synchronous_area": district.id_synchronous_area,
        "regional_energy_system_ids": [
            item.id for item in (district.regional_energy_systems or [])
        ],
    }


def _energy_system_type_payload(system_type: EnergySystemType) -> dict[str, Any]:
    return {
        "name": system_type.name,
    }


def _union_energy_system_payload(system: UnionEnergySystem) -> dict[str, Any]:
    return {
        "name": system.name,
        "name_full": system.name_full,
        "display_order": system.display_order,
        "id_energy_system_type": system.id_energy_system_type,
    }


def _regional_energy_system_payload(system: RegionalEnergySystem) -> dict[str, Any]:
    return {
        "name": system.name,
        "name_full": system.name_full,
        "name_rp": system.name_rp,
        "id_union_energy_system": system.id_union_energy_system,
        "regional_district_ids": [item.id for item in (system.regional_districts or [])],
    }


def _synchronous_area_payload(area: SynchronousArea) -> dict[str, Any]:
    return {
        "number": area.number,
        "name": area.name,
    }


def _energy_zone_payload(zone: EnergyZone) -> dict[str, Any]:
    return {
        "number": zone.number,
        "name": zone.name,
    }


def _energy_area_payload(area: EnergyArea) -> dict[str, Any]:
    return {
        "name": area.name,
        "id_regional_district": area.id_regional_district,
    }


def _energy_unit_payload(unit: EnergyUnit) -> dict[str, Any]:
    return {
        "name": unit.name,
        "id_regional_district": unit.id_regional_district,
        "id_regional_energy_system": unit.id_regional_energy_system,
    }


def _station_type_payload(station_type: StationType) -> dict[str, Any]:
    return {
        "name": station_type.name,
    }


def _condition_type_payload(condition_type: ConditionType) -> dict[str, Any]:
    return {
        "name": condition_type.name,
    }


def _machine_type_payload(machine_type: MachineType) -> dict[str, Any]:
    return {
        "name": machine_type.name,
    }


def _tes_type_payload(tes_type: TesType) -> dict[str, Any]:
    return {
        "name": tes_type.name,
    }


def _tes_machine_type_payload(machine_type: TesMachineType) -> dict[str, Any]:
    return {
        "name": machine_type.name,
    }


def _pgu_tes_machine_type_payload(machine_type: PGUTesMachineType) -> dict[str, Any]:
    return {
        "name": machine_type.name,
    }


def _technology_type_payload(tech_type: TechnologyType) -> dict[str, Any]:
    return {
        "name": tech_type.name,
    }


def _technology_availability_payload(availability: TechnologyAvailability) -> dict[str, Any]:
    return {
        "name": availability.name,
    }


def _equipment_group_payload(group: EquipmentGroup) -> dict[str, Any]:
    return {
        "name": group.name,
        "display_order": group.display_order,
        "id_technology_type": group.id_technology_type,
        "id_technology_availability": group.id_technology_availability,
    }


def _gen_company_payload(company: GenCompany) -> dict[str, Any]:
    return {
        "name": company.name,
        "name_short": company.name_short,
    }


def _fuel_category_payload(category: FuelCategory) -> dict[str, Any]:
    return {
        "name": category.name,
    }


def _fuel_type_payload(fuel_type: FuelType) -> dict[str, Any]:
    return {
        "name": fuel_type.name,
    }


def _fuel_payload(fuel: Fuel) -> dict[str, Any]:
    return {
        "name": fuel.name,
        "id_fuel_type": fuel.id_fuel_type,
    }


REFDATA_HISTORY_MAPPINGS = {
    FederalDistrict: ("federal_district", _federal_district_payload),
    RegionalDistrict: ("regional_district", _regional_district_payload),
    EnergySystemType: ("energy_system_type", _energy_system_type_payload),
    UnionEnergySystem: ("union_energy_system", _union_energy_system_payload),
    RegionalEnergySystem: ("regional_energy_system", _regional_energy_system_payload),
    SynchronousArea: ("synchronous_area", _synchronous_area_payload),
    EnergyZone: ("energy_zone", _energy_zone_payload),
    EnergyArea: ("energy_area", _energy_area_payload),
    EnergyUnit: ("energy_unit", _energy_unit_payload),
    StationType: ("station_type", _station_type_payload),
    ConditionType: ("condition_type", _condition_type_payload),
    MachineType: ("machine_type", _machine_type_payload),
    TesType: ("tes_type", _tes_type_payload),
    TesMachineType: ("tes_machine_type", _tes_machine_type_payload),
    PGUTesMachineType: ("pgu_tes_machine_type", _pgu_tes_machine_type_payload),
    TechnologyType: ("technology_type", _technology_type_payload),
    TechnologyAvailability: ("technology_availability", _technology_availability_payload),
    EquipmentGroup: ("equipment_group", _equipment_group_payload),
    FuelCategory: ("fuel_category", _fuel_category_payload),
    FuelType: ("fuel_type", _fuel_type_payload),
    Fuel: ("fuel", _fuel_payload),
    GenCompany: ("gen_company", _gen_company_payload),
}


def sync_refdata_history_for_instance(instance, session, is_deleted: bool = False) -> bool:
    mapping = REFDATA_HISTORY_MAPPINGS.get(instance.__class__)
    if not mapping:
        return False
    database_version_id = getattr(instance, "database_version_id", None)
    if database_version_id is None:
        return False
    try:
        current_year = _get_current_year_number(database_version_id)
    except ValueError:
        return False

    entity_type, payload_builder = mapping
    entity = _get_or_create_refdata_entity(
        entity_type=entity_type,
        entity_id=instance.id,
        database_version_id=database_version_id,
        ref_uuid=getattr(instance, "ref_uuid", None),
    )
    payload = payload_builder(instance) if not is_deleted else {}
    if is_deleted:
        payload["deleted"] = True
    _upsert_refdata_entity_year(
        refdata_entity=entity,
        year=current_year,
        database_version_id=database_version_id,
        payload=payload,
    )
    return True


def snapshot_territories(
    database_version_id: int,
    year: int,
    user,
    do_commit: bool = True,
) -> dict[str, int]:
    """
    Создает/обновляет исторические снимки территориальных справочников за год.
    Возвращает количество созданных и обновленных записей.
    """
    with _ensure_request_context(user):
        created = 0
        updated = 0

        log_to_db(
            user,
            "Исторический снимок: территории",
            f"database_version_id={database_version_id}, year={year}",
            entity_type="refdata_history",
        )

        federal_districts = FederalDistrict.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for district in federal_districts:
            entity = _get_or_create_refdata_entity(
                entity_type="federal_district",
                entity_id=district.id,
                database_version_id=database_version_id,
                ref_uuid=district.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_federal_district_payload(district),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        regional_districts = RegionalDistrict.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for district in regional_districts:
            entity = _get_or_create_refdata_entity(
                entity_type="regional_district",
                entity_id=district.id,
                database_version_id=database_version_id,
                ref_uuid=district.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_regional_district_payload(district),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        if do_commit:
            db.session.commit()

        log_to_db(
            user,
            "Исторический снимок: территории (готово)",
            f"created={created}, updated={updated}",
            entity_type="refdata_history",
        )

        return {"created": created, "updated": updated}


def snapshot_energy_systems(
    database_version_id: int,
    year: int,
    user,
    do_commit: bool = True,
) -> dict[str, int]:
    """
    Создает/обновляет исторические снимки справочников энергосистем за год.
    Возвращает количество созданных и обновленных записей.
    """
    with _ensure_request_context(user):
        created = 0
        updated = 0

        log_to_db(
            user,
            "Исторический снимок: энергосистемы",
            f"database_version_id={database_version_id}, year={year}",
            entity_type="refdata_history",
        )

        system_types = EnergySystemType.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for system_type in system_types:
            entity = _get_or_create_refdata_entity(
                entity_type="energy_system_type",
                entity_id=system_type.id,
                database_version_id=database_version_id,
                ref_uuid=system_type.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_energy_system_type_payload(system_type),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        union_systems = UnionEnergySystem.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for system in union_systems:
            entity = _get_or_create_refdata_entity(
                entity_type="union_energy_system",
                entity_id=system.id,
                database_version_id=database_version_id,
                ref_uuid=system.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_union_energy_system_payload(system),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        regional_systems = RegionalEnergySystem.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for system in regional_systems:
            entity = _get_or_create_refdata_entity(
                entity_type="regional_energy_system",
                entity_id=system.id,
                database_version_id=database_version_id,
                ref_uuid=system.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_regional_energy_system_payload(system),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        synchronous_areas = SynchronousArea.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for area in synchronous_areas:
            entity = _get_or_create_refdata_entity(
                entity_type="synchronous_area",
                entity_id=area.id,
                database_version_id=database_version_id,
                ref_uuid=area.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_synchronous_area_payload(area),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        energy_zones = EnergyZone.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for zone in energy_zones:
            entity = _get_or_create_refdata_entity(
                entity_type="energy_zone",
                entity_id=zone.id,
                database_version_id=database_version_id,
                ref_uuid=zone.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_energy_zone_payload(zone),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        energy_areas = EnergyArea.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for area in energy_areas:
            entity = _get_or_create_refdata_entity(
                entity_type="energy_area",
                entity_id=area.id,
                database_version_id=database_version_id,
                ref_uuid=area.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_energy_area_payload(area),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        energy_units = EnergyUnit.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for unit in energy_units:
            entity = _get_or_create_refdata_entity(
                entity_type="energy_unit",
                entity_id=unit.id,
                database_version_id=database_version_id,
                ref_uuid=unit.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_energy_unit_payload(unit),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        if do_commit:
            db.session.commit()

        log_to_db(
            user,
            "Исторический снимок: энергосистемы (готово)",
            f"created={created}, updated={updated}",
            entity_type="refdata_history",
        )

        return {"created": created, "updated": updated}


def snapshot_station_machine_types(
    database_version_id: int,
    year: int,
    user,
    do_commit: bool = True,
) -> dict[str, int]:
    """
    Создает/обновляет исторические снимки типов станций и агрегатов за год.
    Возвращает количество созданных и обновленных записей.
    """
    with _ensure_request_context(user):
        created = 0
        updated = 0

        log_to_db(
            user,
            "Исторический снимок: типы станций и агрегатов",
            f"database_version_id={database_version_id}, year={year}",
            entity_type="refdata_history",
        )

        station_types = StationType.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for station_type in station_types:
            entity = _get_or_create_refdata_entity(
                entity_type="station_type",
                entity_id=station_type.id,
                database_version_id=database_version_id,
                ref_uuid=station_type.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_station_type_payload(station_type),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        condition_types = ConditionType.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for condition_type in condition_types:
            entity = _get_or_create_refdata_entity(
                entity_type="condition_type",
                entity_id=condition_type.id,
                database_version_id=database_version_id,
                ref_uuid=condition_type.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_condition_type_payload(condition_type),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        machine_types = MachineType.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for machine_type in machine_types:
            entity = _get_or_create_refdata_entity(
                entity_type="machine_type",
                entity_id=machine_type.id,
                database_version_id=database_version_id,
                ref_uuid=machine_type.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_machine_type_payload(machine_type),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        tes_types = TesType.query.filter_by(database_version_id=database_version_id).all()
        for tes_type in tes_types:
            entity = _get_or_create_refdata_entity(
                entity_type="tes_type",
                entity_id=tes_type.id,
                database_version_id=database_version_id,
                ref_uuid=tes_type.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_tes_type_payload(tes_type),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        tes_machine_types = TesMachineType.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for tes_machine_type in tes_machine_types:
            entity = _get_or_create_refdata_entity(
                entity_type="tes_machine_type",
                entity_id=tes_machine_type.id,
                database_version_id=database_version_id,
                ref_uuid=tes_machine_type.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_tes_machine_type_payload(tes_machine_type),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        pgu_tes_machine_types = PGUTesMachineType.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for pgu_machine_type in pgu_tes_machine_types:
            entity = _get_or_create_refdata_entity(
                entity_type="pgu_tes_machine_type",
                entity_id=pgu_machine_type.id,
                database_version_id=database_version_id,
                ref_uuid=pgu_machine_type.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_pgu_tes_machine_type_payload(pgu_machine_type),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        if do_commit:
            db.session.commit()

        log_to_db(
            user,
            "Исторический снимок: типы станций и агрегатов (готово)",
            f"created={created}, updated={updated}",
            entity_type="refdata_history",
        )

        return {"created": created, "updated": updated}


def snapshot_fuels(
    database_version_id: int,
    year: int,
    user,
    do_commit: bool = True,
) -> dict[str, int]:
    """
    Создает/обновляет исторические снимки топливных справочников за год.
    Возвращает количество созданных и обновленных записей.
    """
    with _ensure_request_context(user):
        created = 0
        updated = 0

        log_to_db(
            user,
            "Исторический снимок: топлива",
            f"database_version_id={database_version_id}, year={year}",
            entity_type="refdata_history",
        )

        fuel_categories = FuelCategory.query.filter_by(
            database_version_id=database_version_id
        ).all()
        for category in fuel_categories:
            entity = _get_or_create_refdata_entity(
                entity_type="fuel_category",
                entity_id=category.id,
                database_version_id=database_version_id,
                ref_uuid=category.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_fuel_category_payload(category),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        fuel_types = FuelType.query.filter_by(database_version_id=database_version_id).all()
        for fuel_type in fuel_types:
            entity = _get_or_create_refdata_entity(
                entity_type="fuel_type",
                entity_id=fuel_type.id,
                database_version_id=database_version_id,
                ref_uuid=fuel_type.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_fuel_type_payload(fuel_type),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        fuels = Fuel.query.filter_by(database_version_id=database_version_id).all()
        for fuel in fuels:
            entity = _get_or_create_refdata_entity(
                entity_type="fuel",
                entity_id=fuel.id,
                database_version_id=database_version_id,
                ref_uuid=fuel.ref_uuid,
            )
            is_created = _upsert_refdata_entity_year(
                refdata_entity=entity,
                year=year,
                database_version_id=database_version_id,
                payload=_fuel_payload(fuel),
            )
            created += 1 if is_created else 0
            updated += 0 if is_created else 1

        if do_commit:
            db.session.commit()

        log_to_db(
            user,
            "Исторический снимок: топлива (готово)",
            f"created={created}, updated={updated}",
            entity_type="refdata_history",
        )

        return {"created": created, "updated": updated}


def snapshot_territories_for_active_version(user) -> dict[str, int]:
    """
    Полный цикл для территорий: активная версия + текущий год.
    """
    active_version_id = get_current_db_version_id()
    if not active_version_id:
        raise ValueError("Активная версия БД не установлена.")
    current_year = _get_current_year_number(active_version_id)
    return snapshot_territories(active_version_id, current_year, user)


def snapshot_territories_for_version(
    database_version_id: int,
    user,
    do_commit: bool = True,
    source_version_id: int | None = None,
) -> dict[str, int]:
    """
    Полный цикл для территорий: указанная версия + текущий год.
    """
    current_year = _get_current_year_number(database_version_id, source_version_id)
    return snapshot_territories(
        database_version_id=database_version_id,
        year=current_year,
        user=user,
        do_commit=do_commit,
    )


def snapshot_energy_systems_for_version(
    database_version_id: int,
    user,
    do_commit: bool = True,
    source_version_id: int | None = None,
) -> dict[str, int]:
    """
    Полный цикл для энергосистем: указанная версия + текущий год.
    """
    current_year = _get_current_year_number(database_version_id, source_version_id)
    return snapshot_energy_systems(
        database_version_id=database_version_id,
        year=current_year,
        user=user,
        do_commit=do_commit,
    )


def snapshot_station_machine_types_for_version(
    database_version_id: int,
    user,
    do_commit: bool = True,
    source_version_id: int | None = None,
) -> dict[str, int]:
    """
    Полный цикл для типов станций/агрегатов: указанная версия + текущий год.
    """
    current_year = _get_current_year_number(database_version_id, source_version_id)
    return snapshot_station_machine_types(
        database_version_id=database_version_id,
        year=current_year,
        user=user,
        do_commit=do_commit,
    )


def snapshot_fuels_for_version(
    database_version_id: int,
    user,
    do_commit: bool = True,
    source_version_id: int | None = None,
) -> dict[str, int]:
    """
    Полный цикл для топлива: указанная версия + текущий год.
    """
    current_year = _get_current_year_number(database_version_id, source_version_id)
    return snapshot_fuels(
        database_version_id=database_version_id,
        year=current_year,
        user=user,
        do_commit=do_commit,
    )
