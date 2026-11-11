BEGIN READ ONLY;

SELECT
    m.database_version_id,
    v.version_number,
    m.id AS machine_id,
    m.external_code AS machine_external_code,
    m.machine_name,
    s.id AS station_id,
    s.external_code AS station_external_code,
    s.name AS station_name,
    rd.name AS regional_district,
    rd.ref_uuid AS regional_district_uuid,
    res.name AS regional_energy_system,
    (
        SELECT jsonb_agg(jsonb_build_object(
            'year', p.year_number,
            'p_ust', p.p_ust,
            'p_ogr', p.p_ogr,
            'p_rasp', p.p_rasp
        ) ORDER BY p.id)
        FROM gs_gen.gs_gen_machine_powers p
        WHERE p.id_machine = m.id AND p.year_number = 2031
    ) AS power_2031,
    (
        SELECT jsonb_agg(jsonb_build_object(
            'id', fp.id,
            'equipment_group_id', fp.equipment_group_id
        ) ORDER BY fp.id)
        FROM gs_fue.gs_fue_machine_fuel_param fp
        WHERE fp.machine_id = m.id
    ) AS fuel_bindings
FROM gs_gen.gs_gen_machines m
JOIN gs_gen.gs_gen_stations s ON s.id = m.id_station
LEFT JOIN gs_sys.gs_database_versions v ON v.id = m.database_version_id
LEFT JOIN gs_sys.gs_sys_regional_districts rd ON rd.id = s.id_regional_district
LEFT JOIN gs_sys.gs_sys_regional_energy_systems res ON res.id = s.id_regional_energy_system
WHERE m.external_code IN (
    '5d8eedf4-e62a-4ca5-81f4-d707fb54c8cb',
    'f4a7946e-d625-4296-9641-62af1b0bb0ae',
    '0819acca-716d-46e7-8bf9-67ffedaaf3f5',
    '0d2d1dab-9641-5624-99ea-fbc412b18853'
)
ORDER BY m.external_code, m.database_version_id, m.id;

COMMIT;
