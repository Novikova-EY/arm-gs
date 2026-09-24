# -*- coding: utf-8 -*-
"""Проверки таблицы выработки от собственника (ВЭС/СЭС) на карточке станции."""
from types import SimpleNamespace

from app.generation.services.station_services.station_type_flags import (
    is_gaes_station,
    is_ges_station,
    is_ves_or_ses_station,
)


def _station(type_name):
    return SimpleNamespace(station_type=SimpleNamespace(name=type_name))


def test_ves_and_ses_are_detected():
    assert is_ves_or_ses_station(_station("ВЭС")) is True
    assert is_ves_or_ses_station(_station("СЭС")) is True
    assert is_ves_or_ses_station(_station("вэс")) is True
    assert is_ves_or_ses_station(_station("ВЭС (Р)")) is True
    assert is_ves_or_ses_station(_station("СЭС (Р)")) is True


def test_other_station_types_are_not_ves_ses():
    assert is_ves_or_ses_station(_station("ТЭС")) is False
    assert is_ves_or_ses_station(_station("ГАЭС")) is False
    assert is_ves_or_ses_station(_station("ГЭС")) is False
    assert is_ves_or_ses_station(_station(None)) is False
    assert is_ves_or_ses_station(SimpleNamespace(station_type=None)) is False


def test_gaes_detection_unchanged():
    assert is_gaes_station(_station("ГАЭС")) is True
    assert is_gaes_station(_station("ВЭС")) is False


def test_ges_detection():
    assert is_ges_station(_station("ГЭС")) is True
    assert is_ges_station(_station("гэс")) is True
    assert is_ges_station(_station("ГАЭС")) is False
    assert is_ges_station(_station("ТЭС")) is False


def test_clearing_zero_energy_is_detected_as_change():
    from app.generation.services.station_services.station_services import (
        _station_numeric_field_changed,
    )

    assert _station_numeric_field_changed("", "0,0") is True
    assert _station_numeric_field_changed("", "0.0") is True
    assert _station_numeric_field_changed("0", "") is True
    assert _station_numeric_field_changed("0,0", "0.0") is False
    assert _station_numeric_field_changed("", "") is False
