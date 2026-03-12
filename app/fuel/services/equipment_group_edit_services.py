# -*- coding: utf-8 -*-
"""Сервис редактирования групп оборудования (EquipmentGroup)."""

from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import (
    EquipmentGroupSetStation,
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
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.common.services.database_version_filter import filter_by_db_version


def get_equipment_group_edit_context(equipment_group_id):
    """
    Загружает EquipmentGroup и справочники для выпадающих списков.
    Возвращает dict с equipment_group и choices для каждого FK-поля.
    """
    group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
    if not group:
        return None

    # Справочники для выпадающих списков (external_id -> display_name)
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
    # codegor -> CitiesExternalMapping.code (Integer), EquipmentGroup.codegor - string
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

    # Как на странице stations_equipment_groups
    d_choices = [("", "—"), ("1", "да")]
    r_choices = [("", "—"), ("1", "да")]
    forem_choices = [("", "—"), ("1", "да")]
    vedomstvo_choices = [
        ("", "—"),
        ("1", "станция отрасли"),
        ("2", "пром. предприятие"),
    ]

    # Субъект РФ и Региональная энергосистема (regional_district_id, regional_energy_system_id)
    rd_query = filter_by_db_version(RegionalDistrict.query, RegionalDistrict)
    regional_district_choices = [
        ("", "—"),
        *[(str(r.id), r.name or str(r.id)) for r in rd_query.order_by(RegionalDistrict.name).all()],
    ]
    res_query = filter_by_db_version(RegionalEnergySystem.query, RegionalEnergySystem)
    regional_energy_system_choices = [
        ("", "—"),
        *[(str(r.id), r.name or str(r.id)) for r in res_query.order_by(RegionalEnergySystem.name).all()],
    ]

    # Отображаемые значения для режима чтения (по choices)
    def _label_for(choices, val):
        v = (val or "").strip()
        for cval, clabel in choices:
            if (cval or "").strip() == v:
                return clabel
        return val or "—"

    def _label_for_id(choices, val):
        """Для integer FK (regional_district_id, regional_energy_system_id)."""
        if val is None:
            return "—"
        return _label_for(choices, str(val))

    choice_displays = {
        "regional_district_id": _label_for_id(regional_district_choices, group.regional_district_id),
        "regional_energy_system_id": _label_for_id(regional_energy_system_choices, group.regional_energy_system_id),
        "obl": _label_for(obl_choices, group.obl),
        "dep": _label_for(dep_choices, group.dep),
        "oes": _label_for(oes_choices, group.oes),
        "er": _label_for(er_choices, group.er),
        "fo": _label_for(fo_choices, group.fo),
        "codegor": _label_for(codegor_choices, group.codegor),
        "be": _label_for(be_choices, group.be),
        "gk": _label_for(gk_choices, group.gk),
        "gkf": _label_for(gkf_choices, group.gkf),
        "d": _label_for(d_choices, group.d),
        "r": _label_for(r_choices, group.r),
        "forem": _label_for(forem_choices, group.forem),
        "vedomstvo": _label_for(vedomstvo_choices, group.vedomstvo),
    }

    return {
        "equipment_group": group,
        "regional_district_choices": regional_district_choices,
        "regional_energy_system_choices": regional_energy_system_choices,
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
        "choice_displays": choice_displays,
    }


def _get_station_id_for_equipment_group(equipment_group_id: int):
    """Возвращает station_id из первой связи группы, или 0 если связей нет."""
    sets = EquipmentGroupSet.query.filter_by(equipment_group_id=equipment_group_id).all()
    for s in sets:
        link = EquipmentGroupSetStation.query.get(s.equipment_group_set_station_id)
        if link:
            return link.station_id
    return 0


def update_equipment_group_from_form(equipment_group_id, form_data):
    """
    Обновляет EquipmentGroup из данных формы.
    При совпадении наименования с другой группой — объединяет дубликаты (как на station_details).
    Возвращает (success: bool, message: str).
    """
    from app.extensions import db
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.fuel.services.equipment_group_merge_services import (
        rename_or_merge_equipment_group_for_station,
    )

    group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
    if not group:
        return False, "Группа оборудования не найдена"

    new_name = (form_data.get("name") or "").strip()
    current_version_id = get_current_db_version_id()
    station_id = _get_station_id_for_equipment_group(equipment_group_id)

    # Сначала объединяем дубликаты по имени (как на station_details)
    result = rename_or_merge_equipment_group_for_station(
        station_id=station_id,
        equipment_group_id=equipment_group_id,
        new_name=new_name or (group.name or "").strip(),
        current_version_id=current_version_id,
    )
    target_id = result["primary_id"] if result["merged"] else equipment_group_id

    # Применяем данные формы к целевой группе
    target_group = EquipmentGroup.query.filter_by(id=target_id).first()
    if not target_group:
        return False, "Группа оборудования не найдена"

    # dep, oes, er, fo, obl, gk, gkf — только для чтения, не обновляются из формы
    str_fields = [
        "name", "niv", "comp", "main", "d", "r", "forem", "vedomstvo",
        "numb", "tm", "n1", "n2", "p1", "p2",
        "ordnumb", "addr", "note", "codegor", "be",
    ]
    for field in str_fields:
        val = form_data.get(field)
        if val is not None:
            setattr(target_group, field, (val.strip() if val else None))

    # regional_district_id и regional_energy_system_id — редактируемые из формы
    def _parse_int(val):
        if not val or not str(val).strip():
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    rd_val = form_data.get("regional_district_id")
    target_group.regional_district_id = _parse_int(rd_val)
    res_val = form_data.get("regional_energy_system_id")
    target_group.regional_energy_system_id = _parse_int(res_val)

    try:
        db.session.commit()
        if result["merged"]:
            return True, "Группа оборудования объединена с существующей группой с таким же наименованием."
        return True, "Данные успешно сохранены"
    except Exception as e:
        db.session.rollback()
        return False, str(e)
