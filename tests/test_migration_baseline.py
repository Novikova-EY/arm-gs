"""Baseline regression tests; PostgreSQL tests use a disposable admin URL only.

Set MIGRATION_TEST_POSTGRES_URL to run database tests. The supplied role must be
able to create/drop databases. Each test creates its own migration_test_* DB.
"""
import ast
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
import os
from pathlib import Path
import re
import shutil
from uuid import uuid4
from zipfile import ZipFile

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from flask import Flask
from flask_migrate import Migrate, upgrade
from flask_sqlalchemy import SQLAlchemy
import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
SNAPSHOT = MIGRATIONS / "baseline" / "gs26102702.sql"


def test_only_baseline_is_active_and_legacy_graph_is_preserved():
    config = Config(str(MIGRATIONS / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["gs26102702"]
    assert scripts.get_bases() == ["gs26102702"]
    assert len(list(scripts.walk_revisions())) == 1
    with ZipFile(MIGRATIONS / "legacy_gs26102702.zip") as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == 247
        revisions = {}
        for name in archive.namelist():
            tree = ast.parse(archive.read(name).decode("utf-8-sig"))
            values = {
                target.id: ast.literal_eval(node.value)
                for node in tree.body if isinstance(node, ast.Assign)
                for target in node.targets
                if isinstance(target, ast.Name) and target.id in ("revision", "down_revision")
            }
            revisions[values["revision"]] = values["down_revision"]
        parents = {
            parent for value in revisions.values()
            for parent in (value if isinstance(value, tuple) else (value,))
            if parent is not None
        }
        assert set(revisions) - parents == {"gs26102702"}
        assert parents <= set(revisions)


def test_snapshot_has_no_server_configuration_or_version_table():
    sql = SNAPSHOT.read_text(encoding="utf-8")
    assert len(re.findall(r"^CREATE TABLE ", sql, re.M)) == 184
    assert len(re.findall(r"^CREATE SCHEMA ", sql, re.M)) == 14
    assert not re.search(r"(?im)^MAC |MACS=|^CREATE (SERVER|USER MAPPING|EXTENSION)|^\\", sql)
    assert "gs_auth.alembic_version" not in sql
    assert "set_config('search_path', '', true)" in sql
    assert "CREATE TYPE gs_sys.technology_type_enum" in sql
    assert "CREATE VIEW gs_sys.gs_database_versions" in sql


def test_deb_payload_contains_complete_baseline(tmp_path, monkeypatch):
    spec = spec_from_file_location("build_deb", ROOT / "scripts" / "build_deb.py")
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    source = tmp_path / "source"
    shutil.copytree(MIGRATIONS, source / "migrations")
    monkeypatch.setattr(builder, "PROJECT_ROOT", source)
    payload = tmp_path / "payload"
    builder.copy_payload(payload)
    copied = payload / "migrations"
    assert (copied / "baseline" / "gs26102702.sql").read_bytes() == SNAPSHOT.read_bytes()
    assert (copied / "legacy_gs26102702.zip").read_bytes() == (MIGRATIONS / "legacy_gs26102702.zip").read_bytes()
    assert sorted(p.name for p in (copied / "versions").glob("*.py")) == ["gs26102702_baseline.py"]


@pytest.fixture
def migration_database():
    url = os.environ.get("MIGRATION_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("MIGRATION_TEST_POSTGRES_URL is not set")
    admin = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    name = "migration_test_" + uuid4().hex
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}" TEMPLATE template0 ENCODING \'UTF8\'')
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=sa.engine.make_url(url).set(database=name),
        SCHEMA_AUTH="gs_auth",
    )
    db = SQLAlchemy(app)
    Migrate(app, db, directory=str(MIGRATIONS))
    try:
        with app.app_context():
            try:
                yield app, db
            finally:
                db.session.remove()
                db.engine.dispose()
    finally:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


def revision(connection):
    return connection.exec_driver_sql("SELECT version_num FROM gs_auth.alembic_version").scalar_one()


def assert_unchanged_comment(connection):
    comment = connection.exec_driver_sql("""
        SELECT col_description('gs_eco.gs_eco_operating_tes_fuel_chars'::regclass, attnum)
        FROM pg_attribute
        WHERE attrelid = 'gs_eco.gs_eco_operating_tes_fuel_chars'::regclass AND attname = 'ash'
    """).scalar_one()
    assert comment == "Зольность Ар, %"


def make_existing_database(db, head="gs26102702"):
    with db.engine.begin() as connection:
        connection.exec_driver_sql(SNAPSHOT.read_text(encoding="utf-8"), execution_options={"no_parameters": True})
        connection.exec_driver_sql("CREATE TABLE gs_auth.alembic_version (version_num varchar(32) PRIMARY KEY)")
        connection.execute(sa.text("INSERT INTO gs_auth.alembic_version VALUES (:head)"), {"head": head})
        connection.exec_driver_sql("CREATE TABLE gs_auth.baseline_test (id serial PRIMARY KEY, value text)")
        connection.exec_driver_sql("INSERT INTO gs_auth.baseline_test(value) VALUES ('existing data')")


def test_upgrade_empty_database_and_repeat_preserves_data_and_search_path(migration_database):
    _, db = migration_database
    upgrade()
    with db.engine.begin() as connection:
        assert revision(connection) == "gs26102702"
        tables = connection.execute(sa.text("""
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema LIKE 'gs_%' AND table_type = 'BASE TABLE'
        """)).scalar_one()
        assert tables == 185
        assert connection.exec_driver_sql("SHOW search_path").scalar_one() != '""'
        assert connection.exec_driver_sql("SELECT count(*) FROM gs_auth.users").scalar_one() == 0
        assert_unchanged_comment(connection)
        assert sa.inspect(connection).get_view_names(schema="gs_sys") == ["gs_database_versions"]
        connection.exec_driver_sql("CREATE TABLE gs_auth.baseline_test (id serial PRIMARY KEY, value text)")
        connection.exec_driver_sql("INSERT INTO gs_auth.baseline_test(value) VALUES ('existing data')")
    upgrade()
    with db.engine.connect() as connection:
        assert revision(connection) == "gs26102702"
        assert connection.exec_driver_sql("SELECT value FROM gs_auth.baseline_test").scalar_one() == "existing data"


def test_existing_head_never_executes_baseline(migration_database):
    _, db = migration_database
    make_existing_database(db)
    upgrade()
    upgrade()
    with db.engine.begin() as connection:
        assert revision(connection) == "gs26102702"
        assert connection.exec_driver_sql("SELECT value FROM gs_auth.baseline_test").scalar_one() == "existing data"
        assert connection.exec_driver_sql("INSERT INTO gs_auth.baseline_test(value) VALUES ('next') RETURNING id").scalar_one() == 2


def test_older_revision_fails_without_changing_database(migration_database):
    app, db = migration_database
    make_existing_database(db, "gs26102701")
    # Use Alembic directly: Flask-Migrate's CLI wrapper converts errors to SystemExit.
    config = app.extensions["migrate"].migrate.get_config(str(MIGRATIONS))
    with pytest.raises(CommandError, match="Can't locate revision"):
        command.upgrade(config, "head")
    with db.engine.connect() as connection:
        assert revision(connection) == "gs26102701"
        assert connection.exec_driver_sql("SELECT value FROM gs_auth.baseline_test").scalar_one() == "existing data"


def test_unversioned_nonempty_database_is_not_stamped(migration_database):
    app, db = migration_database
    with db.engine.begin() as connection:
        connection.exec_driver_sql("CREATE SCHEMA gs_auth")
        connection.exec_driver_sql("CREATE TABLE gs_auth.baseline_test (id integer)")
        connection.exec_driver_sql("INSERT INTO gs_auth.baseline_test VALUES (7)")
    config = app.extensions["migrate"].migrate.get_config(str(MIGRATIONS))
    with pytest.raises(RuntimeError, match="Baseline requires an empty"):
        command.upgrade(config, "head")
    with db.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT id FROM gs_auth.baseline_test").scalar_one() == 7
        assert not sa.inspect(connection).has_table("alembic_version", schema="gs_auth")


def test_downgrade_below_baseline_is_blocked(migration_database):
    app, db = migration_database
    make_existing_database(db)
    config = app.extensions["migrate"].migrate.get_config(str(MIGRATIONS))
    with pytest.raises(RuntimeError, match="Downgrade below gs26102702 is disabled"):
        command.downgrade(config, "base")
    with db.engine.connect() as connection:
        assert revision(connection) == "gs26102702"
        assert connection.exec_driver_sql("SELECT value FROM gs_auth.baseline_test").scalar_one() == "existing data"


def test_future_revision_can_upgrade_and_downgrade_to_baseline(migration_database, tmp_path):
    app, db = migration_database
    make_existing_database(db)
    directory = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS, directory)
    (directory / "versions" / "future_test.py").write_text(
        "from alembic import op\n"
        "revision = 'future_test'\n"
        "down_revision = 'gs26102702'\n"
        "def upgrade():\n"
        "    op.execute('CREATE TABLE gs_auth.future_test (id integer)')\n"
        "def downgrade():\n"
        "    op.drop_table('future_test', schema='gs_auth')\n",
        encoding="utf-8",
    )
    config = app.extensions["migrate"].migrate.get_config(str(directory))
    command.upgrade(config, "head")
    with db.engine.connect() as connection:
        assert revision(connection) == "future_test"
        assert sa.inspect(connection).has_table("future_test", schema="gs_auth")
    command.downgrade(config, "gs26102702")
    with db.engine.connect() as connection:
        assert revision(connection) == "gs26102702"
        assert not sa.inspect(connection).has_table("future_test", schema="gs_auth")
        assert connection.exec_driver_sql("SELECT value FROM gs_auth.baseline_test").scalar_one() == "existing data"


def test_offline_sql_can_initialize_database(migration_database):
    app, db = migration_database
    config = app.extensions["migrate"].migrate.get_config(str(MIGRATIONS))
    output = StringIO()
    config.output_buffer = output
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE SCHEMA IF NOT EXISTS gs_auth" in sql
    with db.engine.connect() as connection:
        connection.exec_driver_sql(sql, execution_options={"no_parameters": True})
        assert revision(connection) == "gs26102702"
        assert connection.exec_driver_sql("SELECT count(*) FROM gs_auth.users").scalar_one() == 0
        assert_unchanged_comment(connection)
