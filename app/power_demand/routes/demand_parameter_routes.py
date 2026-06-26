# -*- coding: utf-8 -*-
"""Маршруты ведения параметров нагрузки (demand) по типам справочников."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import asc, not_

from app.extensions import db
from app.power_demand.forms.demand_parameter_forms import EmptyCSRFForm
from app.power_demand.routes.power_demand_bp import power_demand_bp
from app.power_demand.services import demand_parameter_services as dps
from app.power_demand.services.formula_text.power_demand_summary_formula_text_services import (
    list_formulas_for_admin,
    reset_formula_text_override,
    save_formula_text_override,
)

# Модели demand
from app.power_demand.models.energy_systems.regional_energy_system_demand_parameter_model import (
    RegionalEnergySystemDemandParameter,
)
from app.power_demand.models.energy_systems.energy_area_demand_parameter_model import (
    EnergyAreaDemandParameter,
)
from app.power_demand.models.energy_systems.energy_unit_demand_parameter_model import (
    EnergyUnitDemandParameter,
)
from app.power_demand.models.energy_systems.energy_zone_demand_parameter_model import (
    EnergyZoneDemandParameter,
)
from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.power_demand.models.territories.federal_district_demand_parameter_model import (
    FederalDistrictDemandParameter,
)
from app.power_demand.models.territories.regional_district_demand_parameter_model import (
    RegionalDistrictDemandParameter,
)
from app.common.perimeter_variant.constants import (
    CODE_WITH_NT,
    CODE_WITHOUT_NT,
    EES_UNIFIED_REF_NAME,
)
from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
    RussiaFederationDemandParameter,
)
from app.power_demand.models.energy_systems.ees_demand_parameter_model import (
    EesDemandParameter,
)
from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
    EesRussiaDemandParameter,
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
from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    synchronous_area_display_order_sort_key,
)


def _synchronous_area_by_display_order(sa: SynchronousArea) -> tuple:
    """Карточки синхронных зон: как :func:`synchronous_area_display_order_sort_key`."""
    return synchronous_area_display_order_sort_key(sa)


def _csrf():
    return EmptyCSRFForm()


def _parse_power_demand_rounding_digits() -> int:
    """Знаки после запятой для отображения/ввода Макс. потребления (как на страницах топлива)."""
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
@power_demand_bp.route("/")
@login_required
def hub():
    return render_template("power_demand/power_demand_start.html")


@power_demand_bp.route("/formulas/")
@login_required
def power_demand_formulas():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для редактирования текстов формул.", "danger")
        return redirect(url_for("power_demand_bp.hub"))
    return render_template(
        "power_demand/power_demand_summary_formulas.html",
        page_title="Тексты формул для модуля «Нагрузки»",
        formula_rows=list_formulas_for_admin(),
    )


@power_demand_bp.route("/summary_formulas/")
@login_required
def power_demand_summary_formulas():
    return redirect(url_for("power_demand_bp.power_demand_formulas", **request.args))


@power_demand_bp.route("/formulas/save", methods=["POST"])
@login_required
def power_demand_formulas_save():
    if not getattr(current_user, "has_admin", False):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    try:
        save_formula_text_override(
            formula_key=str(data.get("formula_key") or ""),
            formula_text=str(data.get("formula_text") or ""),
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True)


@power_demand_bp.route("/formulas/reset", methods=["POST"])
@login_required
def power_demand_formulas_reset():
    if not getattr(current_user, "has_admin", False):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    key = str(data.get("formula_key") or "").strip()
    if not key:
        return jsonify(ok=False, error="Не указан ключ формулы."), 400
    reset_formula_text_override(key)
    db.session.commit()
    return jsonify(ok=True)


@power_demand_bp.route("/summary_formulas/save", methods=["POST"])
@login_required
def power_demand_summary_formulas_save():
    return power_demand_formulas_save()


@power_demand_bp.route("/summary_formulas/reset", methods=["POST"])
@login_required
def power_demand_summary_formulas_reset():
    return power_demand_formulas_reset()


# --- Россия (без родителя) ---
@power_demand_bp.route("/russia/", methods=["GET", "POST"])
@login_required
def russia_demand():
    form = _csrf()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect(request.url)
        try:
            dps.save_demand_rows_from_post(
                RussiaFederationDemandParameter,
                None,
                None,
                request.form,
                require_combined_oe_ees=False,
                perimeter_variant_code=CODE_WITHOUT_NT,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        return _redirect_preserving_rounding("power_demand_bp.russia_demand")

    rows = dps.get_demand_rows(
        RussiaFederationDemandParameter,
        None,
        None,
        perimeter_variant_code=CODE_WITHOUT_NT,
    )
    rd = _parse_power_demand_rounding_digits()
    return render_template(
        "power_demand/power_demand_edit.html",
        form=form,
        page_title="Нагрузки: Россия без НТ",
        parent_label="Россия без НТ",
        back_url=url_for("power_demand_bp.hub"),
        rows=rows,
        fk_column=None,
        parent_id=None,
        format_dt=dps.format_peak_datetime,
        year_options=dps.year_dropdown_numbers(rows),
        show_combined_oess_eess=False,
        rounding_digits=rd,
    )


@power_demand_bp.route("/russia_with_nt/", methods=["GET", "POST"])
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
                RussiaFederationDemandParameter,
                None,
                None,
                request.form,
                require_combined_oe_ees=False,
                perimeter_variant_code=CODE_WITH_NT,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        return _redirect_preserving_rounding("power_demand_bp.russia_with_nt_demand")

    rows = dps.get_demand_rows(
        RussiaFederationDemandParameter,
        None,
        None,
        perimeter_variant_code=CODE_WITH_NT,
    )
    rd = _parse_power_demand_rounding_digits()
    return render_template(
        "power_demand/power_demand_edit.html",
        form=form,
        page_title="Нагрузки: Россия (с НТ)",
        parent_label="Россия (с НТ)",
        back_url=url_for("power_demand_bp.hub"),
        rows=rows,
        fk_column=None,
        parent_id=None,
        format_dt=dps.format_peak_datetime,
        year_options=dps.year_dropdown_numbers(rows),
        show_combined_oess_eess=False,
        rounding_digits=rd,
    )


def _ees_unified_energy_system_type() -> EnergySystemType | None:
    q = EnergySystemType.query.filter(EnergySystemType.name == EES_UNIFIED_REF_NAME)
    q = dps.filter_parents_by_version(q, EnergySystemType)
    return q.order_by(EnergySystemType.id.asc()).first()


def _redirect_ees_unified_energy_system_type_demand(
    endpoint_name: str,
    *,
    perimeter_variant_code: str | None = None,
):
    est = _ees_unified_energy_system_type()
    if est is None:
        flash(f'В справочнике не найден тип энергосистемы «{EES_UNIFIED_REF_NAME}».', "danger")
        return redirect(url_for("power_demand_bp.hub"))
    url_kwargs: dict[str, Any] = {
        "parent_id": int(est.id),
        "rounding_digits": _parse_power_demand_rounding_digits(),
    }
    if perimeter_variant_code:
        url_kwargs["perimeter_variant"] = perimeter_variant_code
    return redirect(url_for("power_demand_bp.energy_system_type_demand", **url_kwargs))


@power_demand_bp.route("/ees_russia/", methods=["GET", "POST"])
@login_required
def ees_russia_demand():
    """Редирект на ведение «ЕЭС России» (EnergySystemType)."""
    from app.common.perimeter_variant.constants import CODE_WITHOUT_NT_WITHOUT_GAES

    return _redirect_ees_unified_energy_system_type_demand(
        "power_demand_bp.ees_russia_demand",
        perimeter_variant_code=CODE_WITHOUT_NT_WITHOUT_GAES,
    )


@power_demand_bp.route("/ees_russia_with_nt/", methods=["GET", "POST"])
@login_required
def ees_russia_with_nt_demand():
    """Редирект на ведение «ЕЭС России» (EnergySystemType)."""
    from app.common.perimeter_variant.constants import CODE_WITH_NT_WITHOUT_GAES

    return _redirect_ees_unified_energy_system_type_demand(
        "power_demand_bp.ees_russia_with_nt_demand",
        perimeter_variant_code=CODE_WITH_NT_WITHOUT_GAES,
    )


@power_demand_bp.route("/ees/", methods=["GET", "POST"])
@login_required
def ees_demand():
    """ЭЭС России без НТ — отдельная таблица параметров нагрузки (без FK на справочник)."""
    form = _csrf()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect(request.url)
        try:
            dps.save_demand_rows_from_post(
                EesRussiaDemandParameter,
                None,
                None,
                request.form,
                require_combined_oe_ees=False,
                perimeter_variant_code=CODE_WITHOUT_NT,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        return _redirect_preserving_rounding("power_demand_bp.ees_demand")

    rows = dps.get_demand_rows(
        EesRussiaDemandParameter,
        None,
        None,
        perimeter_variant_code=CODE_WITHOUT_NT,
    )
    rd = _parse_power_demand_rounding_digits()
    return render_template(
        "power_demand/power_demand_edit.html",
        form=form,
        page_title="Нагрузки: ЭЭС России без НТ",
        parent_label="ЭЭС России без НТ",
        back_url=url_for("power_demand_bp.hub"),
        rows=rows,
        fk_column=None,
        parent_id=None,
        format_dt=dps.format_peak_datetime,
        year_options=dps.year_dropdown_numbers(rows),
        show_combined_oess_eess=False,
        rounding_digits=rd,
    )


@power_demand_bp.route("/ees_with_nt/", methods=["GET", "POST"])
@login_required
def ees_with_nt_demand():
    """ЭЭС России с НТ — те же поля, что у /ees/, вариант периметра with_nt."""
    form = _csrf()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect(request.url)
        try:
            dps.save_demand_rows_from_post(
                EesRussiaDemandParameter,
                None,
                None,
                request.form,
                require_combined_oe_ees=False,
                perimeter_variant_code=CODE_WITH_NT,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        return _redirect_preserving_rounding("power_demand_bp.ees_with_nt_demand")

    rows = dps.get_demand_rows(
        EesRussiaDemandParameter,
        None,
        None,
        perimeter_variant_code=CODE_WITH_NT,
    )
    rd = _parse_power_demand_rounding_digits()
    return render_template(
        "power_demand/power_demand_edit.html",
        form=form,
        page_title="Нагрузки: ЭЭС России с НТ",
        parent_label="ЭЭС России с НТ",
        back_url=url_for("power_demand_bp.hub"),
        rows=rows,
        fk_column=None,
        parent_id=None,
        format_dt=dps.format_peak_datetime,
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
    template_name: str = "power_demand/power_demand_parent_list.html",
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
        back_url=url_for("power_demand_bp.hub"),
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
    perimeter_variant_code: str | None = None,
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
                perimeter_variant_code=perimeter_variant_code,
            )
            flash("Данные сохранены.", "success")
        except Exception as e:
            flash(f"Ошибка сохранения: {e}", "danger")
        extra: dict[str, Any] = {}
        if perimeter_variant_code:
            extra["perimeter_variant"] = perimeter_variant_code
        return _redirect_preserving_rounding(
            request.endpoint, parent_id=parent_id, **extra
        )

    rows = dps.get_demand_rows(
        demand_model,
        fk_column,
        parent_id,
        perimeter_variant_code=perimeter_variant_code,
    )
    rd = _parse_power_demand_rounding_digits()
    ctx = dict(
        form=form,
        page_title=page_title,
        parent_label=parent_label,
        back_url=url_for(back_list_endpoint),
        rows=rows,
        fk_column=fk_column,
        parent_id=parent_id,
        format_dt=dps.format_peak_datetime,
        year_options=dps.year_dropdown_numbers(rows),
        rounding_digits=rd,
    )
    if show_combined_oess_eess is not None:
        ctx["show_combined_oess_eess"] = show_combined_oess_eess
    ctx["show_combined_on_ez"] = show_combined_on_ez
    return render_template("power_demand/power_demand_edit.html", **ctx)


# Региональные энергосистемы
@power_demand_bp.route("/regional_energy_systems/")
@login_required
def regional_energy_system_list():
    return _parent_list(
        RegionalEnergySystem,
        "Нагрузки: региональные энергосистемы",
        "power_demand_bp.regional_energy_system_list",
        "power_demand_bp.regional_energy_system_demand",
        lambda o: o.name,
        RegionalEnergySystem.name,
        exclude_names=("не указано", "не указано2"),
    )


@power_demand_bp.route("/regional_energy_systems/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def regional_energy_system_demand(parent_id: int):
    p = RegionalEnergySystem.query.get_or_404(parent_id)
    return _demand_detail(
        RegionalEnergySystemDemandParameter,
        "id_regional_energy_system",
        RegionalEnergySystem,
        parent_id,
        "Нагрузки: региональная энергосистема",
        p.name,
        "power_demand_bp.regional_energy_system_list",
        show_combined_oess_eess=False,
        show_combined_on_ez=True,
    )


# Энергоузлы
@power_demand_bp.route("/energy_areas/")
@login_required
def energy_area_list():
    return _parent_list(
        EnergyArea,
        "Нагрузки: энергоузлы",
        "power_demand_bp.energy_area_list",
        "power_demand_bp.energy_area_demand",
        lambda o: o.name,
        EnergyArea.name,
        exclude_names=("не указано", "не указано2"),
    )


@power_demand_bp.route("/energy_areas/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def energy_area_demand(parent_id: int):
    p = EnergyArea.query.get_or_404(parent_id)
    return _demand_detail(
        EnergyAreaDemandParameter,
        "id_energy_area",
        EnergyArea,
        parent_id,
        "Нагрузки: энергоузел",
        p.name,
        "power_demand_bp.energy_area_list",
    )


# Федеральные округа
@power_demand_bp.route("/federal_districts/")
@login_required
def federal_district_list():
    return _parent_list(
        FederalDistrict,
        "Нагрузки: федеральные округа",
        "power_demand_bp.federal_district_list",
        "power_demand_bp.federal_district_demand",
        lambda o: o.name,
        custom_order_by=(
            FederalDistrict.display_order.asc().nullslast(),
            FederalDistrict.name.asc(),
            FederalDistrict.id.asc(),
        ),
        template_name="power_demand/power_demand_parent_list_cards.html",
        exclude_names=("не указано", "не указано2"),
    )


@power_demand_bp.route("/federal_districts/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def federal_district_demand(parent_id: int):
    p = FederalDistrict.query.get_or_404(parent_id)
    return _demand_detail(
        FederalDistrictDemandParameter,
        "id_federal_district",
        FederalDistrict,
        parent_id,
        "Нагрузки: федеральный округ",
        p.name,
        "power_demand_bp.federal_district_list",
        show_combined_oess_eess=False,
    )


# Энергорайоны
@power_demand_bp.route("/energy_units/")
@login_required
def energy_unit_list():
    return _parent_list(
        EnergyUnit,
        "Нагрузки: энергорайоны",
        "power_demand_bp.energy_unit_list",
        "power_demand_bp.energy_unit_demand",
        lambda o: o.name,
        EnergyUnit.name,
        exclude_names=("не указано", "не указано2"),
    )


@power_demand_bp.route("/energy_units/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def energy_unit_demand(parent_id: int):
    p = EnergyUnit.query.get_or_404(parent_id)
    return _demand_detail(
        EnergyUnitDemandParameter,
        "id_energy_unit",
        EnergyUnit,
        parent_id,
        "Нагрузки: энергорайон",
        p.name,
        "power_demand_bp.energy_unit_list",
        show_combined_on_es=True,
    )


# Энергозоны
@power_demand_bp.route("/energy_zones/")
@login_required
def energy_zone_list():
    return _parent_list(
        EnergyZone,
        "Нагрузки: энергозоны",
        "power_demand_bp.energy_zone_list",
        "power_demand_bp.energy_zone_demand",
        lambda o: f"{o.number} — {o.name}",
        EnergyZone.number,
        exclude_names=("не указано", "не указано2"),
    )


@power_demand_bp.route("/energy_zones/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def energy_zone_demand(parent_id: int):
    p = EnergyZone.query.get_or_404(parent_id)
    return _demand_detail(
        EnergyZoneDemandParameter,
        "id_energy_zone",
        EnergyZone,
        parent_id,
        "Нагрузки: энергозона",
        f"{p.number} — {p.name}",
        "power_demand_bp.energy_zone_list",
    )


# Субъекты РФ
@power_demand_bp.route("/regional_districts/")
@login_required
def regional_district_list():
    return _parent_list(
        RegionalDistrict,
        "Нагрузки: субъекты РФ",
        "power_demand_bp.regional_district_list",
        "power_demand_bp.regional_district_demand",
        lambda o: o.name,
        RegionalDistrict.name,
        exclude_names=("не указано", "не указано2"),
    )


@power_demand_bp.route("/regional_districts/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def regional_district_demand(parent_id: int):
    p = RegionalDistrict.query.get_or_404(parent_id)
    return _demand_detail(
        RegionalDistrictDemandParameter,
        "id_regional_district",
        RegionalDistrict,
        parent_id,
        "Нагрузки: субъект РФ",
        p.name,
        "power_demand_bp.regional_district_list",
        show_combined_on_es=True,
    )


# Синхронные зоны
@power_demand_bp.route("/synchronous_areas/")
@login_required
def synchronous_area_list():
    return _parent_list(
        SynchronousArea,
        "Нагрузки: синхронные зоны",
        "power_demand_bp.synchronous_area_list",
        "power_demand_bp.synchronous_area_demand",
        lambda o: o.name,
        SynchronousArea.id,
        template_name="power_demand/power_demand_parent_list_cards.html",
        exclude_names=("не указано",),
        post_sort_key=_synchronous_area_by_display_order,
    )


@power_demand_bp.route("/synchronous_areas/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def synchronous_area_demand(parent_id: int):
    p = SynchronousArea.query.get_or_404(parent_id)
    is_first = (p.name or "").strip().casefold().startswith("первая синхронная зона")
    suffix = " без НТ" if is_first else ""
    return _demand_detail(
        SynchronousAreaDemandParameter,
        "id_synchronous_area",
        SynchronousArea,
        parent_id,
        f"Нагрузки: {p.name}{suffix}",
        f"{p.name}{suffix}",
        "power_demand_bp.synchronous_area_list",
        show_combined_oess_eess=False,
        perimeter_variant_code=CODE_WITHOUT_NT,
    )


@power_demand_bp.route("/synchronous_areas/<int:parent_id>/with_nt/", methods=["GET", "POST"])
@login_required
def synchronous_area_with_nt_demand(parent_id: int):
    p = SynchronousArea.query.get_or_404(parent_id)
    return _demand_detail(
        SynchronousAreaDemandParameter,
        "id_synchronous_area",
        SynchronousArea,
        parent_id,
        f"Нагрузки: {p.name} с НТ",
        f"{p.name} с НТ",
        "power_demand_bp.synchronous_area_list",
        show_combined_oess_eess=False,
        perimeter_variant_code=CODE_WITH_NT,
    )


# ОЭС
@power_demand_bp.route("/union_energy_systems/")
@login_required
def union_energy_system_list():
    return _parent_list(
        UnionEnergySystem,
        "Нагрузки: объединённые энергосистемы (ОЭС)",
        "power_demand_bp.union_energy_system_list",
        "power_demand_bp.union_energy_system_demand",
        lambda o: o.name,
        custom_order_by=(
            UnionEnergySystem.display_order.asc().nullslast(),
            UnionEnergySystem.name.asc(),
            UnionEnergySystem.id.asc(),
        ),
        template_name="power_demand/power_demand_parent_list_cards.html",
        exclude_names=("не указано", "не указано2"),
    )


@power_demand_bp.route("/union_energy_systems/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def union_energy_system_demand(parent_id: int):
    from app.common.perimeter_variant.registry import (
        perimeter_variant_definitions,
        resolve_entity_perimeter_variants,
        variant_label_for_entity,
    )

    p = UnionEnergySystem.query.get_or_404(parent_id)
    binding = resolve_entity_perimeter_variants("union_energy_system", p.name)
    spv = (
        request.args.get("perimeter_variant")
        or request.args.get("south_variant")
        or ""
    ).strip()
    if binding is not None:
        allowed = {v.code for v in binding.variants}
        if spv not in allowed:
            spv = binding.variants[0].code if binding.variants else ""
        suffix = ""
        pdefs = perimeter_variant_definitions()
        if spv and spv in pdefs:
            suffix = f" — {variant_label_for_entity(binding, pdefs[spv])}"
    else:
        spv = ""
        suffix = ""
    return _demand_detail(
        UnionEnergySystemDemandParameter,
        "id_union_energy_system",
        UnionEnergySystem,
        parent_id,
        f"Нагрузки: ОЭС{suffix}",
        p.name,
        "power_demand_bp.union_energy_system_list",
        show_combined_oess_eess=False,
        perimeter_variant_code=(spv or None) if binding else None,
    )


# Тип энергосистемы
@power_demand_bp.route("/energy_system_types/")
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
        "power_demand/power_demand_parent_list.html",
        form=_csrf(),
        page_title="Нагрузки: типы энергосистем",
        items=items,
        label_fn=lambda o: o.name,
        list_endpoint="power_demand_bp.energy_system_type_list",
        demand_endpoint="power_demand_bp.energy_system_type_demand",
        search=search,
        back_url=url_for("power_demand_bp.hub"),
    )


@power_demand_bp.route("/energy_system_types/<int:parent_id>/", methods=["GET", "POST"])
@login_required
def energy_system_type_demand(parent_id: int):
    p = EnergySystemType.query.get_or_404(parent_id)
    pvc = (request.args.get("perimeter_variant") or "").strip() or None
    return _demand_detail(
        EnergySystemTypeDemandParameter,
        "id_energy_system_type",
        EnergySystemType,
        parent_id,
        f"Нагрузки: {p.name}",
        p.name,
        "power_demand_bp.energy_system_type_list",
        perimeter_variant_code=pvc,
    )
