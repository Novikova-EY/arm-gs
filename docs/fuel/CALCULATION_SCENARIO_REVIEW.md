# Итоговая сверка сценария «Расчёт» (топливо по группам оборудования)

Документ фиксирует **единую линию расчёта** и чеклист ручной сверки между: карточкой группы (details/edit), пакетным UI, запуском по `DistributionParameter` и эталоном Access.

## 1. Общее ядро расчёта

Математика сценария «Расчёт» для строк **`EquipmentGroupFuelParam`** / **`EquipmentGroupExtraFuelParam`** на заданный **год** сосредоточена в:

- `EquipmentGroupFuelCalculationService.calculate_group_year` — `app/fuel/services/equipment_group_fuel_calculation_services.py` (логика, перенесённая из Access).

Пакетный слой только перебирает группы и коммитит транзакции:

- `EquipmentGroupFuelBatchCalculationService.calculate_for_many_groups` — `app/fuel/services/equipment_group_fuel_batch_calculation_services.py`.

Снимок полей после расчёта для API (в т.ч. годы исходных строк удельных и формулы) — `fuel_calculation_snapshot_for_api` в том же batch-файле.

**Входы на один год расчёта (как в пакете):**

- строка удельных `EquipmentGroupSpecificFuelConsumption`: последняя с `year_number` ≤ году расчёта;
- строка формулы `EquipmentGroupFuelFormula`: последняя с `year_number` ≤ году расчёта для `variant_number` (и версии БД);
- поля энергобаланса в строке `EquipmentGroupFuelParam` за **этот же год расчёта** (`e`, `q`, `qotr`, `turt` и т.д. — как в описании на странице пакета).

**Что сценарий «Расчёт» не делает:** не перезаписывает вручную заданные на карточке входные удельные `k, y, btp, sntp, bk, snk`; не считает `*_calc` удельных (это отдельный recalc после сохранения карточки); не считает цену `xxx_c` (отдельный пересчёт цены).

---

## 2. Карточка группы (details / edit)

**Маршрут:** `fuel_bp.equipment_group_edit` (старый URL `equipment_group_details` редиректит сюда).

**Сохранение:**

- Основные/доп. параметры топлива, входные удельные, стоимость — через `equipment_group_details_params_update_services` и write-сервисы.
- После изменения входных удельных вызывается `recalculate_all_specific_fuel_consumption_calc` для `*_calc`.
- Цена пересчитывается `recalculate_specific_fuel_prices_for_equipment_group`, поля цены с формы не пишутся.

**Сверка с пакетом:** пакет обновляет **тот же** расчётный контур топлива (`calculate_group_year`), но **не** подменяет сценарий сохранения карточки. Сравнивать имеет смысл **строку за год расчёта** в `EquipmentGroupFuelParam` / `EquipmentGroupExtraFuelParam` после пакета с тем, что получится при согласованных входах (удельные, формула, баланс).

---

## 3. Пакетный UI

**Страница:** `fuel_bp.equipment_group_fuel_batch_calculation_page` — шаблон `fuel/batch_recalc/equipment_group_fuel_batch_calculation.html`.

**API расчёта:** `POST .../equipment_group_fuel_batch_calculation/batch` — разбор территориальных фильтров → список `equipment_group_ids` → тот же `EquipmentGroupFuelBatchCalculationService`.

**Сверка:** блок «Сверка с карточкой группы и сценарием «Расчёт»» на странице; JSON-ответ содержит сведения о пакете; предпросмотр таблиц подтягивает сохранённые данные после успешного прогона.

---

## 4. Выбор по `DistributionParameter`

**Модель:** `DistributionParameter` (`gs_fue_distribution_parameters`), поле **`filter_text`** обрабатывается через **`AccessFilterAdapter.build_expression`** (не произвольный SQL в сервисе).

**Сервис:** `DistributionParameterCalculationService` — `app/fuel/services/distribution_parameter_calculation_services.py`.

**Цепочка:** строка `DistributionParameter` → отбор `EquipmentGroup` по фильтру и версии БД → **`EquipmentGroupFuelBatchCalculationService.calculate_for_many_groups`** с `year_number` из строки параметра.

**API:**

- `POST .../equipment_group_fuel_batch_calculation/distribution` — один `distribution_param_id`;
- `POST .../equipment_group_fuel_batch_calculation/distribution_multi` — несколько id / имя / год.

Параметры `commit_each`, `final_commit`, `stop_on_error`, `strict_formula_validation` согласованы с пакетным batch API.

**Сверка с пакетным UI:** при тех же `year_number`, `variant_number`, версии БД и наборе групп, который даёт `filter_text`, результаты batch должны совпадать с прогоном по явному списку id через `/batch`.

---

## 5. Контрольные группы и Access (ручная сверка 1–2 групп)

Цель: убедиться, что **числа в БД** после расчёта ARM совпадают с эталоном Access для выбранных групп и года.

**Рекомендуемый порядок:**

1. Зафиксировать **год расчёта**, **variant_number**, **версию БД**.
2. Выбрать **1–2 контрольные группы** с полными данными: удельные, формула, баланс за год, при необходимости — стоимость (для цены не для пакета fuel param).
3. Выполнить расчёт одним из способов:
   - пакетный UI по фильтру, включающему только эти группы; или
   - API `distribution` с параметром распределения, в котором `filter_text` отбирает те же группы; или
   - прямой вызов сервиса в среде разработки (по согласованию с командой).
4. Выгрузить или посмотреть в UI строки **`EquipmentGroupFuelParam`** и **`EquipmentGroupExtraFuelParam`** за **год расчёта** для этих групп.
5. Сопоставить с выгрузкой Access по тем же ключевым полям (энергоблок: `ewtp`, `eotp`, `eust`, `eurt`, `tust`, `b`; основные/доп. виды топлива согласно `TOPLS` / `UGLI` / `UGLI1` в `equipment_group_fuel_calculation_services.py`).

**На что обратить внимание при расхождении:**

- другой **год строки** удельных или формулы (правило «последняя ≤ году расчёта»);
- другой **`variant_number`** или строка формулы;
- несовпадение **версии БД** у группы и параметров;
- округление в UI vs полное значение в БД.

---

## 6. Краткий чеклист «готово к приёмке»

| Проверка | Где смотреть |
|----------|----------------|
| Входные удельные и `*_calc` разделены по смыслу и сохранению | `equipment_group_specific_fuel_consumption_write_services`, карточка edit |
| После сохранения удельных пересчитаны `*_calc` | `recalculate_all_specific_fuel_consumption_calc` из orchestration |
| Цена не пишется с формы, пересчёт отдельно | `recalculate_specific_fuel_prices_for_equipment_group` |
| Пакет пишет fuel/extra за год расчёта | `EquipmentGroupFuelBatchCalculationService` |
| DistributionParameter даёт тот же batch | `DistributionParameterCalculationService` |
| Документация для пользователя на batch-странице согласована с кодом | `equipment_group_fuel_batch_calculation.html` |

При необходимости этот чеклист дополняют автотестами на `calculate_group_year` с фикстурами, отдельно от UI.
