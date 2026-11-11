from http.client import HTTPException
from urllib.error import HTTPError, URLError

from flask import abort, current_app, jsonify, render_template, request
from flask_login import login_required

from app.rational_structure.routes import rational_structure_module_bp
from app.rational_structure.services.calculated_values_services import (
    RESULT_DATASETS,
    fetch_calculated_values,
)


@rational_structure_module_bp.route("/calculated_values/<dataset_key>")
@login_required
def calculated_values(dataset_key):
    if dataset_key not in RESULT_DATASETS:
        abort(404)
    result = None
    error = None
    status = 200
    wants_json = request.accept_mimetypes.best == "application/json"
    if wants_json or request.args.get("load") == "1":
        try:
            result = fetch_calculated_values(dataset_key)
        except TimeoutError:
            current_app.logger.warning("Тайм-аут API рассчитанных значений: %s", dataset_key, exc_info=True)
            error = "Превышено время ожидания API. Повторите загрузку позже."
            status = 504
        except HTTPError as exc:
            current_app.logger.warning("Ошибка HTTP API рассчитанных значений: %s", dataset_key, exc_info=True)
            error = f"API вернул ошибку HTTP {exc.code}. Повторите загрузку позже."
            status = 502
        except (URLError, OSError, HTTPException):
            current_app.logger.warning("API рассчитанных значений недоступен: %s", dataset_key, exc_info=True)
            error = "Не удалось подключиться к API. Проверьте доступность сервиса и повторите загрузку."
            status = 502
        except ValueError:
            current_app.logger.warning("Некорректный ответ API рассчитанных значений: %s", dataset_key, exc_info=True)
            error = "API вернул некорректные данные. Повторите загрузку позже."
            status = 502
    if wants_json:
        if error:
            return jsonify(error=error), status
        return jsonify(html=render_template(
            "rational_structure/_calculated_values_table.html",
            definition=RESULT_DATASETS[dataset_key],
            dataset_key=dataset_key,
            result=result,
        ))
    return render_template(
        "rational_structure/calculated_values.html",
        page_title=RESULT_DATASETS[dataset_key]["title"],
        dataset_key=dataset_key,
        result_datasets=RESULT_DATASETS,
        result=result,
        error=error,
    ), status
