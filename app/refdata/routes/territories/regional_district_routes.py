"""Маршруты справочника «Субъекты РФ»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.territories.regional_district_forms import (
    RegionalDistrictFilterForm, 
    AddRegionalDistrictForm,
)

from app.common.services.choices_cache_service import choices_cache
from app.common.services.get_services.energy_systems.energy_zone_get_services import (
    get_energy_zone_list_full,
)
from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    get_synchronous_area_list_full,
)
from app.refdata.services.territories.regional_district_services import (
    regional_district_query,
    get_regional_district_list,
    update_regional_district_service, 
    add_regional_district_service, 
    delete_regional_district_service,
    import_regional_district_service, 
    export_regional_district_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/regional_district", methods=["GET", "POST"])
@login_required
def regional_district_list():
    """Маршрут для отображения списка субъектов РФ."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница субъектов РФ", entity_type="regional_district")
    
    # Создание формы
    form = RegionalDistrictFilterForm()

    # Получение параметров запроса
    page                        = request.args.get("page", 1, type=int)
    per_page                    = request.args.get("per_page", 20, type=int)
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    region_ids                  = request.args.getlist("region_ids[]")
    regional_district_filter    = request.args.get("regional_district_filter", "").strip()
    federal_district_filter     = request.args.get("federal_district_filter")
    energy_zone_filter          = request.args.get("energy_zone_filter")
    synchronous_area_filter     = request.args.get("synchronous_area_filter")

    if request.method == "POST":
        # Обновление параметров из формы
        page                        = request.form.get("page", 1, type=int)
        per_page                    = request.form.get("per_page", 20, type=int)
        sort_by                     = request.form.get("sort_by", "id")
        sort_dir                    = request.form.get("sort_dir", "asc")
        regional_district_filter    = request.form.get("regional_district_filter", "").strip()
        federal_district_filter     = request.form.get("federal_district_filter")
        energy_zone_filter          = request.form.get("energy_zone_filter")
        synchronous_area_filter     = request.form.get("synchronous_area_filter")

        # Получение данных из формы
        region_ids                      = request.form.getlist("region_ids[]")
        regional_district_ids           = request.form.getlist("regional_district_ids[]")
        regional_district_names         = request.form.getlist("regional_district_names[]")
        regional_district_full_names    = request.form.getlist("regional_district_full_names[]")
        regional_district_rp_names      = request.form.getlist("regional_district_rp_names[]")
        regional_district_dp_names      = request.form.getlist("regional_district_dp_names[]")
        regional_district_delete        = request.form.getlist("regional_district_delete[]")
        federal_district_ids            = request.form.getlist("federal_districts[]")
        energy_zone_ids                 = request.form.getlist("energy_zones[]")
        synchronous_area_ids            = request.form.getlist("synchronous_areas[]")

        # Удаление записей
        if regional_district_delete:
            try:
                delete_regional_district_service(regional_district_delete, user)
                flash("Записи субъектов РФ успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.regional_district_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    regional_district_filter=regional_district_filter,
                                    federal_district_filter=federal_district_filter,
                                    energy_zone_filter=energy_zone_filter,
                                    synchronous_area_filter=synchronous_area_filter,
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
           
        # Обновление данных в базе
        try:
            if not regional_district_ids:
                log_to_db(user, "Нет данных для обновления.", entity_type="regional_district")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.regional_district_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        regional_district_filter=regional_district_filter,
                                        federal_district_filter=federal_district_filter,
                                        energy_zone_filter=energy_zone_filter,
                                        synchronous_area_filter=synchronous_area_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
            
            # Формирование данных для обновления
            regional_district_data = []
            for regional_district_id, regional_district_name, regional_district_full_name, regional_district_rp_name, regional_district_dp_name, federal_district_id, energy_zone_id, synchronous_area_id, region_id in zip(
                regional_district_ids, regional_district_names, regional_district_full_names, regional_district_rp_names, regional_district_dp_names, federal_district_ids, energy_zone_ids, synchronous_area_ids, region_ids
            ):
                try:
                    regional_district_data.append({
                        "regional_district_id": int(regional_district_id) if regional_district_id else None,
                        "region_id": (region_id or "").strip() or None,
                        "name": regional_district_name.strip(),
                        "name_full": regional_district_full_name.strip(),
                        "name_rp": regional_district_rp_name.strip(),
                        "name_dp": regional_district_dp_name.strip(),
                        "federal_district_id": int(federal_district_id) if federal_district_id else None,
                        # Ключ должен совпадать с ожидаемым в update_regional_district_service
                        "energy_zone_id": int(energy_zone_id) if energy_zone_id else None,
                        "synchronous_area_id": int(synchronous_area_id) if synchronous_area_id else None,
                    })
                except ValueError as e:
                    raise ValueError(
                        f"Ошибка обработки данных: "
                        f"regional_district_id={regional_district_id}, "
                        f"region_id={region_id}, "
                        f"name={regional_district_name}, "
                        f"name_full={regional_district_full_name}, "
                        f"federal_district_id={federal_district_id}, "
                        f"energy_zone_id={energy_zone_id}, "
                        f"synchronous_area_id={synchronous_area_id}. "
                        f"Ошибка: {e}"
                    )
            
            # Проверка на дублирующиеся IDs
            ids = [record["regional_district_id"] for record in regional_district_data if record["regional_district_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID: {duplicates}")

            # Обновление данных в базе
            update_regional_district_service(regional_district_data, user)
            flash("Изменения успешно сохранены.", "success")
            
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных: {e}", entity_type="regional_district")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.regional_district_list", 
                                page=page, 
                                per_page=per_page, 
                                regional_district_filter=regional_district_filter,
                                federal_district_filter=federal_district_filter,
                                energy_zone_filter=energy_zone_filter,
                                synchronous_area_filter=synchronous_area_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_regional_district_list(
                                page=page, 
                                per_page=per_page, 
                                regional_district_filter=regional_district_filter,
                                federal_district_filter=federal_district_filter,
                                energy_zone_filter=energy_zone_filter,
                                synchronous_area_filter=synchronous_area_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir,
                                )

    # Подготовка данных для формы с фильтрацией по версии БД
    from app.refdata.models.territories.federal_district_model import FederalDistrict
    form.federal_district.choices = choices_cache.get_choices(FederalDistrict, FederalDistrict.id)

    # Энергозоны — для формы (пары) и для таблицы (тройки) с фильтрацией по версии БД
    from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
    energy_zones = get_energy_zone_list_full()
    form.energy_zone.choices = [(ez.id, f"{ez.number} ({ez.name})") for ez in energy_zones]
    energy_zone_list = [(ez.id, ez.number, ez.name) for ez in energy_zones]

    # Синхронные зоны с фильтрацией по версии БД
    from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
    synchronous_areas = get_synchronous_area_list_full()
    form.synchronous_area.choices = [(sa.id, f"{sa.number} ({sa.name})") for sa in synchronous_areas]
    synchronous_area_list = [(sa.id, sa.number, sa.name) for sa in synchronous_areas]

    return render_template(
        "refdata/territories/regional_district/regional_district.html",
        form=form,
        regional_districts_list=pagination.items,
        pagination=pagination,
        federal_district_list=form.federal_district.choices,
        energy_zone_list=energy_zone_list,
        synchronous_area_list=synchronous_area_list,
        regional_district_filter=regional_district_filter,
        federal_district_filter=federal_district_filter,
        energy_zone_filter=energy_zone_filter,
        synchronous_area_filter=synchronous_area_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_regional_district", methods=["GET", "POST"])
@login_required
def add_regional_district():
    """ Маршрут для добавления нового субъекта РФ."""

    user = session.get("username", "Неизвестный пользователь")
    log_to_db(user, "Открыта страница добавления субъекта РФ", entity_type="regional_district")

    # Создание формы
    form = AddRegionalDistrictForm()

    # Сохранение текущих фильтров и параметров отображения
    page                        = request.args.get("page", 1, type=int)
    per_page                    = request.args.get("per_page", 20, type=int)
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    regional_district_filter    = request.args.get("regional_district_filter", "").strip()
    federal_district_filter     = request.args.get("federal_district_filter", "").strip()
    energy_zone_filter          = request.args.get("energy_zone_filter", "").strip()
    synchronous_area_filter     = request.args.get("synchronous_area_filter", "").strip()
    
    # Подготовка данных для формы с фильтрацией по версии БД
    from app.refdata.models.territories.federal_district_model import FederalDistrict
    form.federal_district.choices = choices_cache.get_choices(FederalDistrict, FederalDistrict.id)

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/territories/regional_district/regional_district_add.html",
                form=form
            )
        
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
                "name_full": (form.name_full.data or "").strip(),
                "name_rp": (form.name_rp.data or "").strip(),
                "name_dp": (form.name_dp.data or "").strip(),
                "federal_district_id": form.federal_district.data,
            }]

            # Добавление новой записи через сервис
            add_regional_district_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = regional_district_query(
                                regional_district_filter, 
                                federal_district_filter, 
                                energy_zone_filter, 
                                synchronous_area_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.regional_district_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                regional_district_filter=regional_district_filter,
                federal_district_filter=federal_district_filter,
                energy_zone_filter=energy_zone_filter,
                synchronous_area_filter=synchronous_area_filter,
            ))

        except ValueError as e:
             # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления нового субъекта РФ", str(e), entity_type="regional_district")
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления нового субъекта РФ", str(e), entity_type="regional_district")

    # Рендеринг формы
    return render_template(
        "refdata/territories/regional_district/regional_district_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        federal_district=form.federal_district.choices,
        regional_district_filter=regional_district_filter,
        federal_district_filter=federal_district_filter,
        energy_zone_filter=energy_zone_filter,
        synchronous_area_filter=synchronous_area_filter,
    )


@refdata_bp.route("/import_regional_district", methods=["POST"])
@login_required
def import_regional_district():
    """Маршрут для импорта данных из Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт списка субъектов РФ из Excel", entity_type="regional_district")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("refdata_bp.regional_district_list"))

    file = request.files['file']

    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("refdata_bp.regional_district_list"))  # ← добавлен return

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("refdata_bp.regional_district_list"))

    try:
        imported_count = import_regional_district_service(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("refdata_bp.regional_district_list"))


@refdata_bp.route("/export_regional_district", methods=["GET"])
@login_required
def export_regional_district():
    """ Маршрут для экспорта субъектов РФ в Excel. """

    user = session.get('username', 'Неизвестный пользователь')

    sort_by                  = request.args.get("sort_by", "id")
    sort_dir                 = request.args.get("sort_dir", "asc")
    regional_district_filter = request.args.get("regional_district_filter", "").strip()
    federal_district_filter  = request.args.get("federal_district_filter", "").strip()
    energy_zone_filter       = request.args.get("energy_zone_filter", "").strip()
    synchronous_area_filter  = request.args.get("synchronous_area_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_regional_district_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        regional_district_filter=regional_district_filter,
                        federal_district_filter=federal_district_filter,
                        energy_zone_filter=energy_zone_filter,
                        synchronous_area_filter=synchronous_area_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.regional_district_list"))
        
        # Формирование имени файла
        filename = f"regional_district_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        # Возврат файла через send_file
        return send_file(
            excel_data,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            max_age=0,
        )


    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта: {e}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("refdata_bp.regional_district_list"))