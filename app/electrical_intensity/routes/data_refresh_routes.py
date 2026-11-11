"""Ручное обновление и проверка актуальности страницы электроемкости."""

from datetime import datetime, timezone

from flask import g, jsonify, request, url_for
from flask_login import current_user, login_required

from app.common.services.database_version_filter import get_current_db_version_id
from app.common.services.economics_fd_data_cache import invalidate_economics_fd_data_cache
from app.electrical_intensity.routes.electrical_intensity_root_bp import (
    electrical_intensity_root_bp,
)
from app.electrical_intensity.services.data_refresh_services import (
    get_electrical_intensity_data_revision,
)

_PAGE_ENDPOINT = "electrical_intensity_root_bp.electrical_intensity"


def _revision() -> str:
    return f"{get_current_db_version_id()}:data:{get_electrical_intensity_data_revision()}"


@electrical_intensity_root_bp.before_request
def capture_page_revision() -> None:
    if request.endpoint == _PAGE_ENDPOINT and current_user.is_authenticated:
        g.electrical_intensity_page_revision = _revision()


@electrical_intensity_root_bp.context_processor
def inject_data_refresh() -> dict:
    if request.endpoint != _PAGE_ENDPOINT or "electrical_intensity_page_revision" not in g:
        return {}
    return {
        "electrical_intensity_refresh": {
            "revision": g.electrical_intensity_page_revision,
            "loadedAt": datetime.now(timezone.utc).isoformat(),
            "statusUrl": url_for("electrical_intensity_root_bp.data_revision"),
            "refreshUrl": url_for("electrical_intensity_root_bp.refresh_data"),
        }
    }


@electrical_intensity_root_bp.after_request
def prevent_stale_page_response(response):
    if request.endpoint in (_PAGE_ENDPOINT, "electrical_intensity_root_bp.data_revision"):
        response.headers["Cache-Control"] = "no-store, private"
    return response


@electrical_intensity_root_bp.route("/data-revision/", methods=["GET"])
@login_required
def data_revision():
    response = jsonify(ok=True, revision=_revision())
    response.headers["Cache-Control"] = "no-store, private"
    return response


@electrical_intensity_root_bp.route("/refresh-data/", methods=["POST"])
@login_required
def refresh_data():
    invalidate_economics_fd_data_cache(get_current_db_version_id())
    response = jsonify(ok=True, revision=_revision())
    response.headers["Cache-Control"] = "no-store, private"
    return response
