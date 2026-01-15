from . import generation_bp
from flask import render_template, request, current_app
from flask_login import login_required


@generation_bp.route("/totals_summary")
@login_required
def totals_summary():
    """Маршрут для отображения итоговых сумм по ЕЭС, ТИТЭС и России.
    Оптимизирован: загружает только агрегированные данные без станций."""
    # Ленивые импорты для ускорения загрузки других страниц
    from config import Config
    from app.generation.services.station_services.station_services import get_filtered_station_ids
    from app.generation.services.station_services.aggregation_station_services.aggregation_rows import get_full_aggregation_rows
    from app.generation.services.station_services.aggregation_station_services.optimized_aggregation import aggregate_all_at_once
    from app.generation.services.station_services.station_services import (
        build_energy_system_type_aggregates,
        build_total_energy_system_type_aggregates,
        build_synchronous_area_aggregates,
        build_federal_district_aggregates,
    )
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_list_full,
        get_energy_system_type_map,
    )
    from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
        get_synchronous_area_list_full,
    )
    from app.common.services.get_services.years.year_feature_services import get_year_feature_dict
    from app.common.services.get_services.years.years_get_services import (
        get_filter_start_year,
        get_filter_end_year,
    )
    from app.common.services.get_services.territories.federal_district_get_services import (
        get_federal_district_list_full,
        get_federal_districts_map,
    )

    import time
    start_data = time.time()

    # Получение параметров запроса (только минимальные фильтры)
    start_year = request.args.get("start_year", type=int) or get_filter_start_year()
    end_year = request.args.get("end_year", type=int) or get_filter_end_year()
    # По умолчанию Рогр и Ррасп скрыты
    show_p_ogr = request.args.get("show_p_ogr", "0") == "1"
    show_p_rasp = request.args.get("show_p_rasp", "0") == "1"
    # Типы агрегации: можно выбрать несколько (ees, tites, russia)
    # По умолчанию только ees
    aggregation_types = request.args.getlist("aggregation_type")
    if not aggregation_types:
        aggregation_types = ["ees"]  # По умолчанию только ЕЭС
    # Фильтруем только допустимые значения (ees, tites, russia, sync_area_{id})
    valid_types = ["fo", "ees", "tites", "russia"]
    # Проверяем также синхронные зоны (формат: "sync_area_{id}")
    filtered_aggregation_types = []
    sync_area_ids = []
    for at in aggregation_types:
        if at in valid_types:
            filtered_aggregation_types.append(at)
        elif at.startswith("sync_area_"):
            try:
                sa_id = int(at.replace("sync_area_", ""))
                sync_area_ids.append(sa_id)
                filtered_aggregation_types.append(at)
            except ValueError:
                pass  # Игнорируем невалидные sync_area_
    aggregation_types = filtered_aggregation_types
    if not aggregation_types:
        aggregation_types = ["ees"]  # Если все невалидные, возвращаемся к умолчанию

    try:
        rounding_digits = int(request.args.get("rounding_digits", 1))
    except (ValueError, TypeError):
        rounding_digits = 1

    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1

    # Минимальные фильтры - только те, что могут влиять на агрегацию
    filters = {}
    # Можно добавить базовые фильтры, если нужно, но для итогов обычно не нужны

    # Получаем ID всех станций по фильтрам (без загрузки самих станций)
    print(f"[TIME] totals_summary: получение station_ids...")
    station_ids = get_filtered_station_ids(filters)
    print(
        f"[TIME] totals_summary: получено {len(station_ids)} station_ids за {time.time() - start_data:.2f} сек"
    )

    # Получаем агрегированные строки напрямую из БД
    print(f"[TIME] totals_summary: получение агрегированных строк...")
    rows_start = time.time()
    rows = get_full_aggregation_rows(start_year, end_year, station_ids, filters)
    print(
        f"[TIME] totals_summary: получено {len(rows)} строк за {time.time() - rows_start:.2f} сек"
    )

    # Выполняем агрегацию
    print(f"[TIME] totals_summary: выполнение агрегации...")
    agg_start = time.time()
    all_aggregations = aggregate_all_at_once(rows)
    print(
        f"[TIME] totals_summary: агрегация выполнена за {time.time() - agg_start:.2f} сек"
    )

    # Получаем данные для шаблона - передаем все необходимые агрегаты
    data = all_aggregations

    # Строим агрегаты для типов энергосистем, России и синхронных зон
    energy_system_type_aggregates = build_energy_system_type_aggregates(data)
    total_energy_system_type_aggregates = build_total_energy_system_type_aggregates(
        data
    )
    synchronous_area_aggregates = build_synchronous_area_aggregates(data)
    federal_district_aggregates = build_federal_district_aggregates(data)

    # Список федеральных округов (порядок: display_order ASC)
    federal_district_list = get_federal_district_list_full()
    federal_district_names = get_federal_districts_map()
    _fd_sorted = sorted(
        federal_district_list,
        key=lambda fd: (
            fd.display_order is None,
            fd.display_order if fd.display_order is not None else 0,
            (fd.name or ""),
            fd.id or 0,
        ),
    )
    sorted_federal_district_ids = [fd.id for fd in _fd_sorted if fd.id]

    # Получаем список типов энергосистем
    energy_system_type_list = get_energy_system_type_list_full()
    energy_system_type_names = get_energy_system_type_map()

    # Сортируем типы энергосистем по ID (это объекты, а не словари)
    sorted_energy_system_type_ids = sorted(
        [est.id for est in energy_system_type_list if est.id]
    )
    
    # Получаем список синхронных зон
    synchronous_area_list = get_synchronous_area_list_full()
    synchronous_area_names = {sa.id: sa.name for sa in synchronous_area_list if sa.id}
    
    # Сортируем синхронные зоны:
    # - синхронная зона Калининградской области (по названию) всегда первой
    # - далее по ID (исключаем id=0 если есть)
    _sa_ids = [sa.id for sa in synchronous_area_list if sa.id and sa.id > 0]
    _kaliningrad_ids = []

    # 1) Надёжный способ: берём sa_id через субъект РФ Калининградской области (номер региона = 39)
    #    -> RegionalDistrict.id_synchronous_area
    try:
        from app.refdata.models.territories.regional_district_model import RegionalDistrict

        rd_query = RegionalDistrict.query
        rd_query = filter_by_db_version(rd_query, RegionalDistrict)
        rd_sa_ids = (
            rd_query.filter(RegionalDistrict.region_number.in_(["39", "039"]))
            .with_entities(RegionalDistrict.id_synchronous_area)
            .all()
        )
        _kaliningrad_ids = [sa_id for (sa_id,) in rd_sa_ids if sa_id]
    except Exception:
        _kaliningrad_ids = []

    # 2) Fallback: пытаемся по названию синхронной зоны (если вдруг нет маппинга на субъекте)
    if not _kaliningrad_ids:
        for _sa in synchronous_area_list:
            try:
                _sid = _sa.id
                _name_l = (_sa.name or "").lower()
            except Exception:
                continue
            if _sid and _sid > 0 and ("калининград" in _name_l):
                _kaliningrad_ids.append(_sid)

    _kaliningrad_ids = sorted(set([i for i in _kaliningrad_ids if i in set(_sa_ids)]))
    _rest_ids = sorted([i for i in _sa_ids if i not in set(_kaliningrad_ids)])
    sorted_synchronous_area_ids = _kaliningrad_ids + _rest_ids

    # Получаем типы станций для шаблона
    from app.refdata.models.refdata_for_stations.station.station_type_model import (
        StationType,
    )
    from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
    from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import (
        TesMachineType,
    )
    from app.refdata.models.fuels.fuel_type_model import FuelType
    from app.common.services.database_version_filter import filter_by_db_version

    station_type_query = StationType.query
    station_type_query = filter_by_db_version(station_type_query, StationType)
    station_type_names = station_type_query.order_by(StationType.id.asc()).all()
    station_type_list = {st.id: st.name for st in station_type_names}

    # Получаем типы ТЭС для шаблона
    tes_type_query = TesType.query
    tes_type_query = filter_by_db_version(tes_type_query, TesType)
    tes_type_names = tes_type_query.order_by(TesType.id.asc()).all()
    tes_type_list = {tt.id: tt.name for tt in tes_type_names}

    # Получаем типы машин ТЭС для шаблона
    tes_machine_type_query = TesMachineType.query
    tes_machine_type_query = filter_by_db_version(
        tes_machine_type_query, TesMachineType
    )
    tes_machine_type_names = tes_machine_type_query.order_by(
        TesMachineType.id.asc()
    ).all()
    tes_machine_type_list = {tmt.id: tmt.name for tmt in tes_machine_type_names}

    # Получаем типы топлива для шаблона
    fuel_type_query = FuelType.query
    fuel_type_query = filter_by_db_version(fuel_type_query, FuelType)
    fuel_type_names = fuel_type_query.order_by(FuelType.id.asc()).all()
    fuel_type_list = {ft.id: ft.name for ft in fuel_type_names}

    # Формируем should_show_totals в зависимости от выбранных типов агрегации
    should_show_totals = {
        "energy_system_types": {},
        "synchronous_areas": {},
        "federal_districts": False,
        "total": False,
    }

    # Проверяем каждый выбранный тип агрегации
    if "russia" in aggregation_types:
        should_show_totals["total"] = True

    if "fo" in aggregation_types:
        should_show_totals["federal_districts"] = True

    # Показываем выбранные типы энергосистем (ЕЭС и/или ТИТЭС)
    for est_id in sorted_energy_system_type_ids:
        es_type_name = energy_system_type_names.get(est_id, "")
        if "ees" in aggregation_types and "ЕЭС" in es_type_name:
            should_show_totals["energy_system_types"][est_id] = True
        if "tites" in aggregation_types and "ТИТЭС" in es_type_name:
            should_show_totals["energy_system_types"][est_id] = True
    
    # Показываем выбранные синхронные зоны (обрабатываем синхронные зоны из aggregation_types)
    # Формат: "sync_area_{id}" или просто проверяем все синхронные зоны, которые есть в данных
    for sa_id in sorted_synchronous_area_ids:
        # Проверяем, есть ли этот ID в aggregation_types
        if f"sync_area_{sa_id}" in aggregation_types:
            should_show_totals["synchronous_areas"][sa_id] = True

    # Получаем year_features
    year_features = get_year_feature_dict()

    # Формируем контекст для шаблона
    context = {
        "start_year": start_year,
        "end_year": end_year,
        "show_p_ogr": show_p_ogr,
        "show_p_rasp": show_p_rasp,
        "rounding_digits": rounding_digits,
        "aggregation_types": aggregation_types,
        "should_show_totals": should_show_totals,
        "sorted_energy_system_type_ids": sorted_energy_system_type_ids,
        "sorted_synchronous_area_ids": sorted_synchronous_area_ids,
        "sorted_federal_district_ids": sorted_federal_district_ids,
        "energy_system_type_list": station_type_list,
        "energy_system_type_names": energy_system_type_names,
        "synchronous_area_names": synchronous_area_names,
        "federal_district_names": federal_district_names,
        "station_type_list": station_type_list,
        "tes_type_list": tes_type_list,
        "tes_machine_type_list": tes_machine_type_list,
        "fuel_type_list": fuel_type_list,
        "year_features": year_features,
        # Агрегированные данные
        **energy_system_type_aggregates,
        **total_energy_system_type_aggregates,
        **synchronous_area_aggregates,
        **federal_district_aggregates,
    }

    overall = time.time() - start_data
    print(f"[TIME] totals_summary загрузка заняла: {overall:.2f} сек")

    return render_template(
        "generation/stations_total_summary/stations_total_summary.html", **context
    )


