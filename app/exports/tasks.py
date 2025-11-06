import os
from datetime import datetime
from pathlib import Path
from typing import Any

from werkzeug.datastructures import MultiDict


def _ensure_exports_dir(base_dir: str) -> str:
    Path(base_dir).mkdir(parents=True, exist_ok=True)
    return base_dir


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _dict_to_multidict(data: dict | None) -> MultiDict:
    pairs: list[tuple[str, Any]] = []
    if not data:
        return MultiDict()
    for key, value in data.items():
        if isinstance(value, list):
            for item in value:
                pairs.append((key, item))
        else:
            pairs.append((key, value))
    return MultiDict(pairs)


def run_export_task(filters: dict | None = None) -> dict:
    """
    Фоновая задача: формирует Excel-выгрузку(и) и сохраняет их на диск.
    Возвращает словарь с путями файлов для скачивания.
    """
    from app import create_app
    from app.generation.services.station_services.export_station_services import (
        export_station_sipr_ees_application_2_service,
        generate_excel_export_with_all_totals,
    )
    from app.generation.services.station_services.station_services import get_station_list_data
    from app.generation.services.station_services.filters_services import extract_filters_from_args
    from config import Config

    export_payload = filters or {}
    export_type = (export_payload.get("export_type") or export_payload.get("_export_type") or "station_list").lower()

    app = create_app()
    saved_files: list[str] = []

    with app.app_context():
        exports_dir = app.config.get("EXPORTS_DIR") or os.path.join(app.instance_path, "exports")
        _ensure_exports_dir(exports_dir)

        def _save_buffer(name: str, buffer) -> str:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = name.replace(" ", "_")
            full_name = f"{ts}_{safe_name}"
            full_path = os.path.join(exports_dir, full_name)
            with open(full_path, "wb") as f:
                f.write(buffer.getbuffer())
            return full_name

        if export_type == "sipr":
            result = export_station_sipr_ees_application_2_service(user="background", filters=export_payload or {})
            if isinstance(result, tuple) and len(result) == 2:
                saved_files.append(_save_buffer(result[0], result[1]))
            elif isinstance(result, list):
                for item in result:
                    if isinstance(item, tuple) and len(item) == 2:
                        saved_files.append(_save_buffer(item[0], item[1]))
        else:
            args_md = _dict_to_multidict(export_payload)
            filters_for_query = extract_filters_from_args(args_md)

            start_year = args_md.get("start_year", default=Config.START_YEAR, type=int)
            end_year = args_md.get("end_year", default=Config.END_YEAR, type=int)
            rounding_raw = args_md.get("rounding_digits", default="1")

            try:
                rounding_digits = int(rounding_raw)
                if rounding_digits == 0:
                    rounding_digits = None
            except (ValueError, TypeError):
                rounding_digits = 1

            show_p_ogr = _to_bool(args_md.get("show_p_ogr", default="0"))
            show_p_rasp = _to_bool(args_md.get("show_p_rasp", default="1"))
            hide_aggregates = _to_bool(args_md.get("hide_aggregates", default="0"))
            show_totals = _to_bool(args_md.get("show_totals", default="0"))

            data = get_station_list_data(
                filters=filters_for_query,
                per_page="all",
                page=1,
                rounding_digits=rounding_digits,
                start_year=start_year,
                end_year=end_year,
                show_p_ogr=show_p_ogr,
                show_p_rasp=show_p_rasp,
                show_all=True,
                show_totals=True,
            )

            rows = data.get("rows", [])
            excel_buffer = generate_excel_export_with_all_totals(
                data=data,
                rows=rows,
                start_year=start_year,
                end_year=end_year,
                rounding_digits=rounding_digits,
                show_p_ogr=show_p_ogr,
                show_p_rasp=show_p_rasp,
                hide_aggregates=hide_aggregates,
                show_totals=show_totals,
            )
            saved_files.append(_save_buffer("stations_export.xlsx", excel_buffer))

    try:
        from rq import get_current_job  # type: ignore
        job = get_current_job()
    except Exception:
        job = None
    return {
        "job_id": job.id if job else None,
        "files": saved_files,
    }


