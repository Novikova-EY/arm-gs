-- Уникальные индексы: одна строка на (сущность, год, версия БД).
-- COALESCE для legacy-строк с database_version_id IS NULL.
-- CONCURRENTLY — без блокировки записи; выполнять вне транзакции.
-- Перед первым запуском: scripts/fix_machine_duplicates_all_versions.sql

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_machine_fuels_machine_year_ver
  ON gs_gen.gs_gen_machine_fuels (id_machine, year_number, COALESCE(database_version_id, -1));

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_machine_tes_types_machine_year_ver
  ON gs_gen.gs_gen_machine_tes_types (id_machine, year_number, COALESCE(database_version_id, -1));

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_machine_powers_machine_year_ver
  ON gs_gen.gs_gen_machine_powers (id_machine, year_number, COALESCE(database_version_id, -1));

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_machine_names_machine_year_ver
  ON gs_gen.gs_gen_machine_names (id_machine, year_number, COALESCE(database_version_id, -1));

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_pgu_machine_powers_machine_year_ver
  ON gs_gen.gs_gen_pgu_machine_powers (id_pgu_machine, year_number, COALESCE(database_version_id, -1));

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_pgu_machine_names_machine_year_ver
  ON gs_gen.gs_gen_pgu_machine_names (id_pgu_machine, year_number, COALESCE(database_version_id, -1));

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_station_powers_station_year_ver
  ON gs_gen.gs_gen_station_powers (id_station, year_number, COALESCE(database_version_id, -1));

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_station_energy_gen_station_year_month_ver
  ON gs_gen.gs_gen_station_energy_generations (id_station, year_number, month_number, COALESCE(database_version_id, -1));

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_station_gaes_charge_station_year_ver
  ON gs_gen.gs_gen_station_gaes_charge_consumptions (id_station, year_number, COALESCE(database_version_id, -1));
