from sqlalchemy import and_, func, or_, select

from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_name_model import MachineName
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_name_model import PGUMachineName
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.generation.models.station.station_model import Station
from app.rational_structure.models import TechnicalInspectionCode, TurbineTechnicalCharacteristic
from app.refdata.models.gen_companies.gen_company_model import GenCompany


def load_machine_candidates(version_id: int, report_year: int) -> list[dict]:
    statement = (
        select(
            Machine.id.label("machine_id"),
            Station.id.label("station_id"),
            GenCompany.name.label("subject_name"),
            Station.name.label("station_name"),
            Machine.machine_number.label("station_number"),
            func.coalesce(func.nullif(func.trim(MachineName.name), ""), Machine.machine_name).label("equipment_brand"),
            MachinePower.p_ust.label("installed_electric_power"),
        )
        .select_from(Machine)
        .join(Station, and_(Station.id == Machine.id_station, Station.database_version_id == version_id))
        .outerjoin(GenCompany, and_(
            GenCompany.id == Machine.id_gen_company,
            or_(GenCompany.database_version_id == version_id, GenCompany.database_version_id.is_(None)),
        ))
        .outerjoin(MachineName, and_(
            MachineName.id_machine == Machine.id,
            MachineName.year_number == report_year,
            MachineName.database_version_id == version_id,
        ))
        .outerjoin(MachinePower, and_(
            MachinePower.id_machine == Machine.id,
            MachinePower.year_number == report_year,
            MachinePower.database_version_id == version_id,
        ))
        .where(
            Machine.database_version_id == version_id,
            ~Machine.id.in_(select(PGUMachine.id_parent_machine).where(PGUMachine.database_version_id == version_id)),
        )
        .order_by(Station.id, Machine.id)
    )
    return [dict(row) for row in db.session.execute(statement).mappings()]


def load_pgu_machine_candidates(version_id: int, report_year: int) -> list[dict]:
    statement = (
        select(
            Machine.id.label("machine_id"),
            PGUMachine.id.label("pgu_machine_id"),
            Station.id.label("station_id"),
            GenCompany.name.label("subject_name"),
            Station.name.label("station_name"),
            PGUMachine.machine_number.label("station_number"),
            func.coalesce(func.nullif(func.trim(PGUMachineName.name), ""), PGUMachine.machine_name).label("equipment_brand"),
            PGUMachinePower.p_ust.label("installed_electric_power"),
        )
        .select_from(PGUMachine)
        .join(Machine, and_(Machine.id == PGUMachine.id_parent_machine, Machine.database_version_id == version_id))
        .join(Station, and_(Station.id == Machine.id_station, Station.database_version_id == version_id))
        .outerjoin(GenCompany, and_(
            GenCompany.id == Machine.id_gen_company,
            or_(GenCompany.database_version_id == version_id, GenCompany.database_version_id.is_(None)),
        ))
        .outerjoin(PGUMachineName, and_(
            PGUMachineName.id_pgu_machine == PGUMachine.id,
            PGUMachineName.year_number == report_year,
            PGUMachineName.database_version_id == version_id,
        ))
        .outerjoin(PGUMachinePower, and_(
            PGUMachinePower.id_pgu_machine == PGUMachine.id,
            PGUMachinePower.year_number == report_year,
            PGUMachinePower.database_version_id == version_id,
        ))
        .where(PGUMachine.database_version_id == version_id)
        .order_by(Station.id, Machine.id, PGUMachine.id)
    )
    return [dict(row) for row in db.session.execute(statement).mappings()]


def get_pgu_machine_technical_inspection_codes(pgu_machine_id: int, version_id: int | None) -> list[str]:
    model = TurbineTechnicalCharacteristic
    statement = (
        select(model.equipment_code)
        .join(PGUMachine, PGUMachine.id == model.pgu_machine_id)
        .where(
            model.pgu_machine_id == pgu_machine_id,
            model.database_version_id == version_id,
            PGUMachine.database_version_id == version_id,
            model.match_status == "matched",
        )
        .distinct()
        .order_by(model.equipment_code)
    )
    saved = select(TechnicalInspectionCode.equipment_code).join(
        PGUMachine, PGUMachine.id == TechnicalInspectionCode.pgu_machine_id,
    ).where(
        TechnicalInspectionCode.pgu_machine_id == pgu_machine_id,
        TechnicalInspectionCode.database_version_id == version_id,
        PGUMachine.database_version_id == version_id,
    )
    return sorted(set(db.session.scalars(statement)) | set(db.session.scalars(saved)))


def get_machine_technical_inspection_codes(machine_id: int, version_id: int | None) -> list[str]:
    model = TurbineTechnicalCharacteristic
    statement = (
        select(model.equipment_code)
        .join(Machine, Machine.id == model.machine_id)
        .where(
            model.machine_id == machine_id,
            model.database_version_id == version_id,
            Machine.database_version_id == version_id,
            model.match_status == "matched",
        )
        .distinct()
        .order_by(model.equipment_code)
    )
    saved = select(TechnicalInspectionCode.equipment_code).join(
        Machine, Machine.id == TechnicalInspectionCode.machine_id,
    ).where(
        TechnicalInspectionCode.machine_id == machine_id,
        TechnicalInspectionCode.database_version_id == version_id,
        Machine.database_version_id == version_id,
    )
    return sorted(set(db.session.scalars(statement)) | set(db.session.scalars(saved)))


def get_machine_station_id(machine_id: int, version_id: int) -> int | None:
    """Возвращает station_id для машины в указанной версии БД."""
    statement = (
        select(Machine.id_station)
        .where(Machine.id == machine_id, Machine.database_version_id == version_id)
    )
    return db.session.scalar(statement)
