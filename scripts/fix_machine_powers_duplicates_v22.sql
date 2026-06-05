-- =============================================================================
-- Удаление дублей gs_gen_machine_powers, версия БД 22
-- Правило: оставляем самую старую запись (created_at ASC, id ASC).
-- Ожидаемый эффект (2024): ЕЭС -585 МВт (Краснодарская ТЭЦ) и ~-2 МВт (ГПЭС)
-- =============================================================================

\set ON_ERROR_STOP on
\set db_version_id 22

BEGIN;

DELETE FROM gs_gen.gs_gen_machine_powers mp
WHERE mp.database_version_id = :db_version_id
  AND mp.id IN (
    WITH scope AS (
        SELECT m.id AS machine_id
        FROM gs_gen.gs_gen_machines m
        JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
        WHERE s.database_version_id = :db_version_id
          AND m.database_version_id = :db_version_id
    )
    SELECT x.id
    FROM (
        SELECT mp2.id,
               ROW_NUMBER() OVER (
                   PARTITION BY mp2.id_machine, mp2.year_number, COALESCE(mp2.database_version_id, -1)
                   ORDER BY mp2.created_at ASC, mp2.id ASC
               ) AS rn
        FROM gs_gen.gs_gen_machine_powers mp2
        JOIN scope sc ON sc.machine_id = mp2.id_machine
        WHERE mp2.database_version_id = :db_version_id
    ) x
    WHERE x.rn > 1
);

COMMIT;

-- Проверка: дублей быть не должно
WITH dup AS (
    SELECT id_machine, year_number, COUNT(*) cnt
    FROM gs_gen.gs_gen_machine_powers
    WHERE database_version_id = :db_version_id
    GROUP BY 1, 2
    HAVING COUNT(*) > 1
)
SELECT COUNT(*) AS remaining_dup_groups FROM dup;
