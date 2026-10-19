# -*- coding: utf-8 -*-
"""Временный обзор: float-шум по всем схемам БД (кроме служебных)."""
import psycopg2

SKIP = ("pg_catalog", "information_schema", "public", "pg_toast")
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
    where c.data_type = 'numeric' and t.table_type = 'BASE TABLE'
      and c.table_schema <> all(%s)
    order by 1, 2, c.ordinal_position
    """,
    (list(SKIP),),
)
columns = cur.fetchall()
print("числовых колонок:", len(columns))
hits = {}
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
        hits[f"{schema}.{table}"] = hits.get(f"{schema}.{table}", 0) + noisy
for key, count in sorted(hits.items(), key=lambda kv: -kv[1]):
    print(f"{key}: {count}")
print("таблиц с шумом:", len(hits), "| значений:", sum(hits.values()))
conn.close()
