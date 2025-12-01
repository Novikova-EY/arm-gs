# migrate_mysql_to_postgres.py
from sqlalchemy import create_engine, MetaData, Table, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert

# -----------------------------
# ПОДКЛЮЧЕНИЯ
# -----------------------------
mysql_url = "mysql+pymysql://root:helnov2010@localhost/gs-gen"
pg_url = URL.create(
    "postgresql+psycopg2",
    username="postgres",
    password="R7fP9wQk",
    host="localhost",
    port=5432,
    database="gs_gen",
)

# -----------------------------
# КОНФИГ
# -----------------------------
BATCH_SIZE = 5_000
TRUNCATE_BEFORE = False  # глобально выключено; включайте вручную при необходимости

# Таблицы, которые уже были успешно загружены — пропускаем
SKIP_TABLES = {
    # AUTH
    "roles", "users", "user_roles",
    # LOGS
    "logs",
    # REFDATA (из вашего лога уже загружены)
    "energy_system_types",
    "year_features",
    "years",
    "fuel_categories",
    "fuel_types",
    "fuels",
    "machine_types",
    "tes_machine_types",
    "tes_types",
    "pgu_tes_machine_types",
    "station_types",
    "condition_types",
    "equipment_groups",
    "union_energy_systems",
    "regional_energy_systems",
    "federal_districts",
    "regional_districts",
    "energy_units",
    # REFDATA: возможно пусто, но схема есть — можете убрать из SKIP, если хотите догрузить
    # "energy_areas",
    # M2M, не отразилась — разберем отдельно, пока пропускаем:
    # "regional_district_regional_energy_system",

    # GENERATION уже загружены
    "stations",
    "station_powers",
    # Пустые — можно оставить для загрузки:
    # "station_groups", "boilers",
}

# ЯВНАЯ КАРТА: источник(MySQL) → (схема PG, таблица PG)
# Порядок важен: сначала справочники, потом зависящие таблицы
TABLE_MAP = [
    # --- AUTH (на будущее, уже загружены)
    ("roles", ("auth", "roles")),
    ("users", ("auth", "users")),
    ("user_roles", ("auth", "user_roles")),

    # --- LOGS (уже загружены)
    ("logs", ("logs", "logs")),

    # --- REFDATA (часть уже загружена; gen_companies ДО machines)
    ("energy_system_types", ("refdata", "energy_system_types")),
    ("year_features", ("refdata", "year_features")),
    ("years", ("refdata", "years")),
    ("fuel_categories", ("refdata", "fuel_categories")),
    ("fuel_types", ("refdata", "fuel_types")),
    ("fuels", ("refdata", "fuels")),
    ("machine_types", ("refdata", "machine_types")),
    ("tes_machine_types", ("refdata", "tes_machine_types")),
    ("tes_types", ("refdata", "tes_types")),
    ("pgu_tes_machine_types", ("refdata", "pgu_tes_machine_types")),
    ("station_types", ("refdata", "station_types")),
    ("condition_types", ("refdata", "condition_types")),
    ("equipment_groups", ("refdata", "equipment_groups")),
    ("gen_companies", ("refdata", "gen_companies")),  # <— ДО generation.machines

    ("union_energy_systems", ("refdata", "union_energy_systems")),
    ("regional_energy_systems", ("refdata", "regional_energy_systems")),
    ("federal_districts", ("refdata", "federal_districts")),
    ("regional_districts", ("refdata", "regional_districts")),
    ("energy_units", ("refdata", "energy_units")),
    ("energy_areas", ("refdata", "energy_areas")),

    # M2M (может не отражаться из-за особенностей PK) — по готовности
    ("regional_district_regional_energy_system", ("refdata", "regional_district_regional_energy_system")),

    # --- GENERATION
    ("station_groups", ("generation", "station_groups")),
    ("stations", ("generation", "stations")),
    ("boilers", ("generation", "boilers")),
    ("machines", ("generation", "machines")),
    ("station_powers", ("generation", "station_powers")),
    ("machine_powers", ("generation", "machine_powers")),
    ("machine_fuels", ("generation", "machine_fuels")),
    ("machine_tes_types", ("generation", "machine_tes_types")),
    ("pgu_machines", ("generation", "pgu_machines")),
    ("pgu_machine_powers", ("generation", "pgu_machine_powers")),
]

# UPSERT-ключи (уникальные поля) для таблиц, где логично поддерживать повторный пуск
UPSERT_KEY = {
    "roles": "name",
    "users": "email",
    "fuel_categories": "name",
    "fuel_types": "name",
    "fuels": "name",
    "machine_types": "name",
    "tes_machine_types": "name",
    "tes_types": "name",
    "pgu_tes_machine_types": "name",
    "station_types": "name",
    "condition_types": "name",
    "equipment_groups": "name",
    "gen_companies": "name",
    "energy_system_types": "name",
    "union_energy_systems": "name",
    "regional_energy_systems": "name",
    "federal_districts": "name",
    "regional_districts": "name",
    "energy_units": "name",
    "energy_areas": "name",
    # при необходимости добавляйте
}

def ensure_schemas(pg_conn, schemas: set[str]):
    existing = {row[0] for row in pg_conn.execute(text(
        "SELECT schema_name FROM information_schema.schemata"
    )).fetchall()}
    for sch in sorted(schemas):
        if sch and sch not in existing:
            try:
                pg_conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{sch}"'))
                print(f"  [SCHEMA] Создана схема: {sch}")
            except Exception as e:
                print(f"  [WARNING] Не удалось создать схему {sch}: {e}")

def get_pg_table(engine, schema: str, name: str) -> Table | None:
    """Пробует отразить существующую таблицу в PG. Если не выходит — возвращает None."""
    try:
        return Table(name, MetaData(), autoload_with=engine, schema=schema)
    except Exception as e:
        print(f"  [ERROR] Не удалось отразить целевую таблицу {schema}.{name}: {e}")
        return None

def upsert_batch(conn, dst_table: Table, rows: list[dict], conflict_col: str):
    """UPSERT по одному уникальному столбцу (обычно name/email)."""
    if not rows:
        return
    stmt = pg_insert(dst_table).values(rows)
    if conflict_col not in dst_table.c:
        # если ожидаемого ключа нет — делаем do_nothing
        stmt = stmt.on_conflict_do_nothing()
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=[conflict_col],
            set_={c.name: stmt.excluded[c.name]
                  for c in dst_table.c if c.name != "id"}
        )
    conn.execute(stmt)

def insert_batch(conn, dst_table: Table, rows: list[dict]):
    if not rows:
        return
    conn.execute(dst_table.insert(), rows)

def main():
    mysql_engine = create_engine(mysql_url)
    pg_engine = create_engine(pg_url)

    # Отразим MySQL один раз
    mysql_md = MetaData()
    mysql_md.reflect(bind=mysql_engine)

    # Создадим схемы в PG (на всякий)
    with pg_engine.begin() as pg_conn:
        schemas = {sch for _, (sch, _) in TABLE_MAP}
        ensure_schemas(pg_conn, schemas)

    # Идем по таблицам в явном порядке
    for src_name, (pg_schema, pg_name) in TABLE_MAP:
        if src_name in SKIP_TABLES:
            print(f"\n[SKIP] Пропускаю (в SKIP_TABLES): {src_name}")
            continue

        if src_name not in mysql_md.tables:
            print(f"\n[SKIP] MySQL-таблица '{src_name}' не найдена — пропуск.")
            continue

        print(f"\n[TABLE] {src_name}  →  {pg_schema}.{pg_name}")
        src_table = mysql_md.tables[src_name]

        # Целевая таблица должна существовать (создана миграциями)
        dst_table = get_pg_table(pg_engine, pg_schema, pg_name)
        if dst_table is None:
            continue

        # Пересечение колонок по именам
        dst_cols = set(dst_table.columns.keys())
        common_cols = [c for c in src_table.columns if c.name in dst_cols]
        if not common_cols:
            print("  [WARNING] Нет общих колонок — пропуск.")
            continue

        # Опционально очистка (внимательно с FK!)
        if TRUNCATE_BEFORE:
            try:
                with pg_engine.begin() as conn:
                    conn.execute(text(f'TRUNCATE TABLE "{pg_schema}"."{pg_name}" RESTART IDENTITY CASCADE'))
                print("  [TRUNCATE] TRUNCATE выполнен.")
            except Exception as e:
                print(f"  [WARNING] TRUNCATE не выполнен: {e}")

        total = 0
        offset = 0
        while True:
            # Читаем пачку из MySQL
            with mysql_engine.connect() as conn:
                rows = conn.execute(
                    src_table.select().limit(BATCH_SIZE).offset(offset)
                ).mappings().all()

            if not rows:
                break

            payload = [
                {col.name: row.get(col.name) for col in common_cols}
                for row in rows
            ]

            try:
                with pg_engine.begin() as conn:
                    conflict_col = UPSERT_KEY.get(pg_name)  # ключ по таблице назначения
                    if conflict_col:
                        upsert_batch(conn, dst_table, payload, conflict_col)
                    else:
                        insert_batch(conn, dst_table, payload)
                total += len(rows)
                print(f"  [OK] вставлено {total} (+{len(rows)})")
            except IntegrityError as e:
                print(f"  [ERROR] Ошибка вставки (IntegrityError) на offset={offset}: {e.orig}")
                # Обычно это FK — проверьте порядок TABLE_MAP и наличие справочников
                break

            offset += BATCH_SIZE

        print(f"  [TOTAL] Итого по таблице: {total}")

    print("\n[SUCCESS] Перенос завершен.")

if __name__ == "__main__":
    main()
