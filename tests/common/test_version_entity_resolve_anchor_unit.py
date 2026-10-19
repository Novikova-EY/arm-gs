from types import SimpleNamespace

from app.common.services import version_entity_resolve_services
from app.fuel.models.fue_equipment_group_model import EquipmentGroup


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _FakeSession:
    """Возвращает подготовленную строку на любой запрос (фильтры не разбираем)."""

    def __init__(self, result):
        self._result = result

    def query(self, *args, **kwargs):
        return _FakeQuery(self._result)


def test_load_by_id_with_version_or_anchor_returns_resolved_row(monkeypatch):
    """Строка текущей версии найдена — якорную не подставляем."""
    resolved = SimpleNamespace(id=30555, database_version_id=37)
    monkeypatch.setattr(
        version_entity_resolve_services, "load_by_id_with_version", lambda *a, **k: resolved
    )
    monkeypatch.setattr(
        version_entity_resolve_services.db,
        "session",
        _FakeSession(SimpleNamespace(id=14693, database_version_id=None)),
    )

    assert (
        version_entity_resolve_services.load_by_id_with_version_or_anchor(
            EquipmentGroup, 14693, 37
        )
        is resolved
    )


def test_load_by_id_with_version_or_anchor_falls_back_to_anchor(monkeypatch):
    """Группы нет в текущей версии — открываем саму запись, а не 404."""
    anchor = SimpleNamespace(id=14693, database_version_id=None)
    monkeypatch.setattr(
        version_entity_resolve_services, "load_by_id_with_version", lambda *a, **k: None
    )
    monkeypatch.setattr(
        version_entity_resolve_services.db, "session", _FakeSession(anchor)
    )

    assert (
        version_entity_resolve_services.load_by_id_with_version_or_anchor(
            EquipmentGroup, 14693, 37
        )
        is anchor
    )


def test_load_by_id_with_version_or_anchor_falls_back_through_query_factory(monkeypatch):
    anchor = SimpleNamespace(id=14693, database_version_id=None)
    monkeypatch.setattr(
        version_entity_resolve_services, "load_by_id_with_version", lambda *a, **k: None
    )

    assert (
        version_entity_resolve_services.load_by_id_with_version_or_anchor(
            EquipmentGroup, 14693, 37, query_factory=lambda: _FakeQuery(anchor)
        )
        is anchor
    )


def test_load_by_id_with_version_or_anchor_returns_none_for_missing_id(monkeypatch):
    """Ни текущей версии, ни якоря — по-прежнему None (роут отдаст 404)."""
    monkeypatch.setattr(
        version_entity_resolve_services, "load_by_id_with_version", lambda *a, **k: None
    )
    monkeypatch.setattr(
        version_entity_resolve_services.db, "session", _FakeSession(None)
    )

    assert (
        version_entity_resolve_services.load_by_id_with_version_or_anchor(
            EquipmentGroup, 999999, 37
        )
        is None
    )
