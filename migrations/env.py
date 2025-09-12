# -*- coding: utf-8 -*-
import logging
from logging.config import fileConfig
from importlib import import_module

from flask import current_app
from alembic import context

# Alembic config + логирование
config = context.config
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

# ---- Достаём engine из Flask-Migrate / Flask-SQLAlchemy ----
def get_engine():
    try:
        # Flask-SQLAlchemy < 3
        return current_app.extensions["migrate"].db.get_engine()
    except (TypeError, AttributeError):
        # Flask-SQLAlchemy >= 3
        return current_app.extensions["migrate"].db.engine

def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace("%", "%%")
    except AttributeError:
        return str(get_engine().url).replace("%", "%%")

# Alembic будет брать URL из текущего приложения
config.set_main_option("sqlalchemy.url", get_engine_url())

# Flask-Migrate даёт нам объект db
target_db = current_app.extensions["migrate"].db

# ---- Импортируем модели, чтобы заполнить metadata всеми таблицами ----
# ВАЖНО: перечисли здесь все модули, где объявлены модели во всех схемах.
# (try/except — чтобы не падать, если чего-то нет в окружении на момент запуска)
def import_all_models():
    modules = [
        # auth
        "app.auth.models.role_model",
        "app.auth.models.user_model",
        "app.auth.models.user_role_model",
        "app.auth.models.log_model",
        # generation
        "app.generation.models.station_group_model",
        "app.generation.models.station_model",
        "app.generation.models.station_power_model",
        "app.generation.models.boiler_model",
        "app.generation.models.machine_model",
        "app.generation.models.machine_power_model",
        "app.generation.models.machine_fuel_model",
        "app.generation.models.machine_tes_type_model",
        "app.generation.models.pgu_machine_model",
        "app.generation.models.pgu_machine_power_model",
        # refdata
        "app.refdata.models.condition_type_model",
        "app.refdata.models.equipment_group_model",
        "app.refdata.models.machine_type_model",
        "app.refdata.models.pgu_tes_machine_type_model",
        "app.refdata.models.station_type_model",
        "app.refdata.models.tes_machine_type_model",
        "app.refdata.models.tes_type_model",
        "app.refdata.models.fuel_category_model",
        "app.refdata.models.fuel_type_model",
        "app.refdata.models.fuel_model",
        "app.refdata.models.gen_company_model",
        "app.refdata.models.energy_zone_model",
        "app.refdata.models.synchronous_area_model",
        "app.refdata.models.union_energy_system_model",
        "app.refdata.models.regional_energy_system_model",
        "app.refdata.models.regional_district_model",
        "app.refdata.models.energy_area_model",
        "app.refdata.models.energy_unit_model",
        "app.refdata.models.year_feature_model",
        "app.refdata.models.year_model",
        "app.refdata.models.regional_district_regional_energy_system_model",
    ]
    for m in modules:
        try:
            import_module(m)
        except Exception as e:
            logger.debug("Skip import %s: %s", m, e)

import_all_models()

# ---- Собираем target_metadata ----
# Обычно у Flask-SQLAlchemy единая metadata (db.metadata) — её достаточно.
# Alembic умеет принимать список MetaData, но в типовой схеме нужен один объект.
target_metadata = target_db.metadata

# ---- Общие настройки автогенерации ----
def process_revision_directives(context, revision, directives):
    """Не генерировать пустые миграции."""
    if getattr(config.cmd_opts, "autogenerate", False):
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []
            logger.info("No changes in schema detected.")

# ---- Offline ----
def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,           # ключ: учитываем все схемы, не только public
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

# ---- Online ----
def run_migrations_online():
    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,        # ключ: учитываем все схемы
            compare_type=True,           # сравниваем типы колонок
            compare_server_default=True, # сравниваем server_default (func.now() и т.п.)
            process_revision_directives=process_revision_directives,
            # version_table_schema="public",  # можно явно хранить alembic_version в public
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
