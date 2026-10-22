# -*- coding: utf-8 -*-
"""
Централизованное логирование открытия HTML-страниц модулей.

Пишет «Открыта страница: …» для каждого document-навигационного GET.
Маршруты, которые уже вызывают log_to_db с таким префиксом, не дублируются.
"""
from __future__ import annotations

import html as html_lib
import re
from typing import Optional

from flask import current_app, g, has_request_context, request
from flask_login import current_user

from app.logs.services import logging_service as logging_service_mod
from app.logs.services.logging_service import PAGE_VIEW_ACTION_PREFIX

# Заголовок из base.html, если страница не задала свой {% block title %}
_DEFAULT_DOCUMENT_TITLES = frozenset({"АРМ ГС", "АРМ ГС –"})

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

SKIP_ENDPOINTS = frozenset(
    {
        "static",
        "chrome_devtools_config",
        "auth.login",
        "auth.register",
    }
)

SKIP_ENDPOINT_SUBSTRINGS = (
    ".api_",
    "/api/",
)

SKIP_PATH_PREFIXES = (
    "/static/",
    "/api/",
    "/.well-known/",
)

MODULE_LABELS = {
    "start": "Главная",
    "auth": "Авторизация",
    "users_bp": "Пользователи",
    "refdata_bp": "Справочники",
    "generation_bp": "Генерация",
    "station_bp": "Генерация",
    "station_changes_bp": "Генерация",
    "prospective_places_bp": "Генерация",
    "rational_structure_bp": "Рациональная структура",
    "fuel_bp": "Топливо",
    "power_demand_bp": "Нагрузки",
    "energy_consumption_bp": "Спрос",
    "long_term_consumption_bp": "Долгосрочный прогноз потребления",
    "electrical_intensity_root_bp": "Долгосрочный прогноз потребления",
    "energy_balance_bp": "Балансы электрической энергии и мощности",
    "ecology_bp": "Экология",
    "economics_bp": "Экономика",
    "territories_bp": "Характеристики территорий",
    "logs": "Журнал",
    "history_bp": "История",
    "perimeter_variant_bp": "Варианты сценариев",
    "year_management": "Справочники",
}


def init_page_view_logging(app) -> None:
    """Регистрирует after_request: лог входа пользователя на HTML-страницу."""

    @app.after_request
    def log_html_page_view(response):
        try:
            maybe_log_page_view(response)
        except Exception as exc:
            try:
                current_app.logger.warning("page_view_logging error: %r", exc)
            except Exception:
                pass
        return response


def maybe_log_page_view(response) -> None:
    if not should_log_page_view(request, response):
        return

    title = _page_title_for_log(request, response)
    action = f"{PAGE_VIEW_ACTION_PREFIX}: {title}"
    module = module_label_for_endpoint(request.endpoint)
    details_parts = [f"url={request.full_path}"]
    if request.endpoint:
        details_parts.append(f"endpoint={request.endpoint}")
    if module:
        details_parts.append(f"module={module}")

    logging_service_mod.log_to_db(
        current_user,
        action,
        details="; ".join(details_parts),
        entity_type="page",
    )


def should_log_page_view(req, response) -> bool:
    if not has_request_context():
        return False
    if getattr(g, "page_view_logged", False):
        return False
    if not _is_authenticated_user():
        return False
    if (req.method or "").upper() != "GET":
        return False
    if getattr(response, "status_code", None) != 200:
        return False
    if not _is_html_response(response):
        return False
    if getattr(response, "direct_passthrough", False):
        return False
    if _is_attachment(response):
        return False
    if not _is_document_navigation(req):
        return False
    if not _is_loggable_endpoint(req):
        return False
    if not _looks_like_full_html_page(response):
        return False
    return True


def module_label_for_endpoint(endpoint: Optional[str]) -> str:
    if not endpoint or "." not in endpoint:
        blueprint = (endpoint or "").strip()
    else:
        blueprint = endpoint.rsplit(".", 1)[0]
    return MODULE_LABELS.get(blueprint, "")


def extract_html_title(markup: str) -> str:
    if not markup:
        return ""
    match = _TITLE_RE.search(markup)
    if not match:
        return ""
    raw = match.group(1)
    raw = _TAG_RE.sub(" ", raw)
    raw = html_lib.unescape(raw)
    return _WS_RE.sub(" ", raw).strip()


def _is_authenticated_user() -> bool:
    try:
        return bool(getattr(current_user, "is_authenticated", False))
    except Exception:
        return False


def _is_html_response(response) -> bool:
    content_type = (getattr(response, "content_type", None) or "").lower()
    return "text/html" in content_type


def _is_attachment(response) -> bool:
    disposition = ""
    try:
        disposition = (response.headers.get("Content-Disposition") or "").lower()
    except Exception:
        return False
    return "attachment" in disposition


def _is_document_navigation(req) -> bool:
    dest = (req.headers.get("Sec-Fetch-Dest") or "").strip().lower()
    if dest:
        return dest == "document"
    if (req.headers.get("X-Requested-With") or "").lower() == "xmlhttprequest":
        return False
    accept = (req.headers.get("Accept") or "").lower()
    if not accept or accept.startswith("*/*"):
        # Тестовый клиент и старые браузеры: решаем по полному HTML-ответу.
        return True
    first = accept.split(",", 1)[0].strip()
    return first.startswith("text/html") or "text/html" in first


def _is_loggable_endpoint(req) -> bool:
    endpoint = req.endpoint or ""
    if not endpoint or endpoint in SKIP_ENDPOINTS:
        return False
    path = req.path or ""
    if any(path.startswith(prefix) for prefix in SKIP_PATH_PREFIXES):
        return False
    combined = f"{endpoint} {path}"
    if any(token in combined for token in SKIP_ENDPOINT_SUBSTRINGS):
        return False
    return True


def _response_head(response, limit: int = 16384) -> str:
    try:
        raw = response.get_data()
    except Exception:
        return ""
    if not raw:
        return ""
    if isinstance(raw, bytes):
        return raw[:limit].decode("utf-8", errors="ignore")
    return str(raw)[:limit]


def _looks_like_full_html_page(response) -> bool:
    head = _response_head(response).lower()
    if not head:
        return False
    return "<html" in head or "<title" in head


def _page_title_for_log(req, response) -> str:
    title = extract_html_title(_response_head(response))
    if title and title not in _DEFAULT_DOCUMENT_TITLES:
        return title

    module = module_label_for_endpoint(req.endpoint)
    view_name = _humanize_endpoint(req.endpoint)
    if module and view_name:
        return f"{module} – {view_name}"
    if module:
        return module
    if view_name:
        return view_name
    path = (req.path or "").strip("/") or "/"
    return path


def _humanize_endpoint(endpoint: Optional[str]) -> str:
    if not endpoint:
        return ""
    view = endpoint.rsplit(".", 1)[-1]
    view = view.replace("_", " ").strip()
    return view
