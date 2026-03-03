# API для работы с external_code (универсальными внешними кодами)

## Описание

`external_code` — это универсальный стабильный идентификатор для сущностей системы, который остается неизменным при копировании версий базы данных. Это позволяет внешним системам надежно идентифицировать и запрашивать данные независимо от версии БД.

## Доступные типы сущностей

1. **Station (Станция)** — электростанция
2. **Machine (Агрегат)** — агрегат электростанции (с трехсторонней привязкой: станция - группа оборудования - агрегат)

## API Endpoints

### 1. Получить станцию по external_code

**GET** `/generation/stations/api/external_codes/station/<external_code>`

**Пример запроса:**
```bash
curl http://msk-arm-gs01.ntcees.ru/generation/stations/api/external_codes/station/5aa8d4b9-1348-588a-8974-d3d590e629d7
```

**Пример ответа:**
```json
{
  "type": "Электростанция",
  "external_code": "abc-123-def-456",
  "database_version_id": 7,
  "database_version": "Наименование версии базы данных",
  "id_station": 123,
  "name_station": "Название станции",
  "regional_district": "Наименование субъекта",
  "station_type": "Наименование типа станции",
  "gen_company": "Наименование генерирующей компании",
}
```

### 2. Получить агрегат по external_code (трехсторонняя привязка)

**GET** `/generation/stations/api/external_codes/machine/<external_code>`

`external_code` агрегата формируется из: `external_code` электростанции + `machine_number` + (`machine_name` или `date_exploitation`). При наличии `date_exploitation` он используется вместо имени (имя может слегка меняться между версиями).

**Пример запроса:**
```bash
curl http://msk-arm-gs01.ntcees.ru/generation/stations/api/external_codes/machine/e7a8ed52-10ed-51fc-a521-fcf9649ef2d8
```

**Пример ответа:**
```json
{
  "type": "Агрегат",
  "external_code": "machine-code-123",
  "database_version_id": 7,
  "database_version": "Наименование версии базы данных",
  "id_machine": 789,
  "machine_number": "1",
  "machine_name": "Название агрегата",
  "id_station": 123,
  "station_external_code": "abc-123-def-456",
  "equipment_group": "Наименование группы оборудования",
  "regional_district": "Наименование субъекта",
  "gen_company": "Наименование генерирующей компании",
}
```

### 3. Batch запрос (получить несколько сущностей за раз)

**POST** `/generation/stations/api/external_codes/batch`

Полезно для внешних систем, которым нужно получить данные для множества сущностей за один запрос.

**Пример запроса:**
```bash
curl -X POST http://your-domain/generation/stations/api/external_codes/batch \
  -H "Content-Type: application/json" \
  -d '{
    "stations": ["code1", "code2"],
    "machines": ["code4", "code5"]
  }'
```

**Пример ответа:**
```json
{
  "stations": [
    {
      "external_code": "code1",
      "id": 123,
      "name": "Станция 1",
      "name_so": "СО1"
    },
    {
      "external_code": "code2",
      "id": 124,
      "name": "Станция 2",
      "name_so": "СО2"
    }
  ],
  "machines": [
    {
      "external_code": "code4",
      "id": 789,
      "machine_name": "Агрегат 1",
      "machine_number": "1"
    }
  ]
}
```

## Как это работает на практике

### Сценарий 1: Внешняя система получает external_code из экспорта

1. Внешняя система запрашивает экспорт данных (Excel/CSV)
2. В экспорте содержится столбец `external_code` для каждой сущности
3. Внешняя система сохраняет эти коды у себя
4. При необходимости получения актуальных данных внешняя система использует эти коды для запросов через API

### Сценарий 2: Массовая синхронизация данных

1. Внешняя система собирает список `external_code`, которые нужно обновить
2. Использует batch endpoint для получения всех данных за один запрос:
   ```bash
   POST /generation/stations/api/external_codes/batch
   {
     "stations": ["code1", "code2"],
     "machines": ["code3", "code4", ...]
   }
   ```
3. Обрабатывает полученные данные и синхронизирует свою базу

## Преимущества использования external_code

1. **Стабильность**: Код не меняется при копировании версий БД
2. **Уникальность**: Каждая сущность имеет уникальный код
3. **Независимость от версий**: Внешняя система не зависит от внутренних ID, которые могут меняться
4. **Простота интеграции**: Понятный REST API для получения данных

## Обработка ошибок

Если запрашиваемый `external_code` не найден, API вернет HTTP 404 с соответствующим сообщением.

## Примечания

- Все `external_code` генерируются детерминированно на основе ключевых полей сущностей
- Код станции формируется по приоритету: `name_so`, затем `name_combined`, иначе `name` + `id_regional_district`
- Код для связки «станция‑группа оборудования» формируется на основе `external_code` станции и `id_equipment_group`
- Код для агрегата (Machine): `external_code` станции + `machine_number` + (`machine_name` или `date_exploitation`). При наличии года ввода в эксплуатацию (`date_exploitation`) он предпочтительнее имени.
- При создании новой версии БД все `external_code` сохраняются, что обеспечивает совместимость

## Формирование external_code агрегата (Machine)

Агрегат имеет уникальный `external_code`, который формируется из:
1. **Электростанция** — `external_code` станции
2. **Номер агрегата** — `machine_number` (с нормализацией: «01» → «1»)
3. **Идентификатор** — `machine_name` (нормализованное) или `date_exploitation` (год ввода в эксплуатацию). При наличии `date_exploitation` он предпочтительнее (имя может слегка меняться между версиями БД).

Это обеспечивает:
- Уникальность кода для каждого агрегата в контексте станции
- Стабильность кода при копировании версий БД (date_exploitation устойчивее к изменениям имени)
- Возможность однозначно идентифицировать агрегат внешними системами

**Пример:**
- Станция: `abc-123-def-456`
- Агрегат №1 с годом ввода 2010: `machine-code-123` (station + num + exploitation)
