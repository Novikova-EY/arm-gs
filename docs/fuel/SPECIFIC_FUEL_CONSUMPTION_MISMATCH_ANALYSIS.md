# Анализ расхождений между загруженными и расчётными значениями

## Источники данных

| Поле | Загруженное (из Excel) | Расчётное (_calc) |
|------|------------------------|-------------------|
| y / y_calc | consumption.y | calc_y_calc(param) |
| btp / btp_calc | consumption.btp | calc_btp_calc(param, consumption.k) |
| sntp / sntp_calc | consumption.sntp | calc_sntp_calc(param) |
| bk / bk_calc | consumption.bk | calc_bk_calc(param, btp_calc, sntp_calc) |
| snk / snk_calc | consumption.snk | param.snk (копия из fuel param) |

**param** = EquipmentGroupFuelParam (ewtp, qotr, ved, e, eurt, eotp, eust, snk)

## Возможные причины расхождений

### 1. Разные входные данные (ewtp, qotr, e, eurt и т.д.)

Расчёт использует **EquipmentGroupFuelParam**. Excel мог быть создан из другой БД (Access) с другими значениями.

- Если param.ewtp ≠ то, что было в Access → y_calc ≠ y
- Если param.eurt, param.e, param.ewtp, K отличаются → btp_calc ≠ btp
- И т.д.

**Проверка:** сравнить значения ewtp, qotr, ved, e, eurt, eotp, eust, snk в fuel param с теми, что использовались при создании Excel.

### 2. Разный SNK в формулах

- **sntp_calc** и **bk_calc** используют `param.snk` (из EquipmentGroupFuelParam)
- **snk_calc** = `param.snk` (копия)
- Загруженный **consumption.snk** — из Excel

Если param.snk ≠ consumption.snk → расчёт sntp_calc, bk_calc и snk_calc будет отличаться от загруженных.

**Вариант:** использовать consumption.snk при расчёте (если задан), чтобы совпадать с Excel.

### 3. Разный K

Расчёт использует consumption.k. Если K в Excel отличался от consumption.k → btp_calc ≠ btp.

### 4. consumption без fuel param

Пересчёт идёт только по записям EquipmentGroupFuelParam. Если consumption создан импортом Excel, но fuel param для этой группы/года нет — пересчёт не выполняется, _calc остаётся пустым или старым.

### 5. Разные версии БД (database_version_id)

Фильтр по current_version_id. Если consumption и fuel param привязаны к разным версиям — возможны несоответствия.

### 6. Округление (quantize Q6)

Результаты округляются до 6 знаков. Excel мог хранить больше знаков → мелкие расхождения.

### 7. Условия формул (ved, ewtp > 0 и т.д.)

При ved ≤ 1 или qotr ≤ 0: y_calc = 0.  
При ved ≤ 1 или ewtp ≤ 0: btp_calc = 0, sntp_calc = 0.  
При e = 0 в btp_calc: возвращается 0.

Если в Excel логика была другой — будут расхождения.

## Результаты диагностики (2024)

Запуск: `python scripts/diagnose_specific_fuel_consumption_mismatch.py 2024`

**Итого:** consumption=246, расхождений=82, без fuel param=143

### Главная причина: consumption.k = None

У большинства записей с расхождениями **consumption.k = None**. При расчёте btp_calc используется K=0 (z(None)=0), поэтому:
- btp_calc = eurt (вместо eurt - K*(1-ewtp/e)*100)
- bk_calc тоже искажается (зависит от btp_calc)

**Обратный расчёт K** (при каком K btp_calc совпадёт с загруженным btp):

| eg_id | Загружено btp | btp_calc (K=None) | K для совпадения |
|-------|---------------|-------------------|------------------|
| 2467  | 388.96        | 452.69            | **1.5**          |
| 2470  | 259.99        | 293.75            | **1.0**          |
| 2471  | 222.90        | 227.40            | **1.5**          |
| 2476  | 188.54        | 252.72            | **0.7**          |

**Важно:** Excel использует дробные K (1.5, 0.7). Модель `consumption.k` — Integer. При импорте дробные K округляются до целых.

### Другие причины

1. **bk: None vs value** — consumption.bk пусто, но расчёт даёт значение (при ved=1 или e=ewtp возвращается eurt/btp_calc).
2. **snk: None vs value** — consumption.snk пусто, snk_calc берётся из param.snk.
3. **Округление** — малые отличия (diff≈0.000000) из-за quantize Q6.
4. **Нет fuel param** — 143 consumption без соответствующего EquipmentGroupFuelParam, пересчёт для них не выполняется.
5. **param.ewtp=None или param.eurt=None** — при неполных fuel param формулы возвращают 0 или eurt, расчёт может не совпадать с Excel.

### Рекомендуемые действия

1. **Заполнить consumption.k** — импорт «Загрузка коэффициента экономии от теплофикации» или столбец K в импорте рассчитанных значений (добавлен).
2. **Дробный K** — если Excel использует K=1.5, 0.7 и т.п., рассмотреть смену типа `consumption.k` на Numeric.
3. **Проверить источник K в Excel** — откуда брался K при создании файла (Access, отдельный столбец и т.п.).
4. **Запустить диагностику** после заполнения K и повторного пересчёта.

## Запуск диагностики

```bash
python scripts/diagnose_specific_fuel_consumption_mismatch.py [год]
```

Без года — все года. Выводит для каждой записи с расхождением: загруженные и расчётные значения, входные параметры (param) и consumption.k.
