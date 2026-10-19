# -*- coding: utf-8 -*-
"""Временный обзор: где в БД есть значения с float-шумом (>15 значащих цифр)."""
import psycopg2

SCHEMAS = ("gs_eco",)

conn = psycopg2.connect(
    host="localhost", port=5432, dbname="gs_gen", user="generation", password="R7fP9wQk"
)
cur = conn.cursor()
cur.execute(
    """
    select c.table_schema, c.table_name, c.column_name
    from information_schema.columns c
    join information_schema.tables t
      on t.table_schema = c.table_schema and t.table_name = c.table_name
    where c.data_type = 'numeric' and c.table_schema = any(%s)
      and t.table_type = 'BASE TABLE'
    order by 1, 2, c.ordinal_position
    """,
    (list(SCHEMAS),),
)
columns = cur.fetchall()
print("числовых колонок:", len(columns))

total_noisy = 0
for schema, table, column in columns:
    cur.execute(
        f"""
        select count(*) from {schema}."{table}"
        where "{column}" is not null
          and length(
                ltrim(replace(split_part("{column}"::text, '.', 1), '-', ''), '0')
                || rtrim(split_part("{column}"::text, '.', 2), '0')
              ) > 15
        """
    )
    noisy = cur.fetchone()[0]
    if noisy:
        cur.execute(f'select count(*) from {schema}."{table}"')
        rows = cur.fetchone()[0]
        total_noisy += noisy
        print(f"{schema}.{table}.{column}: {noisy} из {rows}")
print("всего шумных значений:", total_noisy)
conn.close()
