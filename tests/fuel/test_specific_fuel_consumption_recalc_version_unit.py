# -*- coding: utf-8 -*-
"""Пересчёт удельных: только текущая версия БД при all_versions=False."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.fuel.services.equipment_groups import (
    equipment_group_specific_fuel_consumption_recalc_services as svc,
)


class _FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        matched = [
            r
            for r in self.rows
            if all(getattr(r, k, None) == v for k, v in kwargs.items())
        ]
        return _FakeQuery(matched)

    def with_entities(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


def _model_ns(query, **cols):
    """Модель с .query и колонками-заглушками для SQLAlchemy-выражений в filter()."""
    ns = SimpleNamespace(query=query, **cols)
    return ns


def test_recalculate_all_versions_false_scopes_to_current_version_only():
    """При all_versions=False пересчитывается только ГО текущей версии."""
    current_vid = 37

    current_eg = SimpleNamespace(id=100, database_version_id=current_vid)
    other_eg = SimpleNamespace(id=200, database_version_id=20)

    current_param = SimpleNamespace(
        equipment_group_id=100,
        year_number=2024,
        database_version_id=current_vid,
    )
    other_param = SimpleNamespace(
        equipment_group_id=200,
        year_number=2024,
        database_version_id=20,
    )

    class _EgQuery(_FakeQuery):
        def filter(self, *args, **kwargs):
            return _EgQuery(
                [r for r in self.rows if r.database_version_id == current_vid]
            )

    class _FuelParamQuery(_FakeQuery):
        def all(self):
            return [
                r
                for r in self.rows
                if r.database_version_id == current_vid
                and r.equipment_group_id == current_eg.id
            ]

    existing = SimpleNamespace(
        equipment_group_id=100,
        year_number=2024,
        database_version_id=current_vid,
        k=None,
        y_calc=None,
        btp_calc=None,
        sntp_calc=None,
        bk_calc=None,
        snk_calc=None,
    )

    session = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    session.no_autoflush = cm

    fuel_param_model = _model_ns(
        _FuelParamQuery([current_param, other_param]),
        year_number=object(),
        database_version_id=object(),
        equipment_group_id=object(),
    )
    # Сравнения Model.col == x в filter() не должны падать
    for name in ("year_number", "database_version_id", "equipment_group_id"):
        col = MagicMock(name=name)
        col.__eq__ = lambda self, other, n=name: (n, other)
        setattr(fuel_param_model, name, col)

    eg_model = _model_ns(
        _EgQuery([current_eg, other_eg]),
        id=object(),
        database_version_id=MagicMock(),
    )
    eg_model.database_version_id.__eq__ = lambda self, other: ("database_version_id", other)
    eg_model.database_version_id.is_ = lambda self, v: ("is_", v)

    with patch.object(svc, "get_current_db_version_id", return_value=current_vid), patch.object(
        svc, "EquipmentGroupFuelParam", fuel_param_model
    ), patch.object(svc, "EquipmentGroup", eg_model), patch.object(
        svc,
        "EquipmentGroupSpecificFuelConsumption",
        SimpleNamespace(query=_FakeQuery([existing])),
    ), patch.object(svc, "db", SimpleNamespace(session=session)), patch.object(
        svc, "calc_y_calc", return_value=1
    ), patch.object(svc, "calc_btp_calc", return_value=2), patch.object(
        svc, "calc_sntp_calc", return_value=3
    ), patch.object(svc, "calc_bk_calc", return_value=4), patch.object(
        svc, "calc_snk_calc", return_value=5
    ), patch.object(svc, "_sync_numb1120_from_equipment_group", return_value={}), patch.object(
        svc, "set_db_version_on_create", lambda obj: None
    ):
        updated = svc.recalculate_all_specific_fuel_consumption_calc(
            year=2024, all_versions=False, commit=False
        )

    assert updated == 1
    assert existing.y_calc == 1
    assert existing.btp_calc == 2
    assert existing.sntp_calc == 3
    assert existing.bk_calc == 4
    assert existing.snk_calc == 5


def test_recalculate_all_versions_true_processes_all_version_params():
    """all_versions=True обрабатывает параметры всех версий, без фильтра ГО."""
    params = [
        SimpleNamespace(equipment_group_id=100, year_number=2024, database_version_id=37),
        SimpleNamespace(equipment_group_id=200, year_number=2024, database_version_id=20),
    ]
    created = []

    class _ConsumptionCls:
        query = _FakeQuery([])

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            created.append(self)

    session = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    session.no_autoflush = cm
    session.add = lambda obj: None

    fuel_param_model = _model_ns(
        _FakeQuery(params),
        year_number=MagicMock(),
        database_version_id=MagicMock(),
        equipment_group_id=MagicMock(),
    )
    for name in ("year_number", "database_version_id", "equipment_group_id"):
        col = MagicMock(name=name)
        col.__eq__ = lambda self, other, n=name: (n, other)
        setattr(fuel_param_model, name, col)

    with patch.object(svc, "get_current_db_version_id", return_value=37), patch.object(
        svc, "EquipmentGroupFuelParam", fuel_param_model
    ), patch.object(
        svc, "EquipmentGroupSpecificFuelConsumption", _ConsumptionCls
    ), patch.object(svc, "db", SimpleNamespace(session=session)), patch.object(
        svc, "calc_y_calc", return_value=1
    ), patch.object(svc, "calc_btp_calc", return_value=2), patch.object(
        svc, "calc_sntp_calc", return_value=3
    ), patch.object(svc, "calc_bk_calc", return_value=4), patch.object(
        svc, "calc_snk_calc", return_value=5
    ), patch.object(svc, "_sync_numb1120_from_equipment_group", return_value={}), patch.object(
        svc, "set_db_version_on_create", lambda obj: None
    ):
        with patch.object(svc, "EquipmentGroup") as eg_model:
            eg_model.query = MagicMock()
            updated = svc.recalculate_all_specific_fuel_consumption_calc(
                year=2024, all_versions=True, commit=False
            )
            eg_model.query.filter.assert_not_called()

    assert updated == 2
    assert {c.equipment_group_id for c in created} == {100, 200}
    assert {c.database_version_id for c in created} == {37, 20}
