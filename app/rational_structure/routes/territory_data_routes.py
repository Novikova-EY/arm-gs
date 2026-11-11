from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError

from app.common.services.database_version_filter import get_current_db_version_id
from app.logs.services.logging_service import log_to_db
from app.rational_structure.routes import rational_structure_module_bp
from app.rational_structure.services.territory_data_export_services import export_territory_inputs
from app.rational_structure.services.territory_input_page_services import prepare_territory_input_view
from app.rational_structure.services.territory_input_services import (
    TERRITORY_INPUT_SHEETS, build_territory_input_context, save_territory_inputs,
)


def _context():
    sheet = request.args.get("sheet", "years")
    if sheet not in TERRITORY_INPUT_SHEETS:
        abort(400, "Неизвестная вкладка исходных данных.")
    zone_id = request.args.get("energy_zone_id", type=int)
    if "energy_zone_id" in request.args and zone_id is None:
        abort(400, "Некорректная энергозона.")
    try:
        return build_territory_input_context(get_current_db_version_id(), zone_id, sheet=sheet)
    except ValueError as exc:
        abort(404, str(exc))


@rational_structure_module_bp.route("/territory_inputs", methods=["GET", "POST"])
@login_required
def territory_inputs():
    if request.method == "POST" and not current_user.has_admin:
        abort(403)
    context = _context()
    if request.method == 'POST' and context['is_ees']:
        abort(403, 'Сводка ЕЭС России доступна только для просмотра.')
    form = FlaskForm()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Не удалось проверить форму. Обновите страницу и повторите сохранение.", "danger")
            return redirect(request.url)
        # При ошибке проверки или БД возвращаем введенные пользователем значения.
        for row in context["rows"]:
            row["cells"] = [request.form.get(f"value_{row['key']}_{year}", "") for year in context["years"]]
            row["note"] = request.form.get(f"note_{row['key']}", "")
        try:
            save_territory_inputs(context, request.form, current_user.username)
        except ValueError as exc:
            flash(str(exc), "danger")
            prepare_territory_input_view(context, request.args)
            return render_template("rational_structure/territory_inputs.html", **context,
                                   form=form, can_edit=current_user.has_admin), 400
        except SQLAlchemyError:
            current_app.logger.exception("Ошибка сохранения исходных данных по территориям")
            flash("Данные не сохранены: ошибка базы данных. Повторите попытку позже.", "danger")
            prepare_territory_input_view(context, request.args)
            return render_template("rational_structure/territory_inputs.html", **context,
                                   form=form, can_edit=current_user.has_admin), 500
        zone = context["selected_zone"]
        log_to_db(current_user.username, "Сохранены исходные данные по территориям",
                  f"Энергозона {zone.number}: {zone.name}; версия БД {context['version_id']}",
                  entity_type="rational_structure")
        flash("Исходные данные по территории сохранены.", "success")
        return redirect(url_for("rational_structure_module_bp.territory_inputs", energy_zone_id=zone.id,
                                sheet=context["sheet"]))
    prepare_territory_input_view(context, request.args)
    return render_template("rational_structure/territory_inputs.html", **context,
                           form=form, can_edit=current_user.has_admin)


@rational_structure_module_bp.route("/territory_inputs/export")
@login_required
def export_territory_inputs_excel():
    context = _context()
    if context["selected_zone"] is None and not context['is_ees']:
        abort(400, "Выберите энергозону.")
    prepare_territory_input_view(context, request.args)
    territory = 'ees' if context['is_ees'] else context['selected_zone'].number
    return send_file(export_territory_inputs(context), as_attachment=True,
                     download_name=f"territory_inputs_{territory}_{context['sheet']}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
