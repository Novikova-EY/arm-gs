import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


RESULT_DATASETS = {
    "technologies": {
        "title": "Оптимизированные функционалы",
        "dataset": "rational_struct_export_from_java_technologies",
        "columns": (
            "Номер расчета", "Номер точки", "Номер кластера",
            "Отн. недоотпуск", "Вер-ть дефицита", "Уд. стоимость",
            "Ср. зам. цена", "Уд. эмиссия CO2", "Доля тепл. Элст. на угле",
            "Доля ген. мощн. одного вида", "Мин. уровень резервирования",
            "Расчет принят пользователем", "Расчет принят (дата)", "external_code",
        ),
    },
    "powers": {
        "title": "Мощности по технологиям и районам",
        "dataset": "rational_struct_export_from_java_powers",
        "columns": (
            "Номер расчета", "Номер точки", "Номер кластера",
            "Код энергозоны (экспорт)", "Установленная (расчетная) мощност",
            "Тип технологии", "Расчет принят пользователем",
            "Расчет принят (дата)", "external_code", "Дата создания",
        ),
    },
}


def fetch_calculated_values(dataset_key):
    definition = RESULT_DATASETS[dataset_key]
    url = (
        "http://10.31.224.135:8080/api/v1/external-sync/views/ge_stage/v_"
        + definition["dataset"]
    )
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        if exc.code != 404:
            raise
        # API обозначает пустое представление отдельным JSON-ответом с HTTP 404.
        try:
            with exc:
                error_payload = json.load(exc)
        except ValueError:
            raise exc
        if not (
            isinstance(error_payload, dict)
            and error_payload.get("status") == "error"
            and error_payload.get("message")
            == "Представление пусто или не содержит записей для текущей сессии"
        ):
            raise
        payload = {"dataset": definition["dataset"], "rows": []}
    if not isinstance(payload, dict) or payload.get("dataset") not in (
        definition["dataset"], "v_" + definition["dataset"],
    ):
        raise ValueError("API вернул неожиданный набор данных.")
    rows = payload.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("API вернул некорректный список строк.")
    if any(
        not isinstance(value, (str, int, float, bool, type(None)))
        for row in rows for value in row.values()
    ):
        raise ValueError("API вернул некорректные значения ячеек.")
    columns = list(dict.fromkeys(key for row in rows for key in row))
    if not rows:
        columns = list(definition["columns"])
    return {
        "rows": rows,
        "columns": columns,
        "dataset": payload["dataset"],
        "version": payload.get("version", ""),
        "comment": payload.get("comment", ""),
    }
