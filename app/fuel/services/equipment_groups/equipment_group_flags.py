"""Расшифровки признаков станции и группы оборудования из БД «Топливо»."""

EQUIPMENT_GROUP_FLAG_LABELS = {
    "d": {
        "": "новая",
        "1": "действующая",
        "9": "демонтирована",
    },
    "r": {
        "": "новая станция",
        "1": "действующая группа оборудования",
        "2": "новая группа оборудования действующей станции",
        "9": "демонтирована",
    },
}

# Скрытые из-за несовпадения региона ячейки — не признак новой станции.
MASKED_FLAG_FILTER_VALUE = -1


def equipment_group_flag_label(field, value):
    code = str(value or "").strip()
    if code == str(MASKED_FLAG_FILTER_VALUE):
        return "–"
    if code == "0":
        code = ""
    return EQUIPMENT_GROUP_FLAG_LABELS[field].get(code, code)
