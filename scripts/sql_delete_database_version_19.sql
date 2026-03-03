-- Удаление всех записей с database_version_id = 19
-- Порядок удаления учитывает внешние ключи (сначала дочерние таблицы)

-- ВАЖНО: Выполните бэкап перед запуском!
-- Запуск: psql -U user -d dbname -f scripts/sql_delete_database_version_19.sql

BEGIN;

-- Stage 9: наиболее зависимые таблицы
DELETE FROM gs_gen.pgu_machine_powers WHERE database_version_id = 19;
DELETE FROM gs_fue.gs_fue_machine_fuel_param WHERE database_version_id = 19;

-- Stage 8
DELETE FROM gs_gen.machine_powers WHERE database_version_id = 19;
DELETE FROM gs_gen.machine_fuels WHERE database_version_id = 19;
DELETE FROM gs_gen.machine_tes_types WHERE database_version_id = 19;
DELETE FROM gs_gen.machine_names WHERE database_version_id = 19;
DELETE FROM gs_gen.pgu_machines WHERE database_version_id = 19;
DELETE FROM gs_fue.gs_fue_equipment_group_extra_fuel_param WHERE database_version_id = 19;
DELETE FROM gs_fue.gs_fue_equipment_group_fuel_param WHERE database_version_id = 19;
DELETE FROM gs_fue.gs_fue_equipment_group_toplivo_param WHERE database_version_id = 19;

-- Stage 7
DELETE FROM gs_gen.machines WHERE database_version_id = 19;
DELETE FROM gs_fue.gs_fue_equipment_group_set_stations WHERE database_version_id = 19;
DELETE FROM gs_fue.gs_fue_equipment_group_sets WHERE database_version_id = 19;
DELETE FROM gs_gen.station_powers WHERE database_version_id = 19;
DELETE FROM gs_gen.boilers WHERE database_version_id = 19;

-- Stage 6
DELETE FROM gs_gen.stations WHERE database_version_id = 19;

-- Stage 5
DELETE FROM gs_sys.gs_regional_district_regional_energy_system WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_energy_areas WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_energy_units WHERE database_version_id = 19;

-- Stage 4
DELETE FROM gs_sys.gs_regional_districts WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_regional_energy_systems WHERE database_version_id = 19;

-- Stage 3
DELETE FROM gs_sys.gs_union_energy_systems WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_synchronous_areas WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_energy_zones WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_federal_districts WHERE database_version_id = 19;

-- Stage 2
DELETE FROM gs_sys.gs_station_types WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_machine_types WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_tes_types WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_tes_machine_types WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_pgu_tes_machine_types WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_condition_types WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_technology_types WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_technology_availabilities WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_equipment_groups WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_energy_system_types WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_fuel_categories WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_fuel_types WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_fuels WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_companies WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_year_features WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_years WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_year_service WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_refdata_entity_years WHERE database_version_id = 19;
DELETE FROM gs_sys.gs_refdata_entities WHERE database_version_id = 19;
DELETE FROM gs_gen.station_groups WHERE database_version_id = 19;
DELETE FROM gs_gen.documents_kommod WHERE database_version_id = 19;
DELETE FROM gs_logs.logs WHERE database_version_id = 19;

-- Опционально: удалить саму запись версии
-- DELETE FROM gs_sys.gs_database_versions WHERE id = 19;

COMMIT;
