# Первичное копирование истории (справочники и генерация)

Этот документ описывает первичное заполнение таблиц истории для справочников
(`gs_refdata_entities`, `gs_refdata_entity_years`).

## Когда нужно выполнять
- после внедрения исторического слоя;
- если нужно заполнить историю за прошлые годы;
- один раз для каждой версии `database_version_id` (или для нужного диапазона лет).

## Что уже делается автоматически
При создании **новой версии БД** исторические снимки создаются только если
версия строится **на основе другой версии** или при указании
`refdata_source_version_id`. В этом случае по текущему году создаются снимки
по ключевым справочникам (территории, энергосистемы, типы станций/агрегатов, топливо).

Если версия создается **пустой** (без источника справочников), снимки не создаются,
формируется только набор годов.

Это не заполняет историю за прошлые годы. Для этого нужен backfill.

## Вариант 1. Один год (быстро)
Подходит, если нужно заполнить только один год (например текущий) для выбранной версии.

Запуск через Flask shell:

```
flask shell
```

В интерактивной консоли (справочники):
```
from app.refdata.services.history.refdata_history_services import (
    snapshot_territories,
    snapshot_energy_systems,
    snapshot_station_machine_types,
    snapshot_fuels,
)

version_id = 7
year = 2024
user = "manual_backfill"

snapshot_territories(version_id, year, user)
snapshot_energy_systems(version_id, year, user)
snapshot_station_machine_types(version_id, year, user)
snapshot_fuels(version_id, year, user)
```

## Вариант 2. Диапазон лет (полное заполнение)
Подходит для полного backfill за несколько лет.

```
flask shell
```

```
from app.extensions import db
from app.refdata.models.years.year_model import Year
from app.refdata.services.history.refdata_history_services import (
    snapshot_territories,
    snapshot_energy_systems,
    snapshot_station_machine_types,
    snapshot_fuels,
)

version_id = 7
user = "manual_backfill"
years = [y.number for y in Year.query.filter_by(database_version_id=version_id).all()]

for year in years:
    snapshot_territories(version_id, year, user, do_commit=False)
    snapshot_energy_systems(version_id, year, user, do_commit=False)
    snapshot_station_machine_types(version_id, year, user, do_commit=False)
    snapshot_fuels(version_id, year, user, do_commit=False)
db.session.commit()
```

## Проверка результата

Проверить наличие записей:
```
SELECT count(*) FROM gs_sys.gs_refdata_entities WHERE database_version_id = 7;
SELECT count(*) FROM gs_sys.gs_refdata_entity_years WHERE database_version_id = 7;
```

Проверить, что `payload` читается:
```
SELECT payload->>'name'
FROM gs_sys.gs_refdata_entity_years
LIMIT 10;
```

## Примечания
- Большой backfill может выполняться долго. Запускайте в непиковое время.
- Для большого числа лет лучше делать один `commit` в конце (как в примере).
- Если данные менялись, backfill можно повторить — он обновит существующие записи.
