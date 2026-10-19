# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.energy_balance.services.access_services import can_edit_energy_balance

energy_balance_bp = Blueprint("energy_balance_bp", __name__)

# POST на этих страницах только применяет фильтры и перенаправляет на GET.
_FILTER_POST_ENDPOINTS = frozenset(
    {"energy_balance_bp.ee_generation", "energy_balance_bp.ee_transfers"}
)


@energy_balance_bp.before_request
def require_energy_balance_edit_permission():
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    if request.method == "POST" and request.endpoint in _FILTER_POST_ENDPOINTS:
        return None
    if not can_edit_energy_balance(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    return None


@energy_balance_bp.context_processor
def inject_energy_balance_permissions():
    return {"can_edit_energy_balance": can_edit_energy_balance(current_user)}
