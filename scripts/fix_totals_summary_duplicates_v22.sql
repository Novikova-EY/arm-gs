-- =============================================================================
-- Диагностика и исправление дублей MachineFuel / MachineTesType
-- Версия БД: 22 ("СиПР 2026-2031 сходится УМ")
-- Сервер: 10.31.205.27, база gs_gen
--
-- Проблема: при join в totals_summary одна мощность умножается на
--   fuel_cnt * tes_cnt, если есть >1 строки на (id_machine, year_number).
-- Ожидаемый эффект после удаления дублей (2024):
--   ЕЭС России: 252869.2 -> ~248760.4 (минус ~3522 МВт искусственного завышения)
--
-- Правило сохранения: оставляем САМУЮ СТАРУЮ запись (created_at ASC, id ASC).
-- Все дубли на сервере созданы 2026-05-20..2026-05-27, оригиналы — 2026-02-17.
-- =============================================================================

\set ON_ERROR_STOP on
\set db_version_id 22

-- -----------------------------------------------------------------------------
-- 0) Проверка подключения
-- -----------------------------------------------------------------------------
SELECT inet_server_addr() AS server_ip, current_database() AS db_name, now() AS ts;

-- -----------------------------------------------------------------------------
-- 1) Сводка дублей в версии 22
-- -----------------------------------------------------------------------------
WITH scope AS (
    SELECT m.id AS machine_id
    FROM gs_gen.gs_gen_machines m
    JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
    WHERE s.database_version_id = :db_version_id
      AND m.database_version_id = :db_version_id
),
fuel_dup AS (
    SELECT mf.id_machine, mf.year_number, COUNT(*) AS cnt
    FROM gs_gen.gs_gen_machine_fuels mf
    JOIN scope sc ON sc.machine_id = mf.id_machine
    WHERE mf.database_version_id = :db_version_id
    GROUP BY mf.id_machine, mf.year_number
    HAVING COUNT(*) > 1
),
tes_dup AS (
    SELECT mt.id_machine, mt.year_number, COUNT(*) AS cnt
    FROM gs_gen.gs_gen_machine_tes_types mt
    JOIN scope sc ON sc.machine_id = mt.id_machine
    WHERE mt.database_version_id = :db_version_id
    GROUP BY mt.id_machine, mt.year_number
    HAVING COUNT(*) > 1
)
SELECT 'fuel_dup_groups' AS metric, COUNT(*)::text AS value FROM fuel_dup
UNION ALL
SELECT 'fuel_extra_rows', COALESCE(SUM(cnt - 1), 0)::text FROM fuel_dup
UNION ALL
SELECT 'tes_dup_groups', COUNT(*)::text FROM tes_dup
UNION ALL
SELECT 'tes_extra_rows', COALESCE(SUM(cnt - 1), 0)::text FROM tes_dup;

-- -----------------------------------------------------------------------------
-- 2) Оценка искусственного завышения по годам (как в totals_summary)
-- -----------------------------------------------------------------------------
WITH scope AS (
    SELECT m.id AS machine_id
    FROM gs_gen.gs_gen_machines m
    JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
    WHERE s.database_version_id = :db_version_id
      AND m.database_version_id = :db_version_id
),
mf AS (
    SELECT mf.id_machine, mf.year_number, COUNT(*) AS fuel_cnt
    FROM gs_gen.gs_gen_machine_fuels mf
    JOIN scope sc ON sc.machine_id = mf.id_machine
    WHERE mf.database_version_id = :db_version_id
    GROUP BY mf.id_machine, mf.year_number
),
mt AS (
    SELECT mt.id_machine, mt.year_number, COUNT(*) AS tes_cnt
    FROM gs_gen.gs_gen_machine_tes_types mt
    JOIN scope sc ON sc.machine_id = mt.id_machine
    WHERE mt.database_version_id = :db_version_id
    GROUP BY mt.id_machine, mt.year_number
),
mult AS (
    SELECT mp.year_number,
           COALESCE(mf.fuel_cnt, 1) * COALESCE(mt.tes_cnt, 1) AS mult,
           COALESCE(mp.p_ust, 0) AS p_ust
    FROM gs_gen.gs_gen_machine_powers mp
    JOIN scope sc ON sc.machine_id = mp.id_machine
    LEFT JOIN mf ON mf.id_machine = mp.id_machine AND mf.year_number = mp.year_number
    LEFT JOIN mt ON mt.id_machine = mp.id_machine AND mt.year_number = mp.year_number
    WHERE mp.database_version_id = :db_version_id
      AND mp.year_number BETWEEN 2024 AND 2031
)
SELECT year_number,
       ROUND(SUM((mult - 1) * p_ust)::numeric, 2) AS overcount_mw
FROM mult
WHERE mult > 1
GROUP BY year_number
ORDER BY year_number;

-- -----------------------------------------------------------------------------
-- 3) Топ станций/агрегатов, дающих завышение (2024)
-- -----------------------------------------------------------------------------
WITH scope AS (
    SELECT m.id AS machine_id, m.machine_number, s.name AS station_name, s.external_code
    FROM gs_gen.gs_gen_machines m
    JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
    WHERE s.database_version_id = :db_version_id
      AND m.database_version_id = :db_version_id
),
mf AS (
    SELECT mf.id_machine, mf.year_number, COUNT(*) AS fuel_cnt
    FROM gs_gen.gs_gen_machine_fuels mf
    JOIN scope sc ON sc.machine_id = mf.id_machine
    WHERE mf.database_version_id = :db_version_id
    GROUP BY mf.id_machine, mf.year_number
),
mt AS (
    SELECT mt.id_machine, mt.year_number, COUNT(*) AS tes_cnt
    FROM gs_gen.gs_gen_machine_tes_types mt
    JOIN scope sc ON sc.machine_id = mt.id_machine
    WHERE mt.database_version_id = :db_version_id
    GROUP BY mt.id_machine, mt.year_number
),
mult AS (
    SELECT sc.station_name, sc.external_code, sc.machine_id, sc.machine_number,
           mp.year_number,
           COALESCE(mf.fuel_cnt, 1) AS fuel_cnt,
           COALESCE(mt.tes_cnt, 1) AS tes_cnt,
           COALESCE(mf.fuel_cnt, 1) * COALESCE(mt.tes_cnt, 1) AS mult,
           COALESCE(mp.p_ust, 0) AS p_ust
    FROM gs_gen.gs_gen_machine_powers mp
    JOIN scope sc ON sc.machine_id = mp.id_machine
    LEFT JOIN mf ON mf.id_machine = mp.id_machine AND mf.year_number = mp.year_number
    LEFT JOIN mt ON mt.id_machine = mp.id_machine AND mt.year_number = mp.year_number
    WHERE mp.database_version_id = :db_version_id
      AND mp.year_number = 2024
)
SELECT station_name,
       external_code,
       machine_id,
       machine_number,
       fuel_cnt,
       tes_cnt,
       mult,
       ROUND(SUM((mult - 1) * p_ust)::numeric, 2) AS overcount_2024_mw
FROM mult
WHERE mult > 1
GROUP BY station_name, external_code, machine_id, machine_number, fuel_cnt, tes_cnt, mult
ORDER BY overcount_2024_mw DESC;

-- -----------------------------------------------------------------------------
-- 4) PREVIEW: какие строки будут удалены (оставляем самую старую)
-- -----------------------------------------------------------------------------
WITH scope AS (
    SELECT m.id AS machine_id
    FROM gs_gen.gs_gen_machines m
    JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
    WHERE s.database_version_id = :db_version_id
      AND m.database_version_id = :db_version_id
),
ranked_fuel AS (
    SELECT mf.id,
           mf.id_machine,
           mf.year_number,
           mf.id_fuel,
           mf.created_at,
           s.name AS station_name,
           m.machine_number,
           ROW_NUMBER() OVER (
               PARTITION BY mf.id_machine, mf.year_number, COALESCE(mf.database_version_id, -1)
               ORDER BY mf.created_at ASC, mf.id ASC
           ) AS rn
    FROM gs_gen.gs_gen_machine_fuels mf
    JOIN scope sc ON sc.machine_id = mf.id_machine
    JOIN gs_gen.gs_gen_machines m ON m.id = mf.id_machine
    JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
    WHERE mf.database_version_id = :db_version_id
),
ranked_tes AS (
    SELECT mt.id,
           mt.id_machine,
           mt.year_number,
           mt.id_tes_type,
           tt.name AS tes_type_name,
           mt.created_at,
           s.name AS station_name,
           m.machine_number,
           ROW_NUMBER() OVER (
               PARTITION BY mt.id_machine, mt.year_number, COALESCE(mt.database_version_id, -1)
               ORDER BY mt.created_at ASC, mt.id ASC
           ) AS rn
    FROM gs_gen.gs_gen_machine_tes_types mt
    JOIN scope sc ON sc.machine_id = mt.id_machine
    JOIN gs_gen.gs_gen_machines m ON m.id = mt.id_machine
    JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
    LEFT JOIN gs_sys.gs_sys_tes_types tt ON tt.id = mt.id_tes_type
    WHERE mt.database_version_id = :db_version_id
)
SELECT 'FUEL' AS table_name, id, station_name, machine_number, id_machine, year_number,
       id_fuel AS ref_id, NULL::text AS ref_name, created_at, rn
FROM ranked_fuel
WHERE rn > 1
UNION ALL
SELECT 'TES_TYPE', id, station_name, machine_number, id_machine, year_number,
       id_tes_type, tes_type_name, created_at, rn
FROM ranked_tes
WHERE rn > 1
ORDER BY table_name, station_name, id_machine, year_number;

-- =============================================================================
-- 5) УДАЛЕНИЕ (выполнять вручную, после проверки preview)
-- Рекомендуется: BEGIN; ... DELETE ...; проверка; COMMIT; или ROLLBACK;
-- =============================================================================

BEGIN;

WITH scope AS (
    SELECT m.id AS machine_id
    FROM gs_gen.gs_gen_machines m
    JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
    WHERE s.database_version_id = :db_version_id
      AND m.database_version_id = :db_version_id
),
to_delete_fuel AS (
    SELECT mf.id
    FROM gs_gen.gs_gen_machine_fuels mf
    JOIN scope sc ON sc.machine_id = mf.id_machine
    WHERE mf.database_version_id = :db_version_id
      AND mf.id IN (
          SELECT id
          FROM (
              SELECT mf2.id,
                     ROW_NUMBER() OVER (
                         PARTITION BY mf2.id_machine, mf2.year_number, COALESCE(mf2.database_version_id, -1)
                         ORDER BY mf2.created_at ASC, mf2.id ASC
                     ) AS rn
              FROM gs_gen.gs_gen_machine_fuels mf2
              JOIN scope sc2 ON sc2.machine_id = mf2.id_machine
              WHERE mf2.database_version_id = :db_version_id
          ) x
          WHERE x.rn > 1
      )
),
to_delete_tes AS (
    SELECT mt.id
    FROM gs_gen.gs_gen_machine_tes_types mt
    JOIN scope sc ON sc.machine_id = mt.id_machine
    WHERE mt.database_version_id = :db_version_id
      AND mt.id IN (
          SELECT id
          FROM (
              SELECT mt2.id,
                     ROW_NUMBER() OVER (
                         PARTITION BY mt2.id_machine, mt2.year_number, COALESCE(mt2.database_version_id, -1)
                         ORDER BY mt2.created_at ASC, mt2.id ASC
                     ) AS rn
              FROM gs_gen.gs_gen_machine_tes_types mt2
              JOIN scope sc2 ON sc2.machine_id = mt2.id_machine
              WHERE mt2.database_version_id = :db_version_id
          ) x
          WHERE x.rn > 1
      )
)
-- Сначала посмотреть, сколько удалится:
SELECT 'fuel_to_delete' AS what, COUNT(*) FROM to_delete_fuel
UNION ALL
SELECT 'tes_to_delete', COUNT(*) FROM to_delete_tes;

DELETE FROM gs_gen.gs_gen_machine_fuels mf
WHERE mf.id IN (
    WITH scope AS (
        SELECT m.id AS machine_id
        FROM gs_gen.gs_gen_machines m
        JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
        WHERE s.database_version_id = :db_version_id
          AND m.database_version_id = :db_version_id
    )
    SELECT x.id
    FROM (
        SELECT mf2.id,
               ROW_NUMBER() OVER (
                   PARTITION BY mf2.id_machine, mf2.year_number, COALESCE(mf2.database_version_id, -1)
                   ORDER BY mf2.created_at ASC, mf2.id ASC
               ) AS rn
        FROM gs_gen.gs_gen_machine_fuels mf2
        JOIN scope sc ON sc.machine_id = mf2.id_machine
        WHERE mf2.database_version_id = :db_version_id
    ) x
    WHERE x.rn > 1
);

DELETE FROM gs_gen.gs_gen_machine_tes_types mt
WHERE mt.id IN (
    WITH scope AS (
        SELECT m.id AS machine_id
        FROM gs_gen.gs_gen_machines m
        JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
        WHERE s.database_version_id = :db_version_id
          AND m.database_version_id = :db_version_id
    )
    SELECT x.id
    FROM (
        SELECT mt2.id,
               ROW_NUMBER() OVER (
                   PARTITION BY mt2.id_machine, mt2.year_number, COALESCE(mt2.database_version_id, -1)
                   ORDER BY mt2.created_at ASC, mt2.id ASC
               ) AS rn
        FROM gs_gen.gs_gen_machine_tes_types mt2
        JOIN scope sc ON sc.machine_id = mt2.id_machine
        WHERE mt2.database_version_id = :db_version_id
    ) x
    WHERE x.rn > 1
);

COMMIT;

-- -----------------------------------------------------------------------------
-- 6) Проверка после COMMIT (запустить отдельно)
-- -----------------------------------------------------------------------------
-- Повторить блоки (1) и (2): дублей быть не должно, overcount = 0.
-- Затем пересчитать totals_summary / выгрузить Excel и сравнить с эталоном 26.02.

-- -----------------------------------------------------------------------------
-- 7) (Опционально) уникальные ограничения, чтобы дубли не появлялись снова
-- -----------------------------------------------------------------------------
-- CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_machine_fuels_machine_year_ver
--   ON gs_gen.gs_gen_machine_fuels (id_machine, year_number, database_version_id);
--
-- CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_machine_tes_types_machine_year_ver
--   ON gs_gen.gs_gen_machine_tes_types (id_machine, year_number, database_version_id);
