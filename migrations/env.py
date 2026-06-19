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

# ---- Достаем engine из Flask-Migrate / Flask-SQLAlchemy ----
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

# Flask-Migrate дает нам объект db
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
        "app.generation.models.station.station_gaes_charge_consumption_model",
        "app.energy_balance.models.station_energy_generation_model",
        "app.energy_balance.models.espp_energy_generation_model",
        "app.energy_balance.models.regional_energy_system_energy_generation_model",
        "app.generation.models.boiler_model",
        "app.generation.models.machine_model",
        "app.generation.models.machine_power_model",
        "app.generation.models.machine_fuel_model",
        "app.generation.models.machine_tes_type_model",
        "app.generation.models.pgu_machine_model",
        "app.generation.models.pgu_machine_power_model",
        "app.generation.models.pgu_machine.pgu_machine_name_model",
        # fuel
        "app.fuel.models.fue_machine_fuel_param_model",
        "app.fuel.models.fue_equipment_group_fuel_param_model",
        "app.fuel.models.fue_equipment_group_extra_fuel_param_model",
        "app.fuel.models.fue_equipment_group_specific_fuel_consumption_model",
        "app.fuel.models.fue_distribution_parameter_model",
        "app.fuel.models.coefficient.distribution_coefficient_summary_model",
        "app.fuel.models.coefficient.equipment_group_coefficient_result_model",
        # fuel equipment groups
        "app.fuel.models.fue_equipment_group_model",
        "app.fuel.models.fue_equipment_group_set_station_model",
        "app.fuel.models.fue_equipment_group_set_model",
        "app.fuel.models.external_mapping.fue_em_union_energy_system_model",
        "app.fuel.models.external_mapping.fue_em_federal_district_model",
        "app.fuel.models.external_mapping.fue_em_territories_energy_model",
        "app.fuel.models.external_mapping.fue_em_business_unit_model",
        "app.fuel.models.external_mapping.fue_em_department_model",
        "app.fuel.models.external_mapping.fue_em_economic_region_model",
        "app.fuel.models.external_mapping.fue_em_economic_region_model",
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
        "app.refdata.models.year_service_model",
        "app.refdata.models.regional_district_regional_energy_system_model",
        # power_demand (gs_pd)
        "app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model",
        "app.power_demand.models.energy_systems.ees_demand_parameter_model",
        "app.power_demand.models.energy_systems.ees_russia_demand_parameter_model",
        "app.power_demand.models.energy_systems.energy_area_demand_parameter_model",
        "app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model",
        "app.power_demand.models.energy_systems.energy_unit_demand_parameter_model",
        "app.power_demand.models.energy_systems.energy_zone_demand_parameter_model",
        "app.power_demand.models.energy_systems.regional_energy_system_demand_parameter_model",
        "app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model",
        "app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model",
        "app.common.models.perimeter_variant.perimeter_variant_model",
        "app.common.models.perimeter_variant.entity_perimeter_binding_model",
        "app.power_demand.models.territories.federal_district_demand_parameter_model",
        "app.power_demand.models.territories.regional_district_demand_parameter_model",
        "app.power_demand.models.territories.russia_federation_demand_parameter_model",
    ]
    for m in modules:
        try:
            import_module(m)
        except Exception as e:
            logger.debug("Skip import %s: %s", m, e)

import_all_models()

# ---- Собираем target_metadata ----
# Обычно у Flask-SQLAlchemy единая metadata (db.metadata) — ее достаточно.
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

# ---- Фильтр объектов: не удалять то, чего нет в metadata, и игнорировать alembic_version ----
def include_object(object, name, type_, reflected, compare_to):
    # не трогаем таблицу версий Alembic
    if type_ == "table" and name == "alembic_version":
        return False
    # при автогенерации не учитываем индексы, чтобы не плодить повторы
    if type_ == "index" and getattr(config.cmd_opts, "autogenerate", False):
        return False
    # объект есть в БД (reflected=True), но отсутствует в metadata (compare_to is None)
    # => это что-то не импортировали в модели; не генерим DROP
    if reflected and compare_to is None:
        return False
    return True

# ---- Offline ----
def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    version_schema = current_app.config.get("SCHEMA_AUTH", "gs_auth")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
        version_table='alembic_version',
        version_table_schema=version_schema,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()

# ---- Online ----
def run_migrations_online():
    connectable = get_engine()
    with connectable.connect() as connection:
        version_schema = current_app.config.get("SCHEMA_AUTH", "gs_auth")
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,        # ключ: учитываем все схемы
            compare_type=True,           # сравниваем типы колонок
            compare_server_default=True, # сравниваем server_default (func.now() и т.п.)
            include_object=include_object,
            process_revision_directives=process_revision_directives,
            version_table='alembic_version',
            version_table_schema=version_schema,
            # Иначе весь `flask db upgrade` в одной транзакции: любой сбой откатывает
            # даже успешно применённые миграции в этой сессии.
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

from alembic.operations.ops import DropTableOp, DropColumnOp, DropConstraintOp, DropIndexOp

def process_revision_directives(context, revision, directives):
    """Не генерировать пустые миграции + вычищать DROP-операции при autogenerate."""
    if getattr(config.cmd_opts, "autogenerate", False) and directives:
        script = directives[0]

        # 1) убрать дропы из upgrade_ops
        keep_ops = []
        for op in script.upgrade_ops.ops:
            if isinstance(op, (DropTableOp, DropColumnOp, DropConstraintOp, DropIndexOp)):
                # пропускаем разрушительные операции
                continue
            keep_ops.append(op)
        script.upgrade_ops.ops = keep_ops

        # 2) удалить пустые миграции
        if script.upgrade_ops.is_empty():
            directives[:] = []
            logger.info("No changes in schema detected.")