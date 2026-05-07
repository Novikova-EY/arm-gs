# -*- coding: utf-8 -*-
"""Маршруты ведения параметров нагрузки (demand) по типам справочников."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import asc, not_

from app.energy_consumption.forms.energy_consumption_parameter_forms import EmptyCSRFForm
from app.energy_consumption.routes.energy_consumption_bp import energy_consumption_bp
from app.energy_consumption.services import energy_consumption_parameter_services as dps

# Модели demand
from app.energy_consumption.models.energy_systems.regional_energy_system_energy_consumption_parameter_model import (
    RegionalEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_area_energy_consumption_parameter_model import (
    EnergyAreaEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_unit_energy_consumption_parameter_model import (
    EnergyUnitEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_zone_energy_consumption_parameter_model import (
    EnergyZoneEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.synchronous_area_energy_consumption_parameter_model import (
    SynchronousAreaEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
    UnionEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_system_type_energy_consumption_parameter_model import (
    EnergySystemTypeEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.federal_district_energy_consumption_parameter_model import (
    FederalDistrictEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.regional_district_energy_consumption_parameter_model import (
    RegionalDistrictEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.russia_federation_energy_consumption_parameter_model import (
    RussiaFederationEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.russia_federation_with_nt_energy_consumption_parameter_model import (
    RussiaFederationWithNtEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.ees_energy_consumption_parameter_model import (
    EesEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.ees_russia_energy_consumption_parameter_model import (
    EesRussiaEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.ees_russia_with_nt_energy_consumption_parameter_model import (
    EesRussiaWithNtEnergyConsumptionParameter,
)

# Родительские справочники
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.energy_area_model import EnergyArea
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict


def _synchronous_area_by_display_order(sa: SynchronousArea) -> tuple:
    """Карточки синхронных зон: display_order по возрастанию, NULL в конце, затем name, id."""
    d = getattr(sa, "display_order", None)
    if d is not None:
        return (0, int(d), (getattr(sa, "name", None) or "").casefold(), sa.id)
    return (1, 0, (getattr(sa, "name", None) or "").casefold(), sa.id)


def _csrf():
    return EmptyCSRFForm()


def _parse_energy_consumption_rounding_digits() -> int:
    """Знаки после запятой для отображения полей потребления (млн кВт·ч), как на страницах топлива."""
    raw = request.args.get("rounding_digits")
    if request.method == "POST" and (raw is None or str(raw).strip() == ""):
        raw = request.form.get("rounding_digits")
    if raw is None or str(raw).strip() == "":
        return 1
    try:
        v = int(raw)
    except (ValueError, TypeError):
        return 1
    if v == -1:
        return -1
    if v in (0, 1, 2, 3):
        return v
    return 1


def _redirect_preserving_rounding(endpoint: str, **url_kwargs):
    rd = request.form.get("rounding_digits")
    if rd is not None and str(rd).strip() != "":
        url_kwargs["rounding_digits"] = rd
    return redirect(url_for(endpoint, **url_kwargs))


# Типы энергосистем, вынесенные на хаб отдельными кнопками (не показываются в /energy-system-types/)
ENERGY_SYSTEM_TYPE_HUB_NAMES = ("ЕЭС России", "ТИТЭС")


# --- Хаб ---
@energy_consumption_bp.route("/")
@login_required
def hub():
    return render_template("energy_consumption/energy_consumption_start.html")


# --- Россия (без родителя) ---
@energy_consumption_bp.route("/russia/", methods=["GET", "POST"])
@login_required
def russia_demand():
    form = _csrf()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect(request.url)
        try:
            dps.save_demand_rows_from_post(
                RussiaFederationEnergyConsumptionParameter,
                None,
                None,
                request.form,
                require_combined_oe_ees=False,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        return _redirect_preserving_rounding("energy_consumption_bp.russia_demand")

    rows = dps.get_demand_rows(RussiaFederationEnergyConsumptionParameter, None, None)
    rd = _parse_energy_consumption_rounding_digits()
    return render_template(
        "energy_consumption/energy_consumption_edit.html",
        form=form,
        page_title="Нагрузки: Россия (без НТ)",
        parent_label="Россия (без НТ)",
        back_url=url_for("energy_consumption_bp.hub"),
        rows=rows,
        fk_column=None,
        parent_id=None,
        year_options=dps.year_dropdown_numbers(rows),
        show_combined_oess_eess=False,
        rounding_digits=rd,
    )


@energy_consumption_bp.route("/russia-with-nt/", methods=["GET", "POST"])
@login_required
def russia_with_nt_demand():
    """Те же поля и логика, что у /russia/, отдельная таблица (сценарий с новыми территориями)."""
    form = _csrf()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect(request.url)
        try:
            dps.save_demand_rows_from_post(
                RussiaFederationWithNtEnergyConsumptionParameter,
                None,
                None,
                request.form,
                require_combined_oe_ees=False,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        return _redirect_preserving_rounding("energy_consumption_bp.russia_with_nt_demand")

    rows = dps.get_demand_rows(RussiaFederationWithNtEnergyConsumptionParameter, None, None)
    rd = _parse_energy_consumption_rounding_digits()
    return render_template(
        "energy_consumption/energy_consumption_edit.html",
        form=form,
        page_title="Нагрузки: Россия (с НТ)",
        parent_label="Россия (с НТ)",
        back_url=url_for("energy_consumption_bp.hub"),
        rows=rows,
        fk_column=None,
        parent_id=None,
        year_options=dps.year_dropdown_numbers(rows),
        show_combined_oess_eess=False,
        rounding_digits=rd,
    )


@energy_consumption_bp.route("/ees-russia/", methods=["GET", "POST"])
@login_required
def ees_russia_demand():
    """ЕЭС России без НТ — отдельная таблица параметров нагрузки."""
    form = _csrf()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect(request.url)
        try:
            dps.save_demand_rows_from_post(
                EesRussiaEnergyConsumptionParameter,
                None,
                None,
                request.form,
                require_combined_oe_ees=False,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        return _redirect_preserving_rounding("energy_consumption_bp.ees_russia_demand")

    rows = dps.get_demand_rows(EesRussiaEnergyConsumptionParameter, None, None)
    rd = _parse_energy_consumption_rounding_digits()
    return render_template(
        "energy_consumption/energy_consumption_edit.html",
        form=form,
        page_title="Нагрузки: ЕЭС России (без НТ)",
        parent_label="ЕЭС России (без НТ)",
        back_url=url_for("energy_consumption_bp.hub"),
        rows=rows,
        fk_column=None,
        parent_id=None,
        year_options=dps.year_dropdown_numbers(rows),
        show_combined_oess_eess=False,
        rounding_digits=rd,
    )


@energy_consumption_bp.route("/ees-russia-with-nt/", methods=["GET", "POST"])
@login_required
def ees_russia_with_nt_demand():
    """ЕЭС России с НТ — отдельная таблица."""
    form = _csrf()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect(request.url)
        try:
            dps.save_demand_rows_from_post(
                EesRussiaWithNtEnergyConsumptionParameter,
                None,
                None,
                request.form,
                require_combined_oe_ees=False,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        return _redirect_preserving_rounding("energy_consumption_bp.ees_russia_with_nt_demand")

    rows = dps.get_demand_rows(EesRussiaWithNtEnergyConsumptionParameter, None, None)
    rd = _parse_energy_consumption_rounding_digits()
    return render_template(
        "energy_consumption/energy_consumption_edit.html",
        form=form,
        page_title="Нагрузки: ЕЭС России (с НТ)",
        parent_label="ЕЭС России (с НТ)",
        back_url=url_for("energy_consumption_bp.hub"),
        rows=rows,
        fk_column=None,
        parent_id=None,
        year_options=dps.year_dropdown_numbers(rows),
        show_combined_oess_eess=False,
        rounding_digits=rd,
    )


@energy_consumption_bp.route("/ees/", methods=["GET", "POST"])
@login_required
def ees_demand():
    """ЭЭС — отдельная таблица параметров нагрузки (без FK на справочник)."""
    form = _csrf()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect(request.url)
        try:
            dps.save_demand_rows_from_post(
                EesEnergyConsumptionParameter,
                None,
                None,
                request.form,
                require_combined_oe_ees=False,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        return _redirect_preserving_rounding("energy_consumption_bp.ees_demand")

    rows = dps.get_demand_rows(EesEnergyConsumptionParameter, None, None)
    rd = _parse_energy_consumption_rounding_digits()
    return render_template(
        "energy_consumption/energy_consumption_edit.html",
        form=form,
        page_title="Нагрузки: ЭЭС",
        parent_label="ЭЭС",
        back_url=url_for("energy_consumption_bp.hub"),
        rows=rows,
        fk_column=None,
        parent_id=None,
        year_options=dps.year_dropdown_numbers(rows),
        show_combined_oess_eess=False,
        rounding_digits=rd,
    )


# --- Универсальные list + detail ---
def _parent_list(
    parent_model,
    title: str,
    list_endpoint: str,
    demand_endpoint,
    label_fn,
    *order_columns,
    template_name: str = "energy_consumption/energy_consumption_parent_list.html",
    exclude_names: tuple[str, ...] = (),
    custom_order_by: tuple[Any, ...] | None = None,
    post_sort_key: Callable[[Any], tuple] | None = None,
):
    q = parent_model.query
    q = dps.filter_parents_by_version(q, parent_model)
    if custom_order_by is not None:
        q = q.order_by(*custom_order_by)
    elif order_columns:
        q = q.order_by(*[asc(c) for c in order_columns])
    else:
        q = q.order_by(asc(parent_model.id))
    search = (request.args.get("q") or "").strip()
    if search and hasattr(parent_model, "name"):
        q = q.filter(parent_model.name.ilike(f"%{search}%"))
    items = q.all()
    if exclude_names and hasattr(parent_model, "name"):
        excluded = {n.strip().casefold() for n in exclude_names}
        items = [
            i
            for i in items
            if (getattr(i, "name", None) or "").strip().casefold() not in excluded
        ]
    if post_sort_key is not None:
        items = sorted(items, key=post_sort_key)
    return render_template(
        template_name,
        form=_csrf(),
        page_title=title,
        items=items,
        label_fn=label_fn,
        list_endpoint=list_endpoint,
        demand_endpoint=demand_endpoint,
        search=search,
        back_url=url_for("energy_consumption_bp.hub"),
    )


def _demand_detail(
    demand_model,
    fk_column: str,
    parent_model,
    parent_id: int,
    page_title: str,
    parent_label: str,
    back_list_endpoint: str,
    show_combined_oess_eess: bool | None = None,
    show_combined_on_es: bool = False,
    show_combined_on_ez: bool = False,
):
    form = _csrf()
    parent_model.query.get_or_404(parent_id)
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect(request.url)
        try:
            dps.save_demand_rows_from_post(
                demand_model,
                fk_column,
                parent_id,
                request.form,
                require_combined_oe_ees=show_combined_oess_eess is not False
                and not show_combined_on_ez,
                require_combined_on_ez=show_combined_on_ez,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        return _redirect_preserving_rounding(request.endpoint, parent_id=parent_id)

    rows = dps.get_demand_rows(demand_model, fk_column, parent_id)
    rd = _parse_energy_consumption_rounding_digits()
    ctx = dict(
        form=form,
        page_title=page_title,
        parent_label=parent_label,
        back_url=url_for(back_list_endpoint),
        rows=rows,
        fk_column=fk_column,
        parent_id=parent_id,
        year_options=dps.year_dropdown_numbers(rows),
        rounding_digits=rd,
    )
    if show_combined_oess_eess is not None:
        ctx["show_combined_oess_eess"] = show_combined_oess_eess
    ctx["show_combined_on_ez"] = show_combined_on_ez
    return render_template("energy_consumption/energy_consumption_edit.html", **ctx)


# Региональные энергосистемы
@energy_consumption_bp.route("/regional-energy-systems/")
@login_required
def regional_energy_system_list():
    return _parent_list(
        RegionalEnergySystem,
        "Нагрузки: региональные энергосистемы",
        "energy_consumption_bp.regional_energy_system_list",
        "energy_consumption_bp.regional_energy_system_demand",
        lambda o: o.name,
        RegionalEnergySystem.name,
        exclude_names=("не указано", "не указано2"),
    )


@energy_consumption_bp.route("/regional-energy-systems/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def regional_energy_system_demand(parent_id: int):
    p = RegionalEnergySystem.query.get_or_404(parent_id)
    return _demand_detail(
        RegionalEnergySystemEnergyConsumptionParameter,
        "id_regional_energy_system",
        RegionalEnergySystem,
        parent_id,
        "Нагрузки: региональная энергосистема",
        p.name,
        "energy_consumption_bp.regional_energy_system_list",
        show_combined_oess_eess=False,
        show_combined_on_ez=False,
    )


# Энергоузлы
@energy_consumption_bp.route("/energy-areas/")
@login_required
def energy_area_list():
    return _parent_list(
        EnergyArea,
        "Нагрузки: энергоузлы",
        "energy_consumption_bp.energy_area_list",
        "energy_consumption_bp.energy_area_demand",
        lambda o: o.name,
        EnergyArea.name,
        exclude_names=("не указано", "не указано2"),
    )


@energy_consumption_bp.route("/energy-areas/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def energy_area_demand(parent_id: int):
    p = EnergyArea.query.get_or_404(parent_id)
    return _demand_detail(
        EnergyAreaEnergyConsumptionParameter,
        "id_energy_area",
        EnergyArea,
        parent_id,
        "Нагрузки: энергоузел",
        p.name,
        "energy_consumption_bp.energy_area_list",
    )


# Федеральные округа
@energy_consumption_bp.route("/federal-districts/")
@login_required
def federal_district_list():
    return _parent_list(
        FederalDistrict,
        "Нагрузки: федеральные округа",
        "energy_consumption_bp.federal_district_list",
        "energy_consumption_bp.federal_district_demand",
        lambda o: o.name,
        custom_order_by=(
            FederalDistrict.display_order.asc().nullslast(),
            FederalDistrict.name.asc(),
            FederalDistrict.id.asc(),
        ),
        template_name="energy_consumption/energy_consumption_parent_list_cards.html",
        exclude_names=("не указано", "не указано2"),
    )


@energy_consumption_bp.route("/federal-districts/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def federal_district_demand(parent_id: int):
    p = FederalDistrict.query.get_or_404(parent_id)
    return _demand_detail(
        FederalDistrictEnergyConsumptionParameter,
        "id_federal_district",
        FederalDistrict,
        parent_id,
        "Нагрузки: федеральный округ",
        p.name,
        "energy_consumption_bp.federal_district_list",
        show_combined_oess_eess=False,
    )


# Энергорайоны
@energy_consumption_bp.route("/energy-units/")
@login_required
def energy_unit_list():
    return _parent_list(
        EnergyUnit,
        "Нагрузки: энергорайоны",
        "energy_consumption_bp.energy_unit_list",
        "energy_consumption_bp.energy_unit_demand",
        lambda o: o.name,
        EnergyUnit.name,
        exclude_names=("не указано", "не указано2"),
    )


@energy_consumption_bp.route("/energy-units/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def energy_unit_demand(parent_id: int):
    p = EnergyUnit.query.get_or_404(parent_id)
    return _demand_detail(
        EnergyUnitEnergyConsumptionParameter,
        "id_energy_unit",
        EnergyUnit,
        parent_id,
        "Нагрузки: энергорайон",
        p.name,
        "energy_consumption_bp.energy_unit_list",
    )


# Энергозоны
@energy_consumption_bp.route("/energy-zones/")
@login_required
def energy_zone_list():
    return _parent_list(
        EnergyZone,
        "Нагрузки: энергозоны",
        "energy_consumption_bp.energy_zone_list",
        "energy_consumption_bp.energy_zone_demand",
        lambda o: f"{o.number} — {o.name}",
        EnergyZone.number,
        exclude_names=("не указано", "не указано2"),
    )


@energy_consumption_bp.route("/energy-zones/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def energy_zone_demand(parent_id: int):
    p = EnergyZone.query.get_or_404(parent_id)
    return _demand_detail(
        EnergyZoneEnergyConsumptionParameter,
        "id_energy_zone",
        EnergyZone,
        parent_id,
        "Нагрузки: энергозона",
        f"{p.number} — {p.name}",
        "energy_consumption_bp.energy_zone_list",
    )


# Субъекты РФ
@energy_consumption_bp.route("/regional-districts/")
@login_required
def regional_district_list():
    return _parent_list(
        RegionalDistrict,
        "Нагрузки: субъекты РФ",
        "energy_consumption_bp.regional_district_list",
        "energy_consumption_bp.regional_district_demand",
        lambda o: o.name,
        RegionalDistrict.name,
        exclude_names=("не указано", "не указано2"),
    )


@energy_consumption_bp.route("/regional-districts/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def regional_district_demand(parent_id: int):
    p = RegionalDistrict.query.get_or_404(parent_id)
    return _demand_detail(
        RegionalDistrictEnergyConsumptionParameter,
        "id_regional_district",
        RegionalDistrict,
        parent_id,
        "Нагрузки: субъект РФ",
        p.name,
        "energy_consumption_bp.regional_district_list",
        show_combined_on_es=False,
    )


# Синхронные зоны
@energy_consumption_bp.route("/synchronous-areas/")
@login_required
def synchronous_area_list():
    return _parent_list(
        SynchronousArea,
        "Нагрузки: синхронные зоны",
        "energy_consumption_bp.synchronous_area_list",
        "energy_consumption_bp.synchronous_area_demand",
        lambda o: o.name,
        SynchronousArea.id,
        template_name="energy_consumption/energy_consumption_parent_list_cards.html",
        exclude_names=("не указано",),
        post_sort_key=_synchronous_area_by_display_order,
    )


@energy_consumption_bp.route("/synchronous-areas/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def synchronous_area_demand(parent_id: int):
    p = SynchronousArea.query.get_or_404(parent_id)
    return _demand_detail(
        SynchronousAreaEnergyConsumptionParameter,
        "id_synchronous_area",
        SynchronousArea,
        parent_id,
        "Нагрузки: синхронная зона",
        p.name,
        "energy_consumption_bp.synchronous_area_list",
        show_combined_oess_eess=False,
    )


# ОЭС
@energy_consumption_bp.route("/union-energy-systems/")
@login_required
def union_energy_system_list():
    return _parent_list(
        UnionEnergySystem,
        "Нагрузки: объединённые энергосистемы (ОЭС)",
        "energy_consumption_bp.union_energy_system_list",
        "energy_consumption_bp.union_energy_system_demand",
        lambda o: o.name,
        custom_order_by=(
            UnionEnergySystem.display_order.asc().nullslast(),
            UnionEnergySystem.name.asc(),
            UnionEnergySystem.id.asc(),
        ),
        template_name="energy_consumption/energy_consumption_parent_list_cards.html",
        exclude_names=("не указано", "не указано2"),
    )


@energy_consumption_bp.route("/union-energy-systems/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def union_energy_system_demand(parent_id: int):
    p = UnionEnergySystem.query.get_or_404(parent_id)
    return _demand_detail(
        UnionEnergySystemEnergyConsumptionParameter,
        "id_union_energy_system",
        UnionEnergySystem,
        parent_id,
        "Нагрузки: ОЭС",
        p.name,
        "energy_consumption_bp.union_energy_system_list",
        show_combined_oess_eess=False,
    )


# Тип энергосистемы
@energy_consumption_bp.route("/energy-system-types/")
@login_required
def energy_system_type_list():
    q = EnergySystemType.query
    q = dps.filter_parents_by_version(q, EnergySystemType)
    q = q.filter(not_(EnergySystemType.name.in_(ENERGY_SYSTEM_TYPE_HUB_NAMES)))
    q = q.order_by(asc(EnergySystemType.name))
    search = (request.args.get("q") or "").strip()
    if search:
        q = q.filter(EnergySystemType.name.ilike(f"%{search}%"))
    items = q.all()
    return render_template(
        "energy_consumption/energy_consumption_parent_list.html",
        form=_csrf(),
        page_title="Нагрузки: типы энергосистем",
        items=items,
        label_fn=lambda o: o.name,
        list_endpoint="energy_consumption_bp.energy_system_type_list",
        demand_endpoint="energy_consumption_bp.energy_system_type_demand",
        search=search,
        back_url=url_for("energy_consumption_bp.hub"),
    )


@energy_consumption_bp.route("/energy-system-types/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def energy_system_type_demand(parent_id: int):
    p = EnergySystemType.query.get_or_404(parent_id)
    return _demand_detail(
        EnergySystemTypeEnergyConsumptionParameter,
        "id_energy_system_type",
        EnergySystemType,
        parent_id,
        f"Нагрузки: {p.name}",
        p.name,
        "energy_consumption_bp.energy_system_type_list",
    )
