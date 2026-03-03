from flask import render_template, request, redirect, url_for, session, current_app, send_file, flash, abort
from sqlalchemy import or_, func
import os
import uuid
import pandas as pd
from flask_login import login_required
from datetime import datetime
from types import SimpleNamespace
from io import BytesIO

from app.extensions import db

from . import fuel_bp

from app.generation.forms.station_forms import StationFilterForm
from app.generation.services.station_services.station_services import (
    get_station_list_data,
    get_station_list_template_context,
    clear_station_aggregation_cache,
)
from app.generation.services.station_services.export_cache import (
    build_export_key,
    set_export_payload,
)
from app.generation.services.station_services.filters_services import (
    has_any_filters,
    extract_filters_from_args,
    extract_filters_from_form,
)
from app.common.services.get_services.years.years_get_services import (
    get_filter_start_year,
    get_filter_end_year,
)
from app.common.services.database_version_services import (
    get_current_version_year_range_from_name,
)
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
    get_energy_system_type_name,
)
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    filter_by_explicit_db_version,
)
from app.fuel.services.equipment_group_extra_fuel_params_services import (
    load_equipment_group_extra_fuel_params_for_stations,
)
from app.fuel.services.equipment_group_fuel_params_services import (
    load_equipment_group_fuel_params_for_stations,
    build_obor_name_map,
    build_obl_name_map,
    build_dep_name_map,
    build_oes_name_map,
    build_er_name_map,
    build_gk_name_map,
    build_be_name_map,
)
from app.fuel.services.export_stations_equipment_groups_services import (
    export_stations_equipment_groups_to_excel,
)
from app.fuel.services.import_fuel_db_equipment_groups_services import (
    import_fuel_db_equipment_groups_from_excel,
)
from app.fuel.services.import_equipment_group_fuel_params_services import (
    import_equipment_group_fuel_params_from_excel,
)
from app.fuel.services.import_fuel_refdata_services import (
    import_union_energy_system_mappings_from_excel,
    import_federal_district_mappings_from_excel,
    import_gen_company_mappings_from_excel,
    import_gen_company_branch_mappings_from_excel,
    import_department_mappings_from_excel,
    import_business_unit_mappings_from_excel,
    import_economic_region_mappings_from_excel,
    import_territories_energy_from_excel,
    import_cities_from_excel,
    import_equipment_group_mappings_from_excel,
)
from app.refdata.forms.energy_systems.union_energy_system_forms import (
    UnionEnergySystemFilterForm,
)
from app.refdata.forms.territories.federal_district_forms import (
    FederalDistrictFilterForm,
)
from app.refdata.forms.gen_companies.gen_company_forms import (
    GenCompanyFilterForm,
)
from app.refdata.forms.organizations.department_forms import DepartmentFilterForm
from app.refdata.forms.organizations.business_unit_forms import BusinessUnitFilterForm
from app.refdata.forms.organizations.economic_region_forms import (
    EconomicRegionFilterForm,
)
from app.refdata.forms.refdata_for_stations.technologies.equipment_group_forms import (
    EquipmentGroupFilterForm,
)
from app.refdata.services.energy_systems.union_energy_system_services import (
    get_union_energy_system_list,
    export_union_energy_system_service,
    union_energy_system_query,
)
from app.refdata.services.territories.federal_district_services import (
    get_federal_district_list,
    export_federal_district_mappings_service,
    federal_district_query,
)
from app.refdata.services.gen_companies.gen_company_services import (
    get_gen_company_list,
    gen_company_query,
    export_gen_company_mappings_service,
)
from app.refdata.services.organizations.department_services import (
    get_department_list,
    export_department_mappings_service,
    department_query,
)
from app.refdata.services.organizations.business_unit_services import (
    get_business_unit_list,
    export_business_unit_mappings_service,
    business_unit_query,
)
from app.refdata.services.organizations.economic_region_services import (
    get_economic_region_list,
    export_economic_region_mappings_service,
    economic_region_query,
)
from app.refdata.services.refdata_for_stations.technologies.equipment_group_services import (
    get_equipment_group_list,
    equipment_group_query,
    export_equipment_group_mappings_service,
)
from app.common.models.pagination import Pagination
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_federal_district_model import (
    FederalDistrictExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_model import (
    GenCompanyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_branch_model import (
    GenCompanyBranchExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_department_model import (
    DepartmentExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_cities_model import CitiesExternalMapping
from app.fuel.models.external_mapping.fue_em_business_unit_model import (
    BusinessUnitExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_economic_region_model import (
    EconomicRegionExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_economic_region_model import (
    EconomicRegionExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_equipment_group_model import (
    EquipmentGroupExternalMapping,
)
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroup,
)
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.logs.services.logging_service import log_to_db


def _attach_territories_energy_names(items):
    if not items:
        return

    current_version_id = get_current_db_version_id()
    rd_uuids = {
        item.regional_district_ref_uuid
        for item in items
        if item.regional_district_ref_uuid
    }
    res_uuids = {
        item.regional_energy_system_ref_uuid
        for item in items
        if item.regional_energy_system_ref_uuid
    }
    eu_uuids = {item.energy_zone_ref_uuid for item in items if item.energy_zone_ref_uuid}

    def _normalize_uuid(value: str) -> str:
        return (
            str(value or "")
            .strip()
            .lower()
            .replace("{", "")
            .replace("}", "")
        )

    def _normalize_external_id(value: str) -> str:
        return str(value or "").strip()

    rd_uuid_keys = [_normalize_uuid(value) for value in rd_uuids if value]
    res_uuid_keys = [_normalize_uuid(value) for value in res_uuids if value]
    eu_uuid_keys = [_normalize_uuid(value) for value in eu_uuids if value]

    regional_district_names = {}
    energy_zone_by_rd_names = {}
    if rd_uuid_keys:
        rd_query = RegionalDistrict.query.with_entities(
            RegionalDistrict.ref_uuid,
            RegionalDistrict.name,
            RegionalDistrict.database_version_id,
        )
        rd_ref_uuid_key = func.lower(
            func.trim(
                func.replace(func.replace(RegionalDistrict.ref_uuid, "{", ""), "}", "")
            )
        )
        rd_query = rd_query.filter(rd_ref_uuid_key.in_(rd_uuid_keys))
        rd_query = filter_by_explicit_db_version(rd_query, RegionalDistrict, current_version_id)
        for ref_uuid, name, version_id in rd_query.all():
            key = _normalize_uuid(ref_uuid)
            if not key:
                continue
            if key not in regional_district_names:
                regional_district_names[key] = name
            elif current_version_id is not None and version_id == current_version_id:
                regional_district_names[key] = name

        ez_query = (
            RegionalDistrict.query
            .join(EnergyZone, RegionalDistrict.id_energy_zone == EnergyZone.id)
            .with_entities(RegionalDistrict.ref_uuid, EnergyZone.number)
        )
        ez_query = ez_query.filter(rd_ref_uuid_key.in_(rd_uuid_keys))
        ez_query = filter_by_explicit_db_version(ez_query, RegionalDistrict, current_version_id)
        for ref_uuid, ez_name in ez_query.all():
            key = _normalize_uuid(ref_uuid)
            if key and key not in energy_zone_by_rd_names:
                energy_zone_by_rd_names[key] = ez_name

    regional_energy_system_names = {}
    if res_uuid_keys:
        res_query = RegionalEnergySystem.query.with_entities(
            RegionalEnergySystem.ref_uuid,
            RegionalEnergySystem.name,
            RegionalEnergySystem.database_version_id,
        )
        res_ref_uuid_key = func.lower(
            func.trim(
                func.replace(
                    func.replace(RegionalEnergySystem.ref_uuid, "{", ""), "}", ""
                )
            )
        )
        res_query = res_query.filter(res_ref_uuid_key.in_(res_uuid_keys))
        res_query = filter_by_explicit_db_version(res_query, RegionalEnergySystem, current_version_id)
        for ref_uuid, name, version_id in res_query.all():
            key = _normalize_uuid(ref_uuid)
            if not key:
                continue
            if key not in regional_energy_system_names:
                regional_energy_system_names[key] = name
            elif current_version_id is not None and version_id == current_version_id:
                regional_energy_system_names[key] = name

    energy_unit_names = {}
    if eu_uuid_keys:
        eu_query = EnergyUnit.query.with_entities(
            EnergyUnit.ref_uuid,
            EnergyUnit.name,
            EnergyUnit.database_version_id,
        )
        eu_ref_uuid_key = func.lower(
            func.trim(func.replace(func.replace(EnergyUnit.ref_uuid, "{", ""), "}", ""))
        )
        eu_query = eu_query.filter(eu_ref_uuid_key.in_(eu_uuid_keys))
        eu_query = filter_by_explicit_db_version(eu_query, EnergyUnit, current_version_id)
        for ref_uuid, name, version_id in eu_query.all():
            key = _normalize_uuid(ref_uuid)
            if not key:
                continue
            if key not in energy_unit_names:
                energy_unit_names[key] = name
            elif current_version_id is not None and version_id == current_version_id:
                energy_unit_names[key] = name

    dep_ids = {
        _normalize_external_id(item.dep) for item in items if item.dep
    }
    oes_ids = {
        _normalize_external_id(item.oes) for item in items if item.oes
    }
    fo_ids = {_normalize_external_id(item.fo) for item in items if item.fo}
    er_ids = {_normalize_external_id(item.er) for item in items if item.er}

    department_names = {}
    if dep_ids:
        dep_query = DepartmentExternalMapping.query.with_entities(
            DepartmentExternalMapping.external_id,
            DepartmentExternalMapping.external_name,
        )
        dep_query = dep_query.filter(DepartmentExternalMapping.external_id.in_(dep_ids))
        for external_id, external_name in dep_query.all():
            key = _normalize_external_id(external_id)
            if key and key not in department_names:
                department_names[key] = external_name or ""

    union_energy_system_names = {}
    if oes_ids:
        ues_query = UnionEnergySystemExternalMapping.query.with_entities(
            UnionEnergySystemExternalMapping.external_id,
            UnionEnergySystemExternalMapping.external_name,
            UnionEnergySystemExternalMapping.external_nameoes,
        )
        ues_query = ues_query.filter(
            UnionEnergySystemExternalMapping.external_id.in_(oes_ids)
        )
        for external_id, external_name, external_nameoes in ues_query.all():
            key = _normalize_external_id(external_id)
            if key and key not in union_energy_system_names:
                union_energy_system_names[key] = external_name or external_nameoes or ""

    federal_district_names = {}
    if fo_ids:
        fd_query = FederalDistrictExternalMapping.query.with_entities(
            FederalDistrictExternalMapping.external_id,
            FederalDistrictExternalMapping.external_name,
        )
        fd_query = fd_query.filter(FederalDistrictExternalMapping.external_id.in_(fo_ids))
        for external_id, external_name in fd_query.all():
            key = _normalize_external_id(external_id)
            if key and key not in federal_district_names:
                federal_district_names[key] = external_name or ""

    economic_region_names = {}
    if er_ids:
        er_query = EconomicRegionExternalMapping.query.with_entities(
            EconomicRegionExternalMapping.external_id,
            EconomicRegionExternalMapping.external_name,
        )
        er_query = er_query.filter(EconomicRegionExternalMapping.external_id.in_(er_ids))
        for external_id, external_name in er_query.all():
            key = _normalize_external_id(external_id)
            if key and key not in economic_region_names:
                economic_region_names[key] = external_name or ""

    for item in items:
        rd_key = _normalize_uuid(item.regional_district_ref_uuid)
        res_key = _normalize_uuid(item.regional_energy_system_ref_uuid)
        ez_key = _normalize_uuid(item.energy_zone_ref_uuid)
        dep_key = _normalize_external_id(item.dep)
        oes_key = _normalize_external_id(item.oes)
        fo_key = _normalize_external_id(item.fo)
        er_key = _normalize_external_id(item.er)
        item.regional_district_name = regional_district_names.get(rd_key, "")
        item.energy_zone_by_subject_number = energy_zone_by_rd_names.get(rd_key, "")
        item.regional_energy_system_name = regional_energy_system_names.get(res_key, "")
        item.energy_zone_name = energy_unit_names.get(ez_key, "")
        item.dep_name = department_names.get(dep_key, "")
        item.oes_name = union_energy_system_names.get(oes_key, "")
        item.fo_name = federal_district_names.get(fo_key, "")
        item.er_name = economic_region_names.get(er_key, "")


def _sort_text_value(value):
    if value is None or str(value).strip() == "":
        return (2, "")
    text = str(value).strip()
    if text.isdigit():
        return (0, int(text))
    return (1, text.lower())


@fuel_bp.route("/")
def fuel_start():
    return render_template("fuel/fuel_start.html")


@fuel_bp.route("/refdata")
@login_required
def fuel_refdata_start():
    return render_template("fuel/refdata/fuel_refdata.html")


@fuel_bp.route("/refdata/territories_energy", methods=["GET"])
@login_required
def fuel_territories_energy_list():
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница субъектов РФ/РЭС/энергорайонов (Топливо)",
        entity_type="territories_energy",
    )

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "external_id")
    sort_dir = request.args.get("sort_dir", "asc")
    territories_energy_filter = request.args.get("territories_energy_filter", "").strip()

    display_sort_fields = {
        "regional_district_name",
        "regional_energy_system_name",
        "energy_zone_name",
    }
    allowed_sort = {
        "id",
        "name_ext",
        "ao",
        "obl",
        "alph",
        "dep",
        "oes",
        "er",
        "terr_belyaev",
        "teo90",
        "fo",
        "abbr",
        "reu",
        "pter",
        "keyword",
        *display_sort_fields,
    }
    if sort_by not in allowed_sort:
        sort_by = "id"
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"

    query = TerritoriesEnergyExternalMapping.query
    if territories_energy_filter:
        like_term = f"%{territories_energy_filter}%"
        query = query.filter(
            or_(
                TerritoriesEnergyExternalMapping.name_ext.ilike(like_term),
                TerritoriesEnergyExternalMapping.ao.ilike(like_term),
                TerritoriesEnergyExternalMapping.obl.ilike(like_term),
                TerritoriesEnergyExternalMapping.alph.ilike(like_term),
                TerritoriesEnergyExternalMapping.dep.ilike(like_term),
                TerritoriesEnergyExternalMapping.oes.ilike(like_term),
                TerritoriesEnergyExternalMapping.er.ilike(like_term),
                TerritoriesEnergyExternalMapping.terr_belyaev.ilike(like_term),
                TerritoriesEnergyExternalMapping.teo90.ilike(like_term),
                TerritoriesEnergyExternalMapping.fo.ilike(like_term),
                TerritoriesEnergyExternalMapping.abbr.ilike(like_term),
                TerritoriesEnergyExternalMapping.reu.ilike(like_term),
                TerritoriesEnergyExternalMapping.pter.ilike(like_term),
                TerritoriesEnergyExternalMapping.keyword.ilike(like_term),
            )
        )

    if sort_by in display_sort_fields:
        rows = query.all()
        _attach_territories_energy_names(rows)
        rows.sort(
            key=lambda row: _sort_text_value(getattr(row, sort_by, None)),
            reverse=(sort_dir == "desc"),
        )
        total = len(rows)
        pagination = Pagination(page=page, per_page=per_page, total=total)
        start = (page - 1) * per_page
        end = start + per_page
        items = rows[start:end]
    else:
        sort_col = getattr(
            TerritoriesEnergyExternalMapping, sort_by, TerritoriesEnergyExternalMapping.id
        )
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        items = pagination.items or []
        _attach_territories_energy_names(items)

    return render_template(
        "fuel/refdata/territories_energy/territories_energy.html",
        items=items,
        pagination=pagination,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        territories_energy_filter=territories_energy_filter,
    )


@fuel_bp.route("/refdata/territories_energy/export", methods=["GET"])
@login_required
def export_fuel_territories_energy():
    user = session.get("username", "Неизвестный пользователь")
    territories_energy_filter = request.args.get("territories_energy_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    display_sort_fields = {
        "regional_district_name",
        "regional_energy_system_name",
        "energy_zone_name",
    }
    allowed_sort = {
        "id",
        "name_ext",
        "ao",
        "obl",
        "alph",
        "dep",
        "oes",
        "er",
        "terr_belyaev",
        "teo90",
        "fo",
        "abbr",
        "reu",
        "pter",
        "keyword",
        *display_sort_fields,
    }
    if sort_by not in allowed_sort:
        sort_by = "id"
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"

    query = TerritoriesEnergyExternalMapping.query
    if territories_energy_filter:
        like_term = f"%{territories_energy_filter}%"
        query = query.filter(
            or_(
                TerritoriesEnergyExternalMapping.name_ext.ilike(like_term),
                TerritoriesEnergyExternalMapping.ao.ilike(like_term),
                TerritoriesEnergyExternalMapping.obl.ilike(like_term),
                TerritoriesEnergyExternalMapping.alph.ilike(like_term),
                TerritoriesEnergyExternalMapping.dep.ilike(like_term),
                TerritoriesEnergyExternalMapping.oes.ilike(like_term),
                TerritoriesEnergyExternalMapping.er.ilike(like_term),
                TerritoriesEnergyExternalMapping.terr_belyaev.ilike(like_term),
                TerritoriesEnergyExternalMapping.teo90.ilike(like_term),
                TerritoriesEnergyExternalMapping.fo.ilike(like_term),
                TerritoriesEnergyExternalMapping.abbr.ilike(like_term),
                TerritoriesEnergyExternalMapping.reu.ilike(like_term),
                TerritoriesEnergyExternalMapping.pter.ilike(like_term),
                TerritoriesEnergyExternalMapping.keyword.ilike(like_term),
            )
        )

    if sort_by in display_sort_fields:
        rows = query.all()
        _attach_territories_energy_names(rows)
        rows.sort(
            key=lambda row: _sort_text_value(getattr(row, sort_by, None)),
            reverse=(sort_dir == "desc"),
        )
    else:
        sort_col = getattr(
            TerritoriesEnergyExternalMapping, sort_by, TerritoriesEnergyExternalMapping.id
        )
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
        rows = query.all()
        _attach_territories_energy_names(rows)

    data = []
    for row in rows:
        data.append(
            {
                "Название": row.name_ext or "",
                "АО": row.ao or "",
                "Номер": row.obl or "",
                "Alph": row.alph or "",
                "Департамент": row.dep_name or row.dep or "",
                "ОЭС": row.oes_name or row.oes or "",
                "Экономический район": row.er_name or row.er or "",
                "terr_belyaev": row.terr_belyaev or "",
                "teo90": row.teo90 or "",
                "Федеральный округ": row.fo_name or row.fo or "",
                "Сокр.": row.abbr or "",
                "РЭУ": row.reu or "",
                "pter": row.pter or "",
                "Ключевое слово": row.keyword or "",
                "Номер энергозоны": row.energy_zone_by_subject_number or "",
                "Субъект РФ": row.regional_district_name or "",
                "Региональная энергосистема": row.regional_energy_system_name or "",
                "Энергорайон": row.energy_zone_name or "",
            }
        )

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="TerritoriesEnergy")
    output.seek(0)

    log_to_db(user, "Выгрузка территорий/энергосистем в Excel", entity_type="territories_energy")
    return send_file(
        output,
        as_attachment=True,
        download_name="territories_energy.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@fuel_bp.route("/refdata/union_energy_system", methods=["GET"])
@login_required
def fuel_union_energy_system_list():
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница ОЭС (Топливо)",
        entity_type="union_energy_system",
    )

    form = UnionEnergySystemFilterForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    # По умолчанию сортируем по полю "Номер" (code)
    sort_by = request.args.get("sort_by", "code")
    sort_dir = request.args.get("sort_dir", "asc")
    union_energy_system_filter = request.args.get("union_energy_system_filter", "").strip()
    energy_system_type_filter = request.args.get("energy_system_type_filter", "").strip()

    mapping_sort_fields = {
        "external_id",
        "external_name",
        "external_nameoes",
        "external_abbr",
    }
    display_rows = None
    if sort_by in mapping_sort_fields:
        query = union_energy_system_query(
            union_energy_system_filter=union_energy_system_filter,
            energy_system_type_filter=energy_system_type_filter,
            sort_by="id",
            sort_dir="asc",
        )
        all_items = query.all()
    else:
        pagination = get_union_energy_system_list(
            page=page,
            per_page=per_page,
            union_energy_system_filter=union_energy_system_filter,
            energy_system_type_filter=energy_system_type_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        all_items = pagination.items

    mappings = UnionEnergySystemExternalMapping.query.order_by(
        UnionEnergySystemExternalMapping.id.desc()
    ).all()
    mapping_by_ues = {}
    unmatched_mappings = []
    for mapping in mappings:
        if mapping.union_energy_system_ref_uuid:
            if mapping.union_energy_system_ref_uuid not in mapping_by_ues:
                mapping_by_ues[mapping.union_energy_system_ref_uuid] = mapping
        else:
            unmatched_mappings.append(mapping)

    if sort_by in mapping_sort_fields:
        def _sort_key(row):
            mapping = row.mapping
            value = getattr(mapping, sort_by, None) if mapping else None
            if value is None or str(value).strip() == "":
                return (2, "")
            text = str(value).strip()
            if text.isdigit():
                return (0, int(text))
            return (1, text.lower())

        rows = [SimpleNamespace(ues=ues, mapping=mapping_by_ues.get(ues.ref_uuid)) for ues in all_items]
        rows.extend([SimpleNamespace(ues=None, mapping=m) for m in unmatched_mappings])
        rows.sort(key=_sort_key, reverse=(sort_dir == "desc"))
        total = len(rows)
        pagination = Pagination(page=page, per_page=per_page, total=total)
        start = (page - 1) * per_page
        end = start + per_page
        display_rows = rows[start:end]

    energy_system_types = get_energy_system_type_list_full()
    form.energy_system_type.choices = [(est.id, est.name) for est in energy_system_types]

    return render_template(
        "fuel/refdata/union_energy_system/union_energy_system.html",
        form=form,
        union_energy_system_list=pagination.items if sort_by not in mapping_sort_fields else [],
        pagination=pagination,
        energy_system_types=form.energy_system_type.choices,
        union_energy_system_filter=union_energy_system_filter,
        energy_system_type_filter=energy_system_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        mapping_by_ues=mapping_by_ues,
        unmatched_mappings=unmatched_mappings,
        display_rows=display_rows,
    )


@fuel_bp.route("/refdata/federal_district", methods=["GET"])
@login_required
def fuel_federal_district_list():
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница ФО (Топливо)",
        entity_type="federal_district",
    )

    form = FederalDistrictFilterForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    federal_district_filter = request.args.get("federal_district_filter", "").strip()

    mapping_sort_fields = {"external_id", "external_name"}
    display_rows = None
    if sort_by in mapping_sort_fields:
        query = federal_district_query(
            federal_district_filter=federal_district_filter,
            sort_by="id",
            sort_dir="asc",
        )
        all_items = query.all()
    else:
        pagination = get_federal_district_list(
            page=page,
            per_page=per_page,
            federal_district_filter=federal_district_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        all_items = pagination.items

    mappings = FederalDistrictExternalMapping.query.order_by(
        FederalDistrictExternalMapping.id.desc()
    ).all()
    mapping_by_fd = {}
    unmatched_mappings = []
    for mapping in mappings:
        if mapping.federal_district_ref_uuid:
            if mapping.federal_district_ref_uuid not in mapping_by_fd:
                mapping_by_fd[mapping.federal_district_ref_uuid] = mapping
        else:
            unmatched_mappings.append(mapping)

    if sort_by in mapping_sort_fields:
        def _sort_key(row):
            mapping = row.mapping
            value = getattr(mapping, sort_by, None) if mapping else None
            if value is None or str(value).strip() == "":
                return (2, "")
            text = str(value).strip()
            if text.isdigit():
                return (0, int(text))
            return (1, text.lower())

        rows = [SimpleNamespace(fd=fd, mapping=mapping_by_fd.get(fd.ref_uuid)) for fd in all_items]
        rows.extend([SimpleNamespace(fd=None, mapping=m) for m in unmatched_mappings])
        rows.sort(key=_sort_key, reverse=(sort_dir == "desc"))
        total = len(rows)
        pagination = Pagination(page=page, per_page=per_page, total=total)
        start = (page - 1) * per_page
        end = start + per_page
        display_rows = rows[start:end]

    return render_template(
        "fuel/refdata/federal_district/federal_district.html",
        form=form,
        federal_district_list=pagination.items if sort_by not in mapping_sort_fields else [],
        pagination=pagination,
        federal_district_filter=federal_district_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        mapping_by_fd=mapping_by_fd,
        unmatched_mappings=unmatched_mappings,
        display_rows=display_rows,
    )


@fuel_bp.route("/refdata/gen_company", methods=["GET"])
@login_required
def fuel_gen_company_list():
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница генерирующих компаний (Топливо)",
        entity_type="gen_company",
    )

    form = GenCompanyFilterForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    gen_company_filter = request.args.get("gen_company_filter", "").strip()

    mapping_sort_fields = {"external_id", "external_name", "external_name1"}
    display_rows = None
    if sort_by in mapping_sort_fields:
        query = gen_company_query(
            gen_company_filter=gen_company_filter,
            sort_by="id",
            sort_dir="asc",
        )
        all_items = query.all()
    else:
        pagination = get_gen_company_list(
            page=page,
            per_page=per_page,
            gen_company_filter=gen_company_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        all_items = pagination.items

    mappings = GenCompanyExternalMapping.query.order_by(
        GenCompanyExternalMapping.id.desc()
    ).all()
    mapping_by_gc = {}
    unmatched_mappings = []
    for mapping in mappings:
        if mapping.gen_company_ref_uuid:
            if mapping.gen_company_ref_uuid not in mapping_by_gc:
                mapping_by_gc[mapping.gen_company_ref_uuid] = mapping
        else:
            unmatched_mappings.append(mapping)

    if sort_by in mapping_sort_fields:
        def _sort_key(row):
            mapping = row.mapping
            value = getattr(mapping, sort_by, None) if mapping else None
            if value is None or str(value).strip() == "":
                return (2, "")
            text = str(value).strip()
            if text.isdigit():
                return (0, int(text))
            return (1, text.lower())

        rows = [SimpleNamespace(gc=gc, mapping=mapping_by_gc.get(gc.ref_uuid)) for gc in all_items]
        rows.extend([SimpleNamespace(gc=None, mapping=m) for m in unmatched_mappings])
        rows.sort(key=_sort_key, reverse=(sort_dir == "desc"))
        total = len(rows)
        pagination = Pagination(page=page, per_page=per_page, total=total)
        start = (page - 1) * per_page
        end = start + per_page
        display_rows = rows[start:end]

    return render_template(
        "fuel/refdata/gen_company/gen_company.html",
        form=form,
        gen_company_list=pagination.items if sort_by not in mapping_sort_fields else [],
        pagination=pagination,
        gen_company_filter=gen_company_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        mapping_by_gc=mapping_by_gc,
        unmatched_mappings=unmatched_mappings,
        display_rows=display_rows,
        import_errors=session.pop("fuel_gen_company_import_errors", None),
    )


@fuel_bp.route("/refdata/equipment_group", methods=["GET"])
@login_required
def fuel_equipment_group_list():
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница типов групп оборудования (Топливо)",
        entity_type="equipment_group",
    )

    form = EquipmentGroupFilterForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    equipment_group_filter = request.args.get("equipment_group_filter", "").strip()

    mapping_sort_fields = {
        "code",
        "name_topl",
        "type_",
        "tm",
        "n1",
        "n2",
        "p1",
        "p2",
        "gruppa_oborud",
    }
    query = equipment_group_query(
        equipment_group_filter=equipment_group_filter,
        technology_type_filter=None,
        technology_availability_filter=None,
        sort_by="id" if sort_by in mapping_sort_fields else sort_by,
        sort_dir="asc" if sort_by in mapping_sort_fields else sort_dir,
    )
    # Загружаем все типы групп оборудования (могут быть несколько версий для одного ref_uuid)
    all_items = query.all()

    # Загружаем все маппинги (возможны несколько версий для одного ref_uuid и code)
    mappings = EquipmentGroupExternalMapping.query.order_by(
        EquipmentGroupExternalMapping.id.desc()
    ).all()
    # Группируем маппинги по ref_uuid, убирая точные дубликаты по (code, ref_uuid)
    mappings_by_eg: dict[str, list[EquipmentGroupExternalMapping]] = {}
    unmatched_mappings = []
    seen_pairs: set[tuple[int, str]] = set()
    for mapping in mappings:
        if mapping.equipment_group_ref_uuid:
            pair = (mapping.code, mapping.equipment_group_ref_uuid)
            if mapping.code is not None and pair in seen_pairs:
                continue
            if mapping.code is not None:
                seen_pairs.add(pair)
            mappings_by_eg.setdefault(mapping.equipment_group_ref_uuid, []).append(mapping)
        else:
            unmatched_mappings.append(mapping)

    def _sort_key(row):
        mapping = row.mapping
        if mapping and sort_by in mapping_sort_fields:
            value = getattr(mapping, sort_by, None)
        else:
            value = getattr(row.eg, sort_by, None) if row.eg else None
        return _sort_text_value(value)

    rows = []
    for eg in all_items:
        eg_mappings = mappings_by_eg.get(eg.ref_uuid) or [None]
        for m in eg_mappings:
            rows.append(SimpleNamespace(eg=eg, mapping=m))
    rows.extend(SimpleNamespace(eg=None, mapping=m) for m in unmatched_mappings)
    rows.sort(key=_sort_key, reverse=(sort_dir == "desc"))
    total = len(rows)
    pagination = Pagination(page=page, per_page=per_page, total=total)
    start = (page - 1) * per_page
    end = start + per_page
    display_rows = rows[start:end]

    return render_template(
        "fuel/refdata/equipment_group/equipment_group.html",
        form=form,
        equipment_group_list=[],
        pagination=pagination,
        equipment_group_filter=equipment_group_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        mapping_by_eg={k: (v[0] if v else None) for k, v in mappings_by_eg.items()},
        unmatched_mappings=unmatched_mappings,
        display_rows=display_rows,
    )


@fuel_bp.route("/refdata/gen_company_branch", methods=["GET"])
@login_required
def fuel_gen_company_branch_list():
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница генерирующих компаний (филиалы) (Топливо)",
        entity_type="gen_company_branch",
    )

    form = GenCompanyFilterForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    gen_company_branch_filter = request.args.get("gen_company_branch_filter", "").strip()

    allowed_sort = {"id", "external_id", "external_name", "local_name"}
    if sort_by not in allowed_sort:
        sort_by = "id"
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"

    query = GenCompanyBranchExternalMapping.query
    if gen_company_branch_filter:
        like_term = f"%{gen_company_branch_filter}%"
        query = query.filter(
            or_(
                GenCompanyBranchExternalMapping.external_id.ilike(like_term),
                GenCompanyBranchExternalMapping.external_name.ilike(like_term),
                GenCompanyBranchExternalMapping.local_name.ilike(like_term),
                GenCompanyBranchExternalMapping.gen_company_ref_uuid.ilike(like_term),
            )
        )

    sort_col = getattr(GenCompanyBranchExternalMapping, sort_by, GenCompanyBranchExternalMapping.id)
    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = pagination.items or []

    # Подтягиваем GenCompany по ref_uuid (текущая версия с учетом фильтрации по версии)
    current_version_id = get_current_db_version_id()
    uuids = {m.gen_company_ref_uuid for m in items if m.gen_company_ref_uuid}
    gc_by_uuid = {}
    if uuids:
        gc_query = GenCompany.query.filter(GenCompany.ref_uuid.in_(list(uuids)))
        gc_query = filter_by_explicit_db_version(gc_query, GenCompany, current_version_id)
        for gc in gc_query.all():
            if gc.ref_uuid and gc.ref_uuid not in gc_by_uuid:
                gc_by_uuid[gc.ref_uuid] = gc

    rows = [SimpleNamespace(mapping=m, gc=gc_by_uuid.get(m.gen_company_ref_uuid)) for m in items]

    return render_template(
        "fuel/refdata/gen_company_branch/gen_company_branch.html",
        form=form,
        rows=rows,
        pagination=pagination,
        gen_company_branch_filter=gen_company_branch_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
    )


@fuel_bp.route("/refdata/department", methods=["GET"])
@login_required
def fuel_department_list():
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница департаментов (Топливо)",
        entity_type="department",
    )

    form = DepartmentFilterForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "external_id")
    sort_dir = request.args.get("sort_dir", "asc")
    department_filter = request.args.get("department_filter", "").strip()

    pagination = get_department_list(
        page=page,
        per_page=per_page,
        department_filter=department_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    return render_template(
        "fuel/refdata/department/department.html",
        form=form,
        mappings=pagination.items,
        pagination=pagination,
        department_filter=department_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
    )


@fuel_bp.route("/refdata/cities", methods=["GET"])
@login_required
def fuel_cities_list():
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница городов (Топливо)",
        entity_type="cities",
    )

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "code")
    sort_dir = request.args.get("sort_dir", "asc")
    cities_filter = request.args.get("cities_filter", "").strip()

    allowed_sort = {
        "id",
        "code",
        "name",
        "naselenie",
        "gilfond",
        "obesp_cts",
        "dprom_ao",
        "dgkh_ao",
        "obl",
    }
    if sort_by not in allowed_sort:
        sort_by = "code"
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"

    query = CitiesExternalMapping.query
    if cities_filter:
        like_term = f"%{cities_filter}%"
        query = query.filter(
            or_(
                func.cast(CitiesExternalMapping.code, db.String).ilike(like_term),
                CitiesExternalMapping.name.ilike(like_term),
                CitiesExternalMapping.obesp_cts.ilike(like_term),
                func.cast(CitiesExternalMapping.dprom_ao, db.String).ilike(like_term),
                func.cast(CitiesExternalMapping.dgkh_ao, db.String).ilike(like_term),
                func.cast(CitiesExternalMapping.obl, db.String).ilike(like_term),
            )
        )

    sort_col = getattr(CitiesExternalMapping, sort_by, CitiesExternalMapping.code)
    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = pagination.items or []

    return render_template(
        "fuel/refdata/cities/cities.html",
        items=items,
        pagination=pagination,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        cities_filter=cities_filter,
    )


@fuel_bp.route("/refdata/business_unit", methods=["GET"])
@login_required
def fuel_business_unit_list():
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница бизнес единиц (Топливо)",
        entity_type="business_unit",
    )

    form = BusinessUnitFilterForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    business_unit_filter = request.args.get("business_unit_filter", "").strip()

    pagination = get_business_unit_list(
        page=page,
        per_page=per_page,
        business_unit_filter=business_unit_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    return render_template(
        "fuel/refdata/business_unit/business_unit.html",
        form=form,
        business_unit_list=pagination.items,
        pagination=pagination,
        business_unit_filter=business_unit_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
    )


@fuel_bp.route("/refdata/economic_region", methods=["GET"])
@login_required
def fuel_economic_region_list():
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница экономических районов (Топливо)",
        entity_type="economic_region",
    )

    form = EconomicRegionFilterForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    economic_region_filter = request.args.get("economic_region_filter", "").strip()

    pagination = get_economic_region_list(
        page=page,
        per_page=per_page,
        economic_region_filter=economic_region_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    return render_template(
        "fuel/refdata/economic_region/economic_region.html",
        form=form,
        economic_region_list=pagination.items,
        pagination=pagination,
        economic_region_filter=economic_region_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
    )


@fuel_bp.route("/refdata/union_energy_system/import", methods=["POST"])
@login_required
def import_fuel_union_energy_system_mappings():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.fuel_union_energy_system_list"))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_union_energy_system_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_union_energy_system_list"))

    try:
        result = import_union_energy_system_mappings_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        if result.get("errors"):
            for error in result["errors"][:5]:
                flash(error, "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error(f"Ошибка импорта сопоставлений ОЭС: {exc}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("fuel_bp.fuel_union_energy_system_list"))


@fuel_bp.route("/refdata/federal_district/import", methods=["POST"])
@login_required
def import_fuel_federal_district_mappings():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.fuel_federal_district_list"))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_federal_district_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_federal_district_list"))

    try:
        result = import_federal_district_mappings_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        if result.get("errors"):
            for error in result["errors"][:5]:
                flash(error, "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error(f"Ошибка импорта сопоставлений ФО: {exc}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("fuel_bp.fuel_federal_district_list"))


@fuel_bp.route("/refdata/gen_company/import", methods=["POST"])
@login_required
def import_fuel_gen_company_mappings():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.fuel_gen_company_list"))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_gen_company_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_gen_company_list"))

    try:
        result = import_gen_company_mappings_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        if result.get("errors") or result.get("saved_unmatched"):
            for msg in (result.get("all_messages") or result.get("errors") or [])[:5]:
                flash(msg, "warning")
            session["fuel_gen_company_import_errors"] = result.get("all_messages") or result.get("errors") or []
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error(f"Ошибка импорта сопоставлений генерирующих компаний: {exc}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("fuel_bp.fuel_gen_company_list"))


@fuel_bp.route("/refdata/equipment_group/import", methods=["POST"])
@login_required
def import_fuel_equipment_group_mappings():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.fuel_equipment_group_list"))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_equipment_group_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_equipment_group_list"))

    try:
        result = import_equipment_group_mappings_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        if result.get("errors"):
            for error in result["errors"][:5]:
                flash(error, "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error(
            f"Ошибка импорта сопоставлений типов групп оборудования: {exc}"
        )
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("fuel_bp.fuel_equipment_group_list"))


@fuel_bp.route("/refdata/equipment_group/export", methods=["GET"])
@login_required
def export_fuel_equipment_group():
    user = session.get("username", "Неизвестный пользователь")

    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    equipment_group_filter = request.args.get("equipment_group_filter", "").strip()

    try:
        excel_data = export_equipment_group_mappings_service(
            user=user,
            equipment_group_filter=equipment_group_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("fuel_bp.fuel_equipment_group_list"))

        filename = (
            f"equipment_group_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        return send_file(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.error(
            f"Ошибка экспорта сопоставлений типов групп оборудования: {exc}"
        )
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("fuel_bp.fuel_equipment_group_list"))


@fuel_bp.route("/refdata/gen_company_branch/import", methods=["POST"])
@login_required
def import_fuel_gen_company_branch_mappings():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.fuel_gen_company_branch_list"))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_gen_company_branch_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_gen_company_branch_list"))

    try:
        result = import_gen_company_branch_mappings_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        if result.get("errors"):
            for error in result["errors"][:5]:
                flash(error, "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error(
            f"Ошибка импорта сопоставлений генерирующих компаний (филиалы): {exc}"
        )
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("fuel_bp.fuel_gen_company_branch_list"))


@fuel_bp.route("/refdata/department/import", methods=["POST"])
@login_required
def import_fuel_department_mappings():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.fuel_department_list"))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_department_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_department_list"))

    try:
        result = import_department_mappings_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        if result.get("errors"):
            for error in result["errors"][:5]:
                flash(error, "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error(f"Ошибка импорта сопоставлений департаментов: {exc}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("fuel_bp.fuel_department_list"))


@fuel_bp.route("/refdata/cities/import", methods=["POST"])
@login_required
def import_fuel_cities():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.fuel_cities_list"))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_cities_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_cities_list"))

    try:
        result = import_cities_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        if result.get("errors"):
            for error in result["errors"][:5]:
                flash(error, "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error(f"Ошибка импорта городов: {exc}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("fuel_bp.fuel_cities_list"))


@fuel_bp.route("/refdata/business_unit/import", methods=["POST"])
@login_required
def import_fuel_business_unit_mappings():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.fuel_business_unit_list"))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_business_unit_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_business_unit_list"))

    try:
        result = import_business_unit_mappings_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        if result.get("errors"):
            for error in result["errors"][:5]:
                flash(error, "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error(f"Ошибка импорта сопоставлений бизнес единиц: {exc}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("fuel_bp.fuel_business_unit_list"))


@fuel_bp.route("/refdata/economic_region/import", methods=["POST"])
@login_required
def import_fuel_economic_region_mappings():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.fuel_economic_region_list"))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_economic_region_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_economic_region_list"))

    try:
        result = import_economic_region_mappings_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        if result.get("errors"):
            for error in result["errors"][:5]:
                flash(error, "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error(f"Ошибка импорта сопоставлений экономических районов: {exc}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("fuel_bp.fuel_economic_region_list"))


@fuel_bp.route("/refdata/territories_energy/import", methods=["POST"])
@login_required
def import_fuel_territories_energy():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.fuel_territories_energy_list"))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_territories_energy_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.fuel_territories_energy_list"))

    try:
        result = import_territories_energy_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        if result.get("errors"):
            for error in result["errors"][:5]:
                flash(error, "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error(f"Ошибка импорта территорий/энергосистем: {exc}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("fuel_bp.fuel_territories_energy_list"))




@fuel_bp.route("/refdata/union_energy_system/export", methods=["GET"])
@login_required
def export_fuel_union_energy_system():
    user = session.get("username", "Неизвестный пользователь")

    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    union_energy_system_filter = request.args.get("union_energy_system_filter", "").strip()
    energy_system_type_filter = request.args.get("energy_system_type_filter", "").strip()

    try:
        excel_data = export_union_energy_system_service(
            user=user,
            union_energy_system_filter=union_energy_system_filter,
            energy_system_type_filter=energy_system_type_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("fuel_bp.fuel_union_energy_system_list"))

        filename = (
            f"union_energy_system_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        return send_file(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.error(f"Ошибка экспорта: {exc}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("fuel_bp.fuel_union_energy_system_list"))


@fuel_bp.route("/refdata/federal_district/export", methods=["GET"])
@login_required
def export_fuel_federal_district():
    user = session.get("username", "Неизвестный пользователь")

    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    federal_district_filter = request.args.get("federal_district_filter", "").strip()

    try:
        excel_data = export_federal_district_mappings_service(
            user=user,
            federal_district_filter=federal_district_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("fuel_bp.fuel_federal_district_list"))

        filename = (
            f"federal_district_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        return send_file(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.error(f"Ошибка экспорта ФО: {exc}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("fuel_bp.fuel_federal_district_list"))


@fuel_bp.route("/refdata/gen_company/export", methods=["GET"])
@login_required
def export_fuel_gen_company():
    user = session.get("username", "Неизвестный пользователь")

    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    gen_company_filter = request.args.get("gen_company_filter", "").strip()

    try:
        excel_data = export_gen_company_mappings_service(
            user=user,
            gen_company_filter=gen_company_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("fuel_bp.fuel_gen_company_list"))

        filename = (
            f"gen_company_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        return send_file(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.error(
            f"Ошибка экспорта сопоставлений генерирующих компаний: {exc}"
        )
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("fuel_bp.fuel_gen_company_list"))


@fuel_bp.route("/refdata/gen_company_branch/export", methods=["GET"])
@login_required
def export_fuel_gen_company_branch():
    user = session.get("username", "Неизвестный пользователь")

    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    gen_company_branch_filter = request.args.get("gen_company_branch_filter", "").strip()

    allowed_sort = {"id", "external_id", "external_name", "local_name"}
    if sort_by not in allowed_sort:
        sort_by = "id"
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"

    query = GenCompanyBranchExternalMapping.query
    if gen_company_branch_filter:
        like_term = f"%{gen_company_branch_filter}%"
        query = query.filter(
            or_(
                GenCompanyBranchExternalMapping.external_id.ilike(like_term),
                GenCompanyBranchExternalMapping.external_name.ilike(like_term),
                GenCompanyBranchExternalMapping.local_name.ilike(like_term),
                GenCompanyBranchExternalMapping.gen_company_ref_uuid.ilike(like_term),
            )
        )

    sort_col = getattr(GenCompanyBranchExternalMapping, sort_by, GenCompanyBranchExternalMapping.id)
    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    items = query.all()

    current_version_id = get_current_db_version_id()
    uuids = {m.gen_company_ref_uuid for m in items if m.gen_company_ref_uuid}
    gc_by_uuid = {}
    if uuids:
        gc_query = GenCompany.query.filter(GenCompany.ref_uuid.in_(list(uuids)))
        gc_query = filter_by_explicit_db_version(gc_query, GenCompany, current_version_id)
        for gc in gc_query.all():
            if gc.ref_uuid and gc.ref_uuid not in gc_by_uuid:
                gc_by_uuid[gc.ref_uuid] = gc

    data = []
    for m in items:
        gc = gc_by_uuid.get(m.gen_company_ref_uuid)
        data.append(
            {
                "Номер (code)": m.external_id or "",
                "Наименование (name)": m.external_name or "",
                "UUID": gc.ref_uuid if gc else "",
                "ID (текущая версия)": gc.id if gc else "",
                "Наименование": gc.name if gc else "",
            }
        )

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="GenCompanyBranch")
    output.seek(0)

    log_to_db(
        user,
        "Выгрузка сопоставлений генерирующих компаний (филиалы) в Excel",
        entity_type="gen_company_branch",
    )
    return send_file(
        output,
        as_attachment=True,
        download_name="gen_company_branch.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@fuel_bp.route("/refdata/department/export", methods=["GET"])
@login_required
def export_fuel_department():
    user = session.get("username", "Неизвестный пользователь")

    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    department_filter = request.args.get("department_filter", "").strip()

    try:
        excel_data = export_department_mappings_service(
            user=user,
            department_filter=department_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("fuel_bp.fuel_department_list"))

        filename = (
            f"department_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        return send_file(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.error(f"Ошибка экспорта департаментов: {exc}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("fuel_bp.fuel_department_list"))


@fuel_bp.route("/refdata/cities/export", methods=["GET"])
@login_required
def export_fuel_cities():
    user = session.get("username", "Неизвестный пользователь")
    cities_filter = request.args.get("cities_filter", "").strip()
    sort_by = request.args.get("sort_by", "code")
    sort_dir = request.args.get("sort_dir", "asc")

    allowed_sort = {
        "id",
        "code",
        "name",
        "naselenie",
        "gilfond",
        "obesp_cts",
        "dprom_ao",
        "dgkh_ao",
        "obl",
    }
    if sort_by not in allowed_sort:
        sort_by = "code"
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"

    query = CitiesExternalMapping.query
    if cities_filter:
        like_term = f"%{cities_filter}%"
        query = query.filter(
            or_(
                func.cast(CitiesExternalMapping.code, db.String).ilike(like_term),
                CitiesExternalMapping.name.ilike(like_term),
                CitiesExternalMapping.obesp_cts.ilike(like_term),
                func.cast(CitiesExternalMapping.dprom_ao, db.String).ilike(like_term),
                func.cast(CitiesExternalMapping.dgkh_ao, db.String).ilike(like_term),
                func.cast(CitiesExternalMapping.obl, db.String).ilike(like_term),
            )
        )

    sort_col = getattr(CitiesExternalMapping, sort_by, CitiesExternalMapping.code)
    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    rows = query.all()

    data = []
    for row in rows:
        obl_val = row.territories_energy.external_name if row.territories_energy else (row.obl if row.obl is not None else "")
        data.append(
            {
                "Номер (code)": row.code if row.code is not None else "",
                "Наименование (name)": row.name or "",
                "Население (naselenie)": float(row.naselenie) if row.naselenie is not None else None,
                "Жилфонд (gilfond)": float(row.gilfond) if row.gilfond is not None else None,
                "Обесп. ЦТС (obesp_cts)": row.obesp_cts or "",
                "ПРОМ, АО (dprom_ao)": row.dprom_ao if row.dprom_ao is not None else "",
                "ЖКХ, АО (dgkh_ao)": row.dgkh_ao if row.dgkh_ao is not None else "",
                "Обл (obl)": obl_val,
            }
        )

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cities")
    output.seek(0)

    log_to_db(user, "Выгрузка справочника городов в Excel", entity_type="cities")
    return send_file(
        output,
        as_attachment=True,
        download_name="cities.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@fuel_bp.route("/refdata/business_unit/export", methods=["GET"])
@login_required
def export_fuel_business_unit():
    user = session.get("username", "Неизвестный пользователь")

    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    business_unit_filter = request.args.get("business_unit_filter", "").strip()

    try:
        excel_data = export_business_unit_mappings_service(
            user=user,
            business_unit_filter=business_unit_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("fuel_bp.fuel_business_unit_list"))

        filename = (
            f"business_unit_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        return send_file(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.error(f"Ошибка экспорта бизнес единиц: {exc}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("fuel_bp.fuel_business_unit_list"))


@fuel_bp.route("/refdata/economic_region/export", methods=["GET"])
@login_required
def export_fuel_economic_region():
    user = session.get("username", "Неизвестный пользователь")

    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    economic_region_filter = request.args.get("economic_region_filter", "").strip()

    try:
        excel_data = export_economic_region_mappings_service(
            user=user,
            economic_region_filter=economic_region_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("fuel_bp.fuel_economic_region_list"))

        filename = (
            f"economic_region_mappings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        return send_file(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.error(f"Ошибка экспорта экономических районов: {exc}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("fuel_bp.fuel_economic_region_list"))


@fuel_bp.route("/stations_equipment_groups", methods=["GET", "POST"])
@login_required
def stations_equipment_groups():
    form = StationFilterForm()

    if request.method == "POST":
        return redirect(url_for("fuel_bp.stations_equipment_groups", **extract_filters_from_form(request.form)))

    filters = extract_filters_from_args(request.args)
    page = filters.pop("page", 1)
    start_year = filters.pop("start_year", get_filter_start_year())
    end_year = filters.pop("end_year", get_filter_end_year())
    show_p_ogr = request.args.get("show_p_ogr", "0") == "1"
    show_p_rasp = request.args.get("show_p_rasp", "1") == "1"
    show_totals = request.args.get("show_totals", "0") == "1"
    per_page_param = request.args.get("per_page", "10")

    show_all = per_page_param.lower() == "all"
    if show_all:
        per_page = "all"
    else:
        try:
            per_page = int(per_page_param)
        except ValueError:
            per_page = 10

    try:
        rounding_digits = int(request.args.get("rounding_digits"))
    except (ValueError, TypeError):
        rounding_digits = 1

    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1

    data = get_station_list_data(
        filters=filters,
        per_page=per_page,
        page=page,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        show_p_ogr=show_p_ogr,
        show_p_rasp=show_p_rasp,
        show_all=show_all,
        show_totals=show_totals,
    )

    if (not data.get("stations")) and data.get("total_count", 0) > 0 and page > 1:
        target_page = data.get("total_pages") or 1
        if target_page >= page:
            target_page = max(1, page - 1)
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = {}
        for key, values in args_multi.items():
            if not values:
                continue
            if len(values) == 1:
                redirect_args[key] = values[0]
            else:
                redirect_args[key] = values
        return redirect(url_for("fuel_bp.stations_equipment_groups", **redirect_args))

    try:
        export_key = build_export_key(
            {**filters},
            rounding_digits,
            start_year,
            end_year,
            show_p_ogr,
            show_p_rasp,
        )
        export_payload = {
            "data": data,
            "params": {
                "rounding_digits": rounding_digits,
                "start_year": start_year,
                "end_year": end_year,
                "show_p_ogr": show_p_ogr,
                "show_p_rasp": show_p_rasp,
            },
        }
        set_export_payload(session.get("username") or "anonymous", export_key, export_payload)
    except Exception as exc:
        current_app.logger.warning(f"[EXPORT_CACHE] Failed to store export payload: {exc}")

    if data["page"] > data["total_pages"]:
        return redirect(url_for("fuel_bp.stations_equipment_groups", page=data["total_pages"], per_page=per_page))

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year},
        show_all=show_all,
        hierarchy_data=data.get("hierarchy_data"),
    )

    has_active_filters = has_any_filters(request.args)

    return render_template(
        "fuel/stations_equipment_groups.html",
        has_active_filters=has_active_filters,
        **context,
    )


@fuel_bp.route("/stations_equipment_groups/equipment_group_details/<int:equipment_group_set_station_id>", methods=["GET"])
@login_required
def equipment_group_details(equipment_group_set_station_id):
    """Карточка группы оборудования — топливные параметры EquipmentGroupFuelParam по годам (Год начала...Год конца)."""
    from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
    from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam

    link = EquipmentGroupSetStation.query.filter_by(id=equipment_group_set_station_id).first()
    if not link:
        abort(404, description="Связь группа-станция не найдена")

    station = link.station
    equipment_group_set = link.equipment_group_set

    # Год начала / Год конца (как на machine_details)
    start_year = request.args.get("start_year", get_filter_start_year(), type=int)
    end_year = request.args.get("end_year", get_filter_end_year(), type=int)
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    # Словарь параметров по годам: year_number -> EquipmentGroupFuelParam
    params_by_year = {tp.year_number: tp for tp in link.fuel_params}
    years_range = list(range(start_year, end_year + 1))
    fuel_params_by_year = {y: params_by_year.get(y) for y in years_range}

    # Сетки для таблиц: [(label, {year: value}), ...]
    def _val(tp, attr):
        return getattr(tp, attr, None) if tp else None

    main_attrs = [
        ("OBOR", "obor"), ("VED", "ved"), ("вед", "ved_cyrillic"), ("OBL", "obl"),
        ("DEP", "dep"), ("OES", "oes"), ("EES", "ees"), ("ER", "er"),
        ("GK", "gk"), ("BE", "be"), ("NUMB1120", "numb1120"), ("numb1", "numb1"),
    ]
    table1_attrs = [
        ("NUST", "nust"), ("nr", "nr"), ("E", "e"), ("EOTP", "eotp"), ("EURT", "eurt"),
        ("EUST", "eust"), ("Q", "q"), ("TURT", "turt"), ("TUST", "tust"),
    ]
    table2_attrs = [
        ("B", "b"), ("GAZ", "gaz"), ("ISK_GAZ", "isk_gaz"), ("MAZUT", "mazut"), ("TORF", "torf"),
        ("SLAN", "slan"), ("PROCH", "proch"), ("UGOL", "ugol"), ("DON", "don"), ("PODM", "podm"),
        ("PECH", "pech"), ("ARKT", "arkt"), ("KUZN", "kuzn"), ("URAL", "ural"), ("BASHK", "bashk"),
        ("KAZAH", "kazah"), ("KAN", "kan"), ("TUNG", "tung"), ("IRKUT", "irkut"), ("HAK", "hak"),
        ("TUV", "tuv"), ("BUR", "bur"), ("CHIT", "chit"), ("YAKUT", "yakut"), ("AMUR", "amur"),
        ("URG", "urg"), ("USHUM", "ushum"), ("PRIM", "prim"), ("MAG", "mag"), ("CHUKOT", "chukot"),
        ("KAMCH", "kamch"), ("SAH", "sah"), ("QOTR", "qotr"), ("SNK", "snk"), ("SNt", "sn_t"),
        ("EWTP", "ewtp"), ("NT", "nt"), ("NTsum", "nt_sum"),
    ]

    def _build_grid(attrs):
        return [
            (label, {y: _val(params_by_year.get(y), attr) for y in years_range})
            for label, attr in attrs
        ]

    main_params_grid = _build_grid(main_attrs)
    table1_params_grid = _build_grid(table1_attrs)
    table2_params_grid = _build_grid(table2_attrs)

    _, version_year_end = get_current_version_year_range_from_name()

    group_display_name = (
        equipment_group_set.name if equipment_group_set and equipment_group_set.name
        else (equipment_group_set.equipment_group.name if equipment_group_set and equipment_group_set.equipment_group else "—")
    )

    return render_template(
        "fuel/equipment_group_details.html",
        link=link,
        station=station,
        equipment_group_set=equipment_group_set,
        fuel_params_by_year=fuel_params_by_year,
        main_params_grid=main_params_grid,
        table1_params_grid=table1_params_grid,
        table2_params_grid=table2_params_grid,
        start_year=start_year,
        end_year=end_year,
        version_year_end=version_year_end,
        group_display_name=group_display_name,
    )


@fuel_bp.route("/stations_equipment_groups/export", methods=["GET"])
@login_required
def export_stations_equipment_groups():
    """Экспорт данных stations_equipment_groups в Excel с id станций и агрегатов."""
    try:
        filters = extract_filters_from_args(request.args)
        start_year = int(request.args.get("start_year", get_filter_start_year()))
        end_year = int(request.args.get("end_year", get_filter_end_year()))

        excel_file = export_stations_equipment_groups_to_excel(filters, start_year, end_year)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Группы_оборудования_электростанций_{timestamp}.xlsx"

        excel_file.seek(0)
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта stations_equipment_groups: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash(f"Ошибка экспорта данных: {str(e)}", "danger")
        return redirect(url_for("fuel_bp.stations_equipment_groups", **request.args.to_dict()))


def _get_import_report_dir():
    """Директория для временных отчётов импорта (по аналогии со справочниками)."""
    base = current_app.config.get("UPLOAD_FOLDER", "uploads")
    report_dir = os.path.join(base, "import_reports")
    os.makedirs(report_dir, exist_ok=True)
    return report_dir


def _get_import_fuel_db_redirect_args():
    """Аргументы для редиректа после импорта БД Топливо. redirect_to — endpoint (stations_turbines, stations_equipment_groups, fuel_params)."""
    redirect_to = request.form.get("redirect_to")
    exclude = ("file", "csrf_token", "redirect_to")
    if redirect_to == "stations_equipment_group_fuel_params":
        args = {k: v for k, v in request.form.items() if k not in exclude}
        return "fuel_bp.stations_equipment_group_fuel_params", args
    if redirect_to in ("fuel_bp.stations_turbines", "fuel_bp.stations_equipment_groups"):
        args = {k: v for k, v in request.form.items() if k not in exclude}
        return redirect_to, args
    args = request.args.to_dict() if request.args else request.form.to_dict(flat=True)
    for k in exclude:
        args.pop(k, None)
    return "fuel_bp.stations_equipment_groups", args


@fuel_bp.route("/stations_turbines/import_fuel_db", methods=["POST"])
@login_required
def import_fuel_db_turbines():
    """Загрузка данных БД Топливо на странице «Турбины»: тот же сервис, что и для groups, редирект на stations_turbines."""
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(user, "Начата загрузка данных БД Топливо (турбины)")
    current_app.logger.info(
        "[IMPORT_FUEL_DB_TURBINES] start user=%s filename=%s mimetype=%s remote_addr=%s",
        user,
        getattr(request.files.get("file"), "filename", None),
        getattr(request.files.get("file"), "mimetype", None),
        request.remote_addr,
    )

    redirect_args = {k: v for k, v in request.form.items() if k not in ("file", "csrf_token", "redirect_to")}

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.stations_turbines", **redirect_args))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.stations_turbines", **redirect_args))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.stations_turbines", **redirect_args))

    try:
        result = import_fuel_db_equipment_groups_from_excel(file, user, build_report=False)
        flash(result["message"], "success")
        clear_station_aggregation_cache("после импорта БД Топливо")
        current_app.logger.info(
            "[IMPORT_FUEL_DB_TURBINES] done user=%s filename=%s processed=%s updated=%s errors=%s",
            user,
            getattr(file, "filename", None),
            result.get("processed_rows"),
            result.get("updated_machines"),
            result.get("errors_count"),
        )
    except ValueError as e:
        current_app.logger.warning(
            "[IMPORT_FUEL_DB_TURBINES] validation error user=%s filename=%s: %s",
            user,
            getattr(file, "filename", None),
            str(e),
            exc_info=True,
        )
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.exception(
            "[IMPORT_FUEL_DB_TURBINES] import failed user=%s filename=%s",
            user,
            getattr(file, "filename", None),
        )
        flash("Ошибка загрузки данных БД Топливо.", "danger")

    return redirect(url_for("fuel_bp.stations_turbines", **redirect_args))


@fuel_bp.route("/stations_equipment_groups/import_report/<token>", methods=["GET"])
@login_required
def import_fuel_db_report_download(token):
    """Маршрут больше не используется (выгрузка отчёта отключена)."""
    flash("Выгрузка отчёта с результатами импорта отключена.", "warning")
    return redirect(url_for("fuel_bp.stations_equipment_groups"))


@fuel_bp.route("/stations_equipment_groups/import_fuel_db", methods=["POST"])
@login_required
def import_fuel_db_equipment_groups():
    """Загрузка данных БД Топливо: привязка групп оборудования к агрегатам по external_code."""
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(user, "Начата загрузка данных БД Топливо")
    current_app.logger.info(
        "[IMPORT_FUEL_DB_ROUTE] start user=%s filename=%s mimetype=%s remote_addr=%s",
        user,
        getattr(request.files.get("file"), "filename", None),
        getattr(request.files.get("file"), "mimetype", None),
        request.remote_addr,
    )

    redirect_endpoint, redirect_args = _get_import_fuel_db_redirect_args()

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for(redirect_endpoint, **redirect_args))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for(redirect_endpoint, **redirect_args))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for(redirect_endpoint, **redirect_args))

    try:
        result = import_fuel_db_equipment_groups_from_excel(file, user, build_report=False)
        flash(result["message"], "success")
        clear_station_aggregation_cache("после импорта БД Топливо")
        current_app.logger.info(
            "[IMPORT_FUEL_DB_ROUTE] done user=%s filename=%s processed=%s updated=%s errors=%s",
            user,
            getattr(file, "filename", None),
            result.get("processed_rows"),
            result.get("updated_machines"),
            result.get("errors_count"),
        )
    except ValueError as e:
        current_app.logger.warning(
            "[IMPORT_FUEL_DB_ROUTE] validation error user=%s filename=%s: %s",
            user,
            getattr(file, "filename", None),
            str(e),
            exc_info=True,
        )
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.exception(
            "[IMPORT_FUEL_DB_ROUTE] import failed user=%s filename=%s",
            user,
            getattr(file, "filename", None),
        )
        flash("Ошибка загрузки данных БД Топливо.", "danger")

    return redirect(url_for(redirect_endpoint, **redirect_args))


@fuel_bp.route("/stations_turbines", methods=["GET", "POST"])
@login_required
def stations_turbines():
    """Страница «Турбины электростанций» — копия groups с полями MachineFuelParam после «Тип агрегата»."""
    form = StationFilterForm()

    if request.method == "POST":
        return redirect(url_for("fuel_bp.stations_turbines", **extract_filters_from_form(request.form)))

    filters = extract_filters_from_args(request.args)
    page = filters.pop("page", 1)
    year_param = request.args.get("year", type=int)
    selected_year = year_param if year_param is not None else get_filter_start_year()
    start_year = end_year = selected_year
    filters["start_year"] = start_year
    filters["end_year"] = end_year
    show_p_ogr = request.args.get("show_p_ogr", "0") == "1"
    show_p_rasp = request.args.get("show_p_rasp", "1") == "1"
    show_totals = request.args.get("show_totals", "0") == "1"
    per_page_param = request.args.get("per_page", "10")

    show_all = per_page_param.lower() == "all"
    if show_all:
        per_page = "all"
    else:
        try:
            per_page = int(per_page_param)
        except ValueError:
            per_page = 10

    try:
        rounding_digits = int(request.args.get("rounding_digits"))
    except (ValueError, TypeError):
        rounding_digits = 1

    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1

    data = get_station_list_data(
        filters=filters,
        per_page=per_page,
        page=page,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        show_p_ogr=show_p_ogr,
        show_p_rasp=show_p_rasp,
        show_all=show_all,
        show_totals=show_totals,
    )

    if (not data.get("stations")) and data.get("total_count", 0) > 0 and page > 1:
        target_page = data.get("total_pages") or 1
        if target_page >= page:
            target_page = max(1, page - 1)
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = {}
        for key, values in args_multi.items():
            if not values:
                continue
            if len(values) == 1:
                redirect_args[key] = values[0]
            else:
                redirect_args[key] = values
        return redirect(url_for("fuel_bp.stations_turbines", **redirect_args))

    try:
        export_key = build_export_key(
            {**filters},
            rounding_digits,
            start_year,
            end_year,
            show_p_ogr,
            show_p_rasp,
        )
        export_payload = {
            "data": data,
            "params": {
                "rounding_digits": rounding_digits,
                "start_year": start_year,
                "end_year": end_year,
                "show_p_ogr": show_p_ogr,
                "show_p_rasp": show_p_rasp,
            },
        }
        set_export_payload(session.get("username") or "anonymous", export_key, export_payload)
    except Exception as exc:
        current_app.logger.warning(f"[EXPORT_CACHE] Failed to store export payload: {exc}")

    if data["page"] > data["total_pages"]:
        redirect_args = {**request.args.to_dict(flat=True), "page": data["total_pages"], "per_page": per_page}
        redirect_args["year"] = selected_year
        return redirect(url_for("fuel_bp.stations_turbines", **redirect_args))

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year},
        show_all=show_all,
        hierarchy_data=data.get("hierarchy_data"),
    )

    has_active_filters = has_any_filters(request.args)

    return render_template(
        "fuel/stations_turbines.html",
        has_active_filters=has_active_filters,
        selected_year=selected_year,
        **context,
    )


@fuel_bp.route("/stations_equipment_group_toplivo_params", methods=["GET"])
def stations_equipment_group_toplivo_params_redirect():
    """Редирект для обратной совместимости (старый URL -> stations_equipment_group_fuel_params)."""
    return redirect(url_for("fuel_bp.stations_equipment_group_fuel_params", **request.args.to_dict()))


@fuel_bp.route("/stations_equipment_group_extra_fuel_params", methods=["GET", "POST"])
@login_required
def stations_equipment_group_extra_fuel_params():
    """Страница «Топливные параметры групп оборудования (дополнительные)»."""
    form = StationFilterForm()

    if request.method == "POST":
        redirect_args = extract_filters_from_form(request.form)
        rd = request.form.get("rounding_digits", type=int)
        if rd is not None:
            redirect_args["rounding_digits"] = rd
        return redirect(
            url_for(
                "fuel_bp.stations_equipment_group_extra_fuel_params",
                **redirect_args,
            )
        )

    filters = extract_filters_from_args(request.args)
    page = filters.pop("page", 1)
    year_param = request.args.get("year", type=int)
    selected_year = year_param if year_param is not None else get_filter_start_year()
    start_year = end_year = selected_year
    filters["start_year"] = start_year
    filters["end_year"] = end_year
    per_page_param = request.args.get("per_page", "10")

    show_all = per_page_param.lower() == "all"
    if show_all:
        per_page = "all"
    else:
        try:
            per_page = int(per_page_param)
        except ValueError:
            per_page = 10

    rounding_digits = request.args.get("rounding_digits", default=1, type=int)
    if rounding_digits is None or rounding_digits < -1 or rounding_digits > 6:
        rounding_digits = 1

    data = get_station_list_data(
        filters=filters,
        per_page=per_page,
        page=page,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        show_p_ogr=False,
        show_p_rasp=False,
        show_all=show_all,
        show_totals=False,
    )

    load_equipment_group_extra_fuel_params_for_stations(data.get("stations") or [])

    if (not data.get("stations")) and data.get("total_count", 0) > 0 and page > 1:
        target_page = data.get("total_pages") or 1
        if target_page >= page:
            target_page = max(1, page - 1)
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = {}
        for key, values in args_multi.items():
            if not values:
                continue
            if len(values) == 1:
                redirect_args[key] = values[0]
            else:
                redirect_args[key] = values
        return redirect(
            url_for("fuel_bp.stations_equipment_group_extra_fuel_params", **redirect_args)
        )

    if data["page"] > data["total_pages"]:
        redirect_args = request.args.to_dict(flat=True)
        redirect_args["page"] = data["total_pages"]
        redirect_args["per_page"] = per_page
        return redirect(
            url_for("fuel_bp.stations_equipment_group_extra_fuel_params", **redirect_args)
        )

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year},
        show_all=show_all,
        hierarchy_data=data.get("hierarchy_data"),
    )

    has_active_filters = has_any_filters(request.args)

    return render_template(
        "fuel/stations_equipment_group_extra_fuel_params.html",
        has_active_filters=has_active_filters,
        selected_year=selected_year,
        **context,
    )


@fuel_bp.route("/stations_equipment_group_fuel_params", methods=["GET", "POST"])
@login_required
def stations_equipment_group_fuel_params():
    """Страница «Топливные параметры групп оборудования» — Группа оборудования + поля EquipmentGroupFuelParam."""
    form = StationFilterForm()

    if request.method == "POST":
        redirect_args = extract_filters_from_form(request.form)
        rd = request.form.get("rounding_digits", type=int)
        if rd is not None:
            redirect_args["rounding_digits"] = rd
        return redirect(
            url_for(
                "fuel_bp.stations_equipment_group_fuel_params",
                **redirect_args,
            )
        )

    filters = extract_filters_from_args(request.args)
    page = filters.pop("page", 1)
    year_param = request.args.get("year", type=int)
    selected_year = year_param if year_param is not None else get_filter_start_year()
    start_year = end_year = selected_year
    filters["start_year"] = start_year
    filters["end_year"] = end_year
    per_page_param = request.args.get("per_page", "10")

    show_all = per_page_param.lower() == "all"
    if show_all:
        per_page = "all"
    else:
        try:
            per_page = int(per_page_param)
        except ValueError:
            per_page = 10

    rounding_digits = request.args.get("rounding_digits", default=1, type=int)
    if rounding_digits is None or rounding_digits < -1 or rounding_digits > 6:
        rounding_digits = 1

    data = get_station_list_data(
        filters=filters,
        per_page=per_page,
        page=page,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        show_p_ogr=False,
        show_p_rasp=False,
        show_all=show_all,
        show_totals=False,
    )

    load_equipment_group_fuel_params_for_stations(data.get("stations") or [])

    if (not data.get("stations")) and data.get("total_count", 0) > 0 and page > 1:
        target_page = data.get("total_pages") or 1
        if target_page >= page:
            target_page = max(1, page - 1)
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = {}
        for key, values in args_multi.items():
            if not values:
                continue
            if len(values) == 1:
                redirect_args[key] = values[0]
            else:
                redirect_args[key] = values
        return redirect(
            url_for("fuel_bp.stations_equipment_group_fuel_params", **redirect_args)
        )

    if data["page"] > data["total_pages"]:
        redirect_args = request.args.to_dict(flat=True)
        redirect_args["page"] = data["total_pages"]
        redirect_args["per_page"] = per_page
        return redirect(
            url_for("fuel_bp.stations_equipment_group_fuel_params", **redirect_args)
        )

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year},
        show_all=show_all,
        hierarchy_data=data.get("hierarchy_data"),
    )

    stations = data.get("stations") or []
    context["obor_name_map"] = build_obor_name_map(stations)
    context["obl_name_map"] = build_obl_name_map(stations)
    context["dep_name_map"] = build_dep_name_map(stations)
    context["oes_name_map"] = build_oes_name_map(stations)
    context["er_name_map"] = build_er_name_map(stations)
    context["gk_name_map"] = build_gk_name_map(stations)
    context["be_name_map"] = build_be_name_map(stations)

    has_active_filters = has_any_filters(request.args)

    return render_template(
        "fuel/stations_equipment_group_fuel_params.html",
        has_active_filters=has_active_filters,
        selected_year=selected_year,
        **context,
    )


@fuel_bp.route("/stations_equipment_group_fuel_params/import_fuel_db", methods=["POST"])
@login_required
def import_equipment_group_fuel_params():
    """Загрузка данных в EquipmentGroupFuelParam из Excel. Связь по NUMB1120 = EquipmentGroupSet.numb."""
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(user, "Начата загрузка EquipmentGroupFuelParam из БД Топливо")
    current_app.logger.info(
        "[IMPORT_EQUIPMENT_GROUP_TOPLIVO_PARAMS_ROUTE] start user=%s filename=%s",
        user,
        getattr(request.files.get("file"), "filename", None),
    )

    year_param = request.form.get("year") or request.args.get("year", type=int)
    if year_param is None:
        flash("Не указан год. Выберите год в выпадающем списке на странице.", "danger")
        return redirect(url_for("fuel_bp.stations_equipment_group_fuel_params", **request.args.to_dict(flat=True)))
    try:
        year = int(year_param)
    except (ValueError, TypeError):
        flash("Некорректное значение года.", "danger")
        return redirect(url_for("fuel_bp.stations_equipment_group_fuel_params", **request.args.to_dict()))

    redirect_base = request.form.to_dict(flat=True) if request.form else request.args.to_dict(flat=True)
    redirect_base.pop("file", None)
    redirect_base.pop("csrf_token", None)

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        redirect_base["year"] = year
        return redirect(url_for("fuel_bp.stations_equipment_group_fuel_params", **redirect_base))

    file = request.files["file"]
    if file.filename == "" or not file.filename:
        flash("Файл не выбран.", "danger")
        redirect_base["year"] = year
        return redirect(url_for("fuel_bp.stations_equipment_group_fuel_params", **redirect_base))

    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла. Требуется Excel (.xlsx или .xls).", "danger")
        redirect_base["year"] = year
        return redirect(url_for("fuel_bp.stations_equipment_group_fuel_params", **redirect_base))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла. Требуется Excel (.xlsx или .xls).", "danger")
        redirect_base["year"] = year
        return redirect(url_for("fuel_bp.stations_equipment_group_fuel_params", **redirect_base))

    try:
        result = import_equipment_group_fuel_params_from_excel(file, user, year)
        flash(result["message"], "success")
        current_app.logger.info(
            "[IMPORT_EQUIPMENT_GROUP_TOPLIVO_PARAMS_ROUTE] done user=%s created=%s updated=%s",
            user,
            result.get("created"),
            result.get("updated"),
        )
    except ValueError as e:
        current_app.logger.warning("[IMPORT_EQUIPMENT_GROUP_TOPLIVO_PARAMS_ROUTE] validation error: %s", str(e))
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.exception("[IMPORT_EQUIPMENT_GROUP_TOPLIVO_PARAMS_ROUTE] import failed")
        flash("Ошибка загрузки данных в EquipmentGroupFuelParam.", "danger")

    redirect_base = {k: v for k, v in request.form.items() if k not in ("file", "csrf_token")}
    redirect_base["year"] = year
    return redirect(url_for("fuel_bp.stations_equipment_group_fuel_params", **redirect_base))
