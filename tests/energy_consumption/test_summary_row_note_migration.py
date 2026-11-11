from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_notes_table_can_be_added_to_legacy_history_and_upgrade_repeated():
    path = Path(__file__).resolve().parents[2] / "migrations/versions/gs26110202_energy_consumption_summary_row_notes.py"
    spec = spec_from_file_location("notes_migration", path)
    revision = module_from_spec(spec)
    spec.loader.exec_module(revision)
    revision.SCHEMA_ENERGY_CONSUMPTION = None
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            connection.execute(text("INSERT INTO alembic_version VALUES ('legacy_revision')"))
            with Operations.context(MigrationContext.configure(connection)):
                revision.upgrade()
                connection.execute(text(
                    "INSERT INTO gs_ec_summary_row_notes (database_version_id, row_key, note) "
                    "VALUES (1, :key, 'Keep this note')"
                ), {"key": "a" * 64})
                revision.upgrade()
            assert set(inspect(connection).get_table_names()) == {"alembic_version", "gs_ec_summary_row_notes"}
            assert inspect(connection).get_foreign_keys("gs_ec_summary_row_notes") == []
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "legacy_revision"
            assert connection.execute(text("SELECT note FROM gs_ec_summary_row_notes")).scalar_one() == "Keep this note"
    finally:
        engine.dispose()
