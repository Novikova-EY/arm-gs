# -*- coding: utf-8 -*-
from collections import Counter

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import login_required

from app.territories.routes.territories_bp import territories_bp
from app.territories.forms.power_transfers_forms import (
    AddPowerTransferForm,
    PowerTransferFilterForm,
)
from app.territories.services.power_transfers_services import (
    add_power_transfer_service,
    delete_power_transfer_service,
    get_power_transfer_choice_lists,
    get_power_transfer_default_year_range,
    get_power_transfer_filter_year_list,
    get_power_transfer_list,
    load_power_transfer_year_values_map,
    parse_power_transfer_year_range,
    power_transfer_display_years,
    power_transfer_query,
    extract_power_transfer_year_values_from_form,
    power_transfer_year_field_name,
    update_power_transfer_service,
)
from app.territories.services.territories_start_services import (
    build_territories_start_context,
)
from app.common.services.get_services.years.years_get_services import (
    get_year_feature_dict,
)
from app.logs.services.logging_service import log_to_db


@territories_bp.route("", strict_slashes=False)
@login_required
def territories_start():
    """Главная страница модуля «Характеристики территорий»."""
    return render_template(
        "territories/territories_start.html",
        **build_territories_start_context(),
    )


def _power_transfer_redirect_params() -> dict:
    start_year, end_year = parse_power_transfer_year_range(request.values)
    return {
        "page": request.values.get("page", 1, type=int),
        "per_page": request.values.get("per_page", 25, type=int),
        "sort_by": request.values.get("sort_by", "id"),
        "sort_dir": request.values.get("sort_dir", "asc"),
        "power_transfer_filter": request.values.get("power_transfer_filter", "").strip(),
        "start_year": start_year,
        "end_year": end_year,
    }


def _populate_add_form_choices(form: AddPowerTransferForm) -> None:
    choices = get_power_transfer_choice_lists()
    form.id_energy_unit.choices = choices["energy_unit_list"]
    form.id_regional_district.choices = choices["regional_district_list"]


@territories_bp.route("/power_transfers", methods=["GET", "POST"], strict_slashes=False)
@login_required
def power_transfers():
    """Перетоки мощности между энергоузлами."""
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница: перетоки мощности энергоузлов",
        entity_type="energy_unit_power_transfer",
    )

    form = PowerTransferFilterForm()
    params = _power_transfer_redirect_params()
    page = params["page"]
    per_page = params["per_page"]
    sort_by = params["sort_by"]
    sort_dir = params["sort_dir"]
    power_transfer_filter = params["power_transfer_filter"]
    start_year = params["start_year"]
    end_year = params["end_year"]
    display_years = power_transfer_display_years(start_year, end_year)

    if request.method == "POST":
        page = request.form.get("page", page, type=int)
        per_page = request.form.get("per_page", per_page, type=int)
        sort_by = request.form.get("sort_by", sort_by)
        sort_dir = request.form.get("sort_dir", sort_dir)
        power_transfer_filter = request.form.get(
            "power_transfer_filter", power_transfer_filter
        ).strip()
        start_year, end_year = parse_power_transfer_year_range(
            request.args,
            form_start_year=request.form.get("start_year"),
            form_end_year=request.form.get("end_year"),
        )
        display_years = power_transfer_display_years(start_year, end_year)

        transfer_ids = request.form.getlist("power_transfer_ids[]")
        energy_units = request.form.getlist("id_energy_units[]")
        regional_districts = request.form.getlist("id_regional_districts[]")
        directions = request.form.getlist("directions[]")
        delete_ids = request.form.getlist("power_transfer_delete[]")

        deleted_ids: set[int] = set()
        if delete_ids:
            try:
                delete_power_transfer_service(delete_ids, user)
                deleted_ids = {int(x) for x in delete_ids if str(x).isdigit()}
                flash("Записи успешно удалены.", "success")
            except Exception:
                flash("Ошибка удаления записей.", "danger")

        try:
            if not (transfer_ids and energy_units and regional_districts):
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
            else:
                if len(directions) < len(transfer_ids):
                    directions.extend([""] * (len(transfer_ids) - len(directions)))

                update_data = []
                for (
                    transfer_id,
                    id_energy_unit,
                    id_regional_district,
                    direction,
                ) in zip(transfer_ids, energy_units, regional_districts, directions):
                    if transfer_id and int(transfer_id) in deleted_ids:
                        continue
                    update_data.append(
                        {
                            "power_transfer_id": int(transfer_id)
                            if transfer_id
                            else None,
                            "id_energy_unit": id_energy_unit,
                            "id_regional_district": id_regional_district,
                            "direction": direction,
                        }
                    )

                if update_data:
                    ids = [
                        r["power_transfer_id"]
                        for r in update_data
                        if r["power_transfer_id"] is not None
                    ]
                    duplicates = [
                        item for item, count in Counter(ids).items() if count > 1
                    ]
                    if duplicates:
                        raise ValueError(
                            f"Обнаружены дублирующиеся ID: {duplicates}"
                        )

                    year_values = extract_power_transfer_year_values_from_form(
                        request.form,
                        [int(x) for x in transfer_ids if str(x).isdigit()],
                        display_years,
                    )
                    update_power_transfer_service(
                        update_data,
                        user,
                        year_values_by_transfer=year_values,
                        display_years=display_years,
                    )
                    flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(
            url_for(
                "territories_bp.power_transfers",
                page=page,
                per_page=per_page,
                power_transfer_filter=power_transfer_filter,
                sort_by=sort_by,
                sort_dir=sort_dir,
                start_year=start_year,
                end_year=end_year,
            )
        )

    pagination = get_power_transfer_list(
        page,
        per_page,
        power_transfer_filter=power_transfer_filter or None,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    choice_lists = get_power_transfer_choice_lists()
    transfer_ids = [item.id for item in pagination.items]
    power_transfer_year_values = load_power_transfer_year_values_map(
        transfer_ids, display_years
    )
    default_start_year, default_end_year = get_power_transfer_default_year_range()

    return render_template(
        "territories/power_transfers/power_transfers.html",
        form=form,
        power_transfer_list=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        power_transfer_filter=power_transfer_filter,
        page=page,
        page_title="Перетоки электроэнергии в смежные энергосистемы",
        start_year=start_year,
        end_year=end_year,
        display_years=display_years,
        filter_year_list=get_power_transfer_filter_year_list(),
        power_transfer_year_values=power_transfer_year_values,
        default_start_year=default_start_year,
        default_end_year=default_end_year,
        year_features=get_year_feature_dict(),
        power_transfer_year_field_name=power_transfer_year_field_name,
        **choice_lists,
    )


@territories_bp.route("/power_transfers/add", methods=["GET", "POST"], strict_slashes=False)
@login_required
def add_power_transfer():
    """Добавление перетока мощности."""
    user = session.get("username", "Неизвестный пользователь")
    log_to_db(
        user,
        "Открыта страница добавления перетока мощности",
        entity_type="energy_unit_power_transfer",
    )

    form = AddPowerTransferForm()
    _populate_add_form_choices(form)

    params = _power_transfer_redirect_params()

    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            return render_template(
                "territories/power_transfers/power_transfers_add.html",
                form=form,
                page_title="Добавить переток",
                **params,
            )

        try:
            payload = [
                {
                    "id_energy_unit": form.id_energy_unit.data,
                    "id_regional_district": form.id_regional_district.data,
                    "direction": (form.direction.data or "").strip(),
                }
            ]
            add_power_transfer_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            total_records = power_transfer_query(
                params["power_transfer_filter"] or None
            ).count()
            last_page = max(1, (total_records + params["per_page"] - 1) // params["per_page"])
            page = min(params["page"], last_page)

            return redirect(
                url_for(
                    "territories_bp.power_transfers",
                    page=last_page,
                    per_page=params["per_page"],
                    sort_by=params["sort_by"],
                    sort_dir=params["sort_dir"],
                    power_transfer_filter=params["power_transfer_filter"],
                    start_year=params["start_year"],
                    end_year=params["end_year"],
                )
            )
        except ValueError as e:
            flash(str(e), "danger")
        except Exception:
            flash(
                "Произошла ошибка при добавлении записи. Попробуйте позже.",
                "danger",
            )

    return render_template(
        "territories/power_transfers/power_transfers_add.html",
        form=form,
        page_title="Добавить переток",
        **params,
    )
