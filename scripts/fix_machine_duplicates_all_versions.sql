-- =============================================================================
-- Удаление дублей по (сущность, год, версия БД) во ВСЕХ версиях.
-- Правило: оставляем самую старую запись (created_at ASC, id ASC).
-- Безопасно перезапускать: удаляются только rn > 1 внутри своей версии.
-- =============================================================================

\set ON_ERROR_STOP on

-- 0) Диагностика ДО (покажет 0, если уже чисто)
\echo '=== Дубли ДО очистки ==='
WITH checks AS (
  SELECT 'machine_fuels' t, database_version_id ver, COUNT(*) dup_groups, COALESCE(SUM(cnt-1),0)::int extra
  FROM (SELECT database_version_id, id_machine, year_number, COUNT(*) cnt FROM gs_gen.gs_gen_machine_fuels GROUP BY 1,2,3 HAVING COUNT(*)>1) x GROUP BY 2
  UNION ALL SELECT 'machine_tes_types', database_version_id, COUNT(*), COALESCE(SUM(cnt-1),0)::int FROM (SELECT database_version_id, id_machine, year_number, COUNT(*) cnt FROM gs_gen.gs_gen_machine_tes_types GROUP BY 1,2,3 HAVING COUNT(*)>1) x GROUP BY 2
  UNION ALL SELECT 'machine_powers', database_version_id, COUNT(*), COALESCE(SUM(cnt-1),0)::int FROM (SELECT database_version_id, id_machine, year_number, COUNT(*) cnt FROM gs_gen.gs_gen_machine_powers GROUP BY 1,2,3 HAVING COUNT(*)>1) x GROUP BY 2
  UNION ALL SELECT 'machine_names', database_version_id, COUNT(*), COALESCE(SUM(cnt-1),0)::int FROM (SELECT database_version_id, id_machine, year_number, COUNT(*) cnt FROM gs_gen.gs_gen_machine_names GROUP BY 1,2,3 HAVING COUNT(*)>1) x GROUP BY 2
  UNION ALL SELECT 'pgu_machine_powers', database_version_id, COUNT(*), COALESCE(SUM(cnt-1),0)::int FROM (SELECT database_version_id, id_pgu_machine, year_number, COUNT(*) cnt FROM gs_gen.gs_gen_pgu_machine_powers GROUP BY 1,2,3 HAVING COUNT(*)>1) x GROUP BY 2
  UNION ALL SELECT 'pgu_machine_names', database_version_id, COUNT(*), COALESCE(SUM(cnt-1),0)::int FROM (SELECT database_version_id, id_pgu_machine, year_number, COUNT(*) cnt FROM gs_gen.gs_gen_pgu_machine_names GROUP BY 1,2,3 HAVING COUNT(*)>1) x GROUP BY 2
  UNION ALL SELECT 'station_powers', database_version_id, COUNT(*), COALESCE(SUM(cnt-1),0)::int FROM (SELECT database_version_id, id_station, year_number, COUNT(*) cnt FROM gs_gen.gs_gen_station_powers GROUP BY 1,2,3 HAVING COUNT(*)>1) x GROUP BY 2
  UNION ALL SELECT 'station_energy_gen', database_version_id, COUNT(*), COALESCE(SUM(cnt-1),0)::int FROM (SELECT database_version_id, id_station, year_number, month_number, COUNT(*) cnt FROM gs_gen.gs_gen_station_energy_generations GROUP BY 1,2,3,4 HAVING COUNT(*)>1) x GROUP BY 2
  UNION ALL SELECT 'station_gaes_charge', database_version_id, COUNT(*), COALESCE(SUM(cnt-1),0)::int FROM (SELECT database_version_id, id_station, year_number, COUNT(*) cnt FROM gs_gen.gs_gen_station_gaes_charge_consumptions GROUP BY 1,2,3 HAVING COUNT(*)>1) x GROUP BY 2
)
SELECT t, ver, dup_groups, extra FROM checks ORDER BY extra DESC, t, ver;

BEGIN;

DELETE FROM gs_gen.gs_gen_machine_fuels
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY id_machine, year_number, COALESCE(database_version_id, -1)
            ORDER BY created_at ASC, id ASC
        ) rn FROM gs_gen.gs_gen_machine_fuels
    ) x WHERE rn > 1
);

DELETE FROM gs_gen.gs_gen_machine_tes_types
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY id_machine, year_number, COALESCE(database_version_id, -1)
            ORDER BY created_at ASC, id ASC
        ) rn FROM gs_gen.gs_gen_machine_tes_types
    ) x WHERE rn > 1
);

DELETE FROM gs_gen.gs_gen_machine_powers
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY id_machine, year_number, COALESCE(database_version_id, -1)
            ORDER BY created_at ASC, id ASC
        ) rn FROM gs_gen.gs_gen_machine_powers
    ) x WHERE rn > 1
);

DELETE FROM gs_gen.gs_gen_machine_names
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY id_machine, year_number, COALESCE(database_version_id, -1)
            ORDER BY created_at ASC, id ASC
        ) rn FROM gs_gen.gs_gen_machine_names
    ) x WHERE rn > 1
);

DELETE FROM gs_gen.gs_gen_pgu_machine_powers
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY id_pgu_machine, year_number, COALESCE(database_version_id, -1)
            ORDER BY created_at ASC, id ASC
        ) rn FROM gs_gen.gs_gen_pgu_machine_powers
    ) x WHERE rn > 1
);

DELETE FROM gs_gen.gs_gen_pgu_machine_names
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY id_pgu_machine, year_number, COALESCE(database_version_id, -1)
            ORDER BY created_at ASC, id ASC
        ) rn FROM gs_gen.gs_gen_pgu_machine_names
    ) x WHERE rn > 1
);

DELETE FROM gs_gen.gs_gen_station_powers
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY id_station, year_number, COALESCE(database_version_id, -1)
            ORDER BY created_at ASC, id ASC
        ) rn FROM gs_gen.gs_gen_station_powers
    ) x WHERE rn > 1
);

DELETE FROM gs_gen.gs_gen_station_energy_generations
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY id_station, year_number, month_number, COALESCE(database_version_id, -1)
            ORDER BY created_at ASC, id ASC
        ) rn FROM gs_gen.gs_gen_station_energy_generations
    ) x WHERE rn > 1
);

DELETE FROM gs_gen.gs_gen_station_gaes_charge_consumptions
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY id_station, year_number, COALESCE(database_version_id, -1)
            ORDER BY created_at ASC, id ASC
        ) rn FROM gs_gen.gs_gen_station_gaes_charge_consumptions
    ) x WHERE rn > 1
);

COMMIT;

\echo '=== Дубли ПОСЛЕ очистки (должно быть пусто) ==='
WITH checks AS (
  SELECT 'machine_fuels' t, COUNT(*) dup_groups FROM (SELECT database_version_id, id_machine, year_number FROM gs_gen.gs_gen_machine_fuels GROUP BY 1,2,3 HAVING COUNT(*)>1) x
  UNION ALL SELECT 'machine_tes_types', COUNT(*) FROM (SELECT database_version_id, id_machine, year_number FROM gs_gen.gs_gen_machine_tes_types GROUP BY 1,2,3 HAVING COUNT(*)>1) x
  UNION ALL SELECT 'machine_powers', COUNT(*) FROM (SELECT database_version_id, id_machine, year_number FROM gs_gen.gs_gen_machine_powers GROUP BY 1,2,3 HAVING COUNT(*)>1) x
  UNION ALL SELECT 'machine_names', COUNT(*) FROM (SELECT database_version_id, id_machine, year_number FROM gs_gen.gs_gen_machine_names GROUP BY 1,2,3 HAVING COUNT(*)>1) x
  UNION ALL SELECT 'pgu_machine_powers', COUNT(*) FROM (SELECT database_version_id, id_pgu_machine, year_number FROM gs_gen.gs_gen_pgu_machine_powers GROUP BY 1,2,3 HAVING COUNT(*)>1) x
  UNION ALL SELECT 'pgu_machine_names', COUNT(*) FROM (SELECT database_version_id, id_pgu_machine, year_number FROM gs_gen.gs_gen_pgu_machine_names GROUP BY 1,2,3 HAVING COUNT(*)>1) x
  UNION ALL SELECT 'station_powers', COUNT(*) FROM (SELECT database_version_id, id_station, year_number FROM gs_gen.gs_gen_station_powers GROUP BY 1,2,3 HAVING COUNT(*)>1) x
  UNION ALL SELECT 'station_energy_gen', COUNT(*) FROM (SELECT database_version_id, id_station, year_number, month_number FROM gs_gen.gs_gen_station_energy_generations GROUP BY 1,2,3,4 HAVING COUNT(*)>1) x
  UNION ALL SELECT 'station_gaes_charge', COUNT(*) FROM (SELECT database_version_id, id_station, year_number FROM gs_gen.gs_gen_station_gaes_charge_consumptions GROUP BY 1,2,3 HAVING COUNT(*)>1) x
)
SELECT t, dup_groups FROM checks ORDER BY t;
