from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_backfill_preserves_events_and_can_be_reapplied_and_reversed(monkeypatch, legacy_migration):
    migration = legacy_migration("lg26102601_add_log_module")
    monkeypatch.setattr(migration, "SCHEMA_LOGS", None)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE TABLE logs (id INTEGER PRIMARY KEY, entity_type VARCHAR(50), "
            "action VARCHAR(500), details TEXT)"
        ))
        original = [
            {"entity_type": "rational_structure", "action": "Изменены характеристики", "details": "было → стало"},
            {"entity_type": "station", "action": "Изменение", "details": "endpoint=energy_consumption_bp.save"},
            {"entity_type": "page", "action": "Открыта страница", "details": "url=/fuel/calculation"},
            {"entity_type": None, "action": "Обновление p_rasp электростанции", "details": None},
            {"entity_type": None, "action": "Успешный вход в систему", "details": None},
            {"entity_type": None, "action": "Неизвестное старое событие", "details": None},
            {"entity_type": "power_demand_summary_oes", "action": "Изменение", "details": None},
        ]
        connection.execute(sa.text("INSERT INTO logs (entity_type, action, details) "
                                   "VALUES (:entity_type, :action, :details)"), original)
        operations = Operations(MigrationContext.configure(connection))

        # SQLite changes column nullability/default through table recreation.
        def alter_column(table, column, **kwargs):
            with operations.batch_alter_table(table) as batch:
                kwargs.pop("schema", None)
                batch.alter_column(column, **kwargs)

        monkeypatch.setattr(migration, "op", operations)
        monkeypatch.setattr(operations, "alter_column", alter_column)
        migration.upgrade()
        migration.upgrade()
        records = connection.execute(sa.text("SELECT * FROM logs ORDER BY id")).mappings().all()
        assert [record["module"] for record in records] == [
            "Рациональная структура", "Спрос", "Топливо", "Генерация", "Авторизация", "Система", "Нагрузки",
        ]
        assert [{key: record[key] for key in ("entity_type", "action", "details")} for record in records] == original
        inspector = sa.inspect(connection)
        column = next(column for column in inspector.get_columns("logs") if column["name"] == "module")
        assert column["nullable"] is False
        assert any(index["column_names"] == ["module"] for index in inspector.get_indexes("logs"))
        connection.execute(sa.text("INSERT INTO logs (action) VALUES ('Raw SQL event')"))
        assert connection.execute(sa.text("SELECT module FROM logs ORDER BY id DESC LIMIT 1")).scalar() == "Система"
        migration.downgrade()
        assert "module" not in {column["name"] for column in sa.inspect(connection).get_columns("logs")}
        assert connection.execute(sa.text("SELECT count(*) FROM logs")).scalar() == 8
