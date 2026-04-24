# -*- coding: utf-8 -*-
"""Сервис добавления групп оборудования (EquipmentGroup)."""

from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_department_model import (
    DepartmentExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_economic_region_model import (
    EconomicRegionExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_federal_district_model import (
    FederalDistrictExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_cities_model import CitiesExternalMapping
from app.fuel.models.external_mapping.fue_em_business_unit_model import (
    BusinessUnitExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_model import (
    GenCompanyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_branch_model import (
    GenCompanyBranchExternalMapping,
)


def get_equipment_group_add_context():
    """
    Возвращает справочники для формы добавления группы оборудования.
    Использует те же choices, что и equipment_group_edit.
    """
    obl_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in TerritoriesEnergyExternalMapping.query.filter(
                TerritoriesEnergyExternalMapping.external_id.isnot(None)
            )
            .order_by(TerritoriesEnergyExternalMapping.external_name, TerritoriesEnergyExternalMapping.external_id)
            .all()
        ],
    ]
    dep_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in DepartmentExternalMapping.query.order_by(
                DepartmentExternalMapping.external_name
            ).all()
        ],
    ]
    oes_choices = [
        ("", "—"),
        *[
            (m.external_id, (m.external_nameoes or m.external_name or m.external_id))
            for m in UnionEnergySystemExternalMapping.query.filter(
                UnionEnergySystemExternalMapping.external_id.isnot(None)
            )
            .order_by(UnionEnergySystemExternalMapping.external_nameoes)
            .all()
        ],
    ]
    er_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in EconomicRegionExternalMapping.query.filter(
                EconomicRegionExternalMapping.external_id.isnot(None)
            )
            .order_by(EconomicRegionExternalMapping.external_name)
            .all()
        ],
    ]
    fo_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in FederalDistrictExternalMapping.query.filter(
                FederalDistrictExternalMapping.external_id.isnot(None)
            )
            .order_by(FederalDistrictExternalMapping.external_name)
            .all()
        ],
    ]
    cities_list = CitiesExternalMapping.query.order_by(CitiesExternalMapping.name).all()
    codegor_choices = [
        ("", "—"),
        *[(str(m.code), (m.name or str(m.code))) for m in cities_list],
    ]
    be_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in BusinessUnitExternalMapping.query.order_by(
                BusinessUnitExternalMapping.external_name
            ).all()
        ],
    ]
    gk_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in GenCompanyExternalMapping.query.filter(
                GenCompanyExternalMapping.external_id.isnot(None)
            )
            .order_by(GenCompanyExternalMapping.external_name)
            .all()
        ],
    ]
    gkf_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in GenCompanyBranchExternalMapping.query.filter(
                GenCompanyBranchExternalMapping.external_id.isnot(None)
            )
            .order_by(GenCompanyBranchExternalMapping.external_name)
            .all()
        ],
    ]

    d_choices = [("", "—"), ("1", "да")]
    r_choices = [("", "—"), ("1", "да")]
    forem_choices = [("", "—"), ("1", "да")]
    vedomstvo_choices = [
        ("", "—"),
        ("1", "станция отрасли"),
        ("2", "пром. предприятие"),
    ]

    return {
        "obl_choices": obl_choices,
        "dep_choices": dep_choices,
        "oes_choices": oes_choices,
        "er_choices": er_choices,
        "fo_choices": fo_choices,
        "codegor_choices": codegor_choices,
        "be_choices": be_choices,
        "gk_choices": gk_choices,
        "gkf_choices": gkf_choices,
        "d_choices": d_choices,
        "r_choices": r_choices,
        "forem_choices": forem_choices,
        "vedomstvo_choices": vedomstvo_choices,
    }


def add_equipment_group_service(form_data, user):
    """
    Создает новую группу оборудования (EquipmentGroup) из данных формы.

    Args:
        form_data: dict с полями формы (request.form)
        user: пользователь для логирования

    Returns:
        tuple: (EquipmentGroup or None, error_message or None)
    """
    str_fields = [
        "name", "name_ext", "niv", "comp", "main", "d", "r", "forem", "vedomstvo",
        "obl", "dep", "oes", "er", "fo", "numb", "tm", "n1", "n2", "p1", "p2",
        "ordnumb", "addr", "note", "codegor", "be", "gk", "gkf",
    ]

    equipment_group = EquipmentGroup()
    version_id = get_current_db_version_id()
    if version_id is not None:
        equipment_group.database_version_id = version_id
    else:
        set_db_version_on_create(equipment_group)

    for field in str_fields:
        val = form_data.get(field)
        if val is not None:
            setattr(equipment_group, field, (val.strip() if val else None))

    # K хранится в EquipmentGroupSpecificFuelConsumption (consumption.k) по году, не в EquipmentGroup

    try:
        db.session.add(equipment_group)
        db.session.flush()
        db.session.commit()
        return equipment_group, None
    except Exception as e:
        db.session.rollback()
        return None, str(e)
