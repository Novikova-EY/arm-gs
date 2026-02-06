from flask import render_template, request, redirect, url_for, session, current_app, send_file, flash
from sqlalchemy import or_, func
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
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
    get_energy_system_type_name,
)
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    filter_by_explicit_db_version,
)
from app.fuel.services.export_stations_equipment_groups_services import (
    export_stations_equipment_groups_to_excel,
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
from app.fuel.services.import_stations_equipment_groups_services import (
    import_station_equipment_groups_from_excel,
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
        _normalize_external_id(item.dep_topl) for item in items if item.dep_topl
    }
    oes_ids = {
        _normalize_external_id(item.oes_topl) for item in items if item.oes_topl
    }
    fo_ids = {_normalize_external_id(item.fo_topl) for item in items if item.fo_topl}
    er_ids = {_normalize_external_id(item.er_topl) for item in items if item.er_topl}

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
        dep_key = _normalize_external_id(item.dep_topl)
        oes_key = _normalize_external_id(item.oes_topl)
        fo_key = _normalize_external_id(item.fo_topl)
        er_key = _normalize_external_id(item.er_topl)
        item.regional_district_name = regional_district_names.get(rd_key, "")
        item.regional_energy_system_name = regional_energy_system_names.get(res_key, "")
        item.energy_zone_name = energy_unit_names.get(ez_key, "")
        item.dep_topl_name = department_names.get(dep_key, "")
        item.oes_topl_name = union_energy_system_names.get(oes_key, "")
        item.fo_topl_name = federal_district_names.get(fo_key, "")
        item.er_topl_name = economic_region_names.get(er_key, "")


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
        "name_topl",
        "ao_topl",
        "obl_topl",
        "alph_topl",
        "dep_topl",
        "oes_topl",
        "er_topl",
        "terr_belyaev_topl",
        "teo90_topl",
        "fo_topl",
        "abbr_topl",
        "reu_topl",
        "pter_topl",
        "keyword_topl",
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
                TerritoriesEnergyExternalMapping.name_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.ao_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.obl_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.alph_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.dep_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.oes_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.er_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.terr_belyaev_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.teo90_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.fo_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.abbr_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.reu_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.pter_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.keyword_topl.ilike(like_term),
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
        "name_topl",
        "ao_topl",
        "obl_topl",
        "alph_topl",
        "dep_topl",
        "oes_topl",
        "er_topl",
        "terr_belyaev_topl",
        "teo90_topl",
        "fo_topl",
        "abbr_topl",
        "reu_topl",
        "pter_topl",
        "keyword_topl",
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
                TerritoriesEnergyExternalMapping.name_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.ao_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.obl_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.alph_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.dep_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.oes_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.er_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.terr_belyaev_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.teo90_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.fo_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.abbr_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.reu_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.pter_topl.ilike(like_term),
                TerritoriesEnergyExternalMapping.keyword_topl.ilike(like_term),
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
                "Субъект РФ в АРМ": row.regional_district_name or "",
                "Региональная энергосистема в АРМ": row.regional_energy_system_name or "",
                "Энергорайон в АРМ": row.energy_zone_name or "",
                "name_topl": row.name_topl or "",
                "ao_topl": row.ao_topl or "",
                "obl_topl": row.obl_topl or "",
                "alph_topl": row.alph_topl or "",
                "dep_topl": row.dep_topl_name or row.dep_topl or "",
                "oes_topl": row.oes_topl_name or row.oes_topl or "",
                "er_topl": row.er_topl_name or row.er_topl or "",
                "terr_belyaev_topl": row.terr_belyaev_topl or "",
                "teo90_topl": row.teo90_topl or "",
                "fo_topl": row.fo_topl_name or row.fo_topl or "",
                "abbr_topl": row.abbr_topl or "",
                "reu_topl": row.reu_topl or "",
                "pter_topl": row.pter_topl or "",
                "keyword_topl": row.keyword_topl or "",
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
    sort_by = request.args.get("sort_by", "id")
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
        "code_topl",
        "name_topl",
        "type_topl",
        "tm_topl",
        "n1_topl",
        "n2_topl",
        "p1_topl",
        "p2_topl",
        "gruppa_oborud_topl",
    }
    display_rows = None
    if sort_by in mapping_sort_fields:
        query = equipment_group_query(
            equipment_group_filter=equipment_group_filter,
            technology_type_filter=None,
            technology_availability_filter=None,
            sort_by="id",
            sort_dir="asc",
        )
        all_items = query.all()
    else:
        pagination = get_equipment_group_list(
            page=page,
            per_page=per_page,
            equipment_group_filter=equipment_group_filter,
            technology_type_filter=None,
            technology_availability_filter=None,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        all_items = pagination.items

    mappings = EquipmentGroupExternalMapping.query.order_by(
        EquipmentGroupExternalMapping.id.desc()
    ).all()
    mapping_by_eg = {}
    unmatched_mappings = []
    for mapping in mappings:
        if mapping.equipment_group_ref_uuid:
            if mapping.equipment_group_ref_uuid not in mapping_by_eg:
                mapping_by_eg[mapping.equipment_group_ref_uuid] = mapping
        else:
            unmatched_mappings.append(mapping)

    if sort_by in mapping_sort_fields:

        def _sort_key(row):
            mapping = row.mapping
            value = getattr(mapping, sort_by, None) if mapping else None
            return _sort_text_value(value)

        rows = [
            SimpleNamespace(eg=eg, mapping=mapping_by_eg.get(eg.ref_uuid))
            for eg in all_items
        ]
        rows.extend([SimpleNamespace(eg=None, mapping=m) for m in unmatched_mappings])
        rows.sort(key=_sort_key, reverse=(sort_dir == "desc"))
        total = len(rows)
        pagination = Pagination(page=page, per_page=per_page, total=total)
        start = (page - 1) * per_page
        end = start + per_page
        display_rows = rows[start:end]

    return render_template(
        "fuel/refdata/equipment_group/equipment_group.html",
        form=form,
        equipment_group_list=pagination.items if sort_by not in mapping_sort_fields else [],
        pagination=pagination,
        equipment_group_filter=equipment_group_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        mapping_by_eg=mapping_by_eg,
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
    sort_by = request.args.get("sort_by", "code_topl")
    sort_dir = request.args.get("sort_dir", "asc")
    cities_filter = request.args.get("cities_filter", "").strip()

    allowed_sort = {
        "id",
        "code_topl",
        "name_topl",
        "naselenie",
        "gilfond",
        "obesp_cts",
        "dprom_ao",
        "dgkh_ao",
        "obl",
    }
    if sort_by not in allowed_sort:
        sort_by = "code_topl"
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"

    query = CitiesExternalMapping.query
    if cities_filter:
        like_term = f"%{cities_filter}%"
        query = query.filter(
            or_(
                func.cast(CitiesExternalMapping.code_topl, db.String).ilike(like_term),
                CitiesExternalMapping.name_topl.ilike(like_term),
                CitiesExternalMapping.obesp_cts.ilike(like_term),
                CitiesExternalMapping.dprom_ao.ilike(like_term),
                CitiesExternalMapping.dgkh_ao.ilike(like_term),
                func.cast(CitiesExternalMapping.obl, db.String).ilike(like_term),
            )
        )

    sort_col = getattr(CitiesExternalMapping, sort_by, CitiesExternalMapping.code_topl)
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
        if result.get("errors"):
            for error in result["errors"][:5]:
                flash(error, "warning")
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
                "code_topl": m.external_id or "",
                "name_topl": m.external_name or "",
                "name": m.local_name or "",
                "UUID генерирующей компании": gc.ref_uuid if gc else "",
                "ID генерирующей компании (текущая версия)": gc.id if gc else "",
                "Наименование генерирующей компании в АРМ": gc.name if gc else "",
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
    sort_by = request.args.get("sort_by", "code_topl")
    sort_dir = request.args.get("sort_dir", "asc")

    allowed_sort = {
        "id",
        "code_topl",
        "name_topl",
        "naselenie",
        "gilfond",
        "obesp_cts",
        "dprom_ao",
        "dgkh_ao",
        "obl",
    }
    if sort_by not in allowed_sort:
        sort_by = "code_topl"
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"

    query = CitiesExternalMapping.query
    if cities_filter:
        like_term = f"%{cities_filter}%"
        query = query.filter(
            or_(
                func.cast(CitiesExternalMapping.code_topl, db.String).ilike(like_term),
                CitiesExternalMapping.name_topl.ilike(like_term),
                CitiesExternalMapping.obesp_cts.ilike(like_term),
                CitiesExternalMapping.dprom_ao.ilike(like_term),
                CitiesExternalMapping.dgkh_ao.ilike(like_term),
                func.cast(CitiesExternalMapping.obl, db.String).ilike(like_term),
            )
        )

    sort_col = getattr(CitiesExternalMapping, sort_by, CitiesExternalMapping.code_topl)
    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    rows = query.all()

    data = []
    for row in rows:
        data.append(
            {
                "code_topl": row.code_topl,
                "name_topl": row.name_topl or "",
                "naselenie": float(row.naselenie) if row.naselenie is not None else None,
                "gilfond": float(row.gilfond) if row.gilfond is not None else None,
                "obesp_cts": row.obesp_cts or "",
                "dprom_ao": row.dprom_ao or "",
                "dgkh_ao": row.dgkh_ao or "",
                "obl": row.obl,
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


@fuel_bp.route("/stations_equipment_groups/export", methods=["GET"])
@login_required
def export_stations_equipment_groups():
    """Экспорт данных stations_equipment_groups в Excel с id станций и агрегатов."""
    try:
        filters = extract_filters_from_args(request.args)
        start_year = int(request.args.get("start_year", get_filter_start_year()))
        end_year = int(request.args.get("end_year", get_filter_end_year()))
        
        # Генерируем Excel файл через отдельный сервис
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


@fuel_bp.route("/stations_equipment_groups/import", methods=["POST"])
@login_required
def import_stations_equipment_groups():
    """Импорт групп оборудования для агрегатов из Excel."""
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(user, "Начата загрузка групп оборудования")
    current_app.logger.info(
        "[IMPORT_EQUIPMENT_GROUPS_ROUTE] start user=%s filename=%s mimetype=%s remote_addr=%s",
        user,
        getattr(request.files.get("file"), "filename", None),
        getattr(request.files.get("file"), "mimetype", None),
        request.remote_addr,
    )

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.stations_equipment_groups", **request.args.to_dict()))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.stations_equipment_groups", **request.args.to_dict()))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.stations_equipment_groups", **request.args.to_dict()))

    try:
        result = import_station_equipment_groups_from_excel(file, user)
        flash(result["message"], "success")
        current_app.logger.info(
            "[IMPORT_EQUIPMENT_GROUPS_ROUTE] done user=%s filename=%s processed=%s errors=%s",
            user,
            getattr(file, "filename", None),
            result.get("processed_rows"),
            result.get("errors_count"),
        )
    except ValueError as e:
        current_app.logger.warning(
            "[IMPORT_EQUIPMENT_GROUPS_ROUTE] validation error user=%s filename=%s: %s",
            user,
            getattr(file, "filename", None),
            str(e),
            exc_info=True,
        )
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.exception(
            "[IMPORT_EQUIPMENT_GROUPS_ROUTE] import failed user=%s filename=%s",
            user,
            getattr(file, "filename", None),
        )
        flash("Ошибка загрузки групп оборудования.", "danger")

    return redirect(url_for("fuel_bp.stations_equipment_groups", **request.args.to_dict()))
