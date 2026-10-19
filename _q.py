import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, dbname="gs_gen", user="generation", password="R7fP9wQk")
cur = conn.cursor()
V=46

# rows with fp.version NULL/other on eg version 46 (ecology includes, fuel excludes)
cur.execute("""
select fp.id, fp.equipment_group_id, fp.year_number, fp.database_version_id, fp.ved, fp.b
from gs_fue.gs_fue_equipment_group_fuel_param fp
join gs_fue.gs_fue_equipment_groups eg on eg.id=fp.equipment_group_id
where eg.database_version_id=%s and fp.year_number between 2023 and 2031
  and (fp.database_version_id is null or fp.database_version_id<>%s)
  and (fp.ved is null or fp.ved<>0)
""",(V,V))
print("FP rows with NULL/other version on current EG (ecology includes, fuel excludes):", cur.fetchall())

# Extra table duplicates per (group, year) -> fan-out risk in ecology SQL
cur.execute("""
select equipment_group_id, year_number, count(*) c
from gs_fue.gs_fue_equipment_group_extra_fuel_param
where year_number between 2023 and 2031
group by 1,2 having count(*)>1 order by c desc limit 10
""")
print("extra dupes per (group,year):", cur.fetchall())

# Extra rows version distribution for in-range, current-version groups
cur.execute("""
select coalesce(x.database_version_id::text,'NULL'), count(*)
from gs_fue.gs_fue_equipment_group_extra_fuel_param x
join gs_fue.gs_fue_equipment_groups eg on eg.id=x.equipment_group_id
where eg.database_version_id=%s and x.year_number between 2023 and 2031
group by 1 order by 1
""",(V,))
print("extra rows by version (current EG):", cur.fetchall())

# Ecology-style SQL (with extra join, grouped) sum of b vs plain sum, to detect fan-out
cur.execute("""
with src as (
  select fp.year_number y, fp.ved v, ues.name uesn, res.name resn, fp.b
  from gs_fue.gs_fue_equipment_group_fuel_param fp
  join gs_fue.gs_fue_equipment_groups eg on eg.id=fp.equipment_group_id
  left join gs_fue.gs_fue_equipment_group_extra_fuel_param x on x.equipment_group_id=fp.equipment_group_id and x.year_number=fp.year_number
  left join gs_sys.gs_sys_regional_energy_systems res on res.id=eg.regional_energy_system_id
  left join gs_sys.gs_sys_union_energy_systems ues on ues.id=res.id_union_energy_system
  where eg.database_version_id=%s and (fp.database_version_id=%s or fp.database_version_id is null)
    and fp.year_number between 2023 and 2031
    and (fp.ved is null or fp.ved<>0)
)
select sum(b) from src
""",(V,V))
print("plain sum(b) with extra join present:", cur.fetchall())
conn.close()
