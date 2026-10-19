# -*- coding: utf-8 -*-
"""Временный обзор: примеры шумных значений по колонкам экологии."""
import psycopg2

TARGETS = [
    ("gs_eco", "gs_eco_gis_tek_greenhouse_gas_params", "co2_from_gas_t"),
    ("gs_eco", "gs_eco_gis_tek_pollutant_params", "gaseous_and_liquid"),
    ("gs_eco", "gs_eco_analysis_pg_params", "co2_from_gas_t"),
    ("gs_eco", "gs_eco_operating_tes_fuel_chars", "qh_kj"),
    ("gs_eco", "gs_eco_operating_tes_fuel_chars", "k_natural"),
    ("gs_eco", "gs_eco_operating_tes_fuel_chars", "t_co2_per_tj"),
]

conn = psycopg2.connect(
    host="localhost", port=5432, dbname="gs_gen", user="generation", password="R7fP9wQk"
)
cur = conn.cursor()
for schema, table, column in TARGETS:
    cur.execute(
        f"""
        select distinct "{column}"::text from {schema}."{table}"
        where "{column}" is not null
          and length(
                ltrim(replace(split_part("{column}"::text, '.', 1), '-', ''), '0')
                || rtrim(split_part("{column}"::text, '.', 2), '0')
              ) > 15
        limit 6
        """
    )
    print(f"{table}.{column}:", [r[0] for r in cur.fetchall()])
conn.close()
