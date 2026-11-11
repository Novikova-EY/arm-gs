from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select

from app.logs.models.data_refresh_event_model import DataRefreshEvent, DataRefreshState
from config import SCHEMA_LOGS


def test_migration_upgrade_downgrade_and_graph(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "migrations/alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_current_head() == "gs26110301"
    assert scripts.get_revision("gs26110301").down_revision == "gs26110202"

    spec = spec_from_file_location("refresh_history_migration", root / "migrations/versions/gs26110301_data_refresh_events.py")
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://", execution_options={"schema_translate_map": {SCHEMA_LOGS: None}})
    with engine.begin() as connection:
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        state = connection.execute(select(DataRefreshState.__table__)).mappings().one()
        assert state["revision"] == 0
        assert len(state["epoch"]) == 36
        assert {column["name"] for column in inspect(connection).get_columns("gs_data_refresh_events")} == set(DataRefreshEvent.__table__.columns.keys())
        migration.downgrade()
        assert inspect(connection).get_table_names() == []
    engine.dispose()
