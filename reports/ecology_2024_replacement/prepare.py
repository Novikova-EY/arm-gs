import hashlib
import json
import re
import runpy
from decimal import Decimal
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = Path(r"z:\НИО-10\АРМ ГС\05. Шаблоны для АРМ ГС\9. Экология\Тест_2024.xlsx")
constants = runpy.run_path(str(ROOT / "app/ecology/services/operating_tes_constants.py"))
sheet = openpyxl.load_workbook(SOURCE, data_only=True)["2024"]
territories = constants["TERRITORIES"][:5]
assert [sheet.cell(1, c).value for c in range(2, 7)] == [
    "Всего", "Станции отрасли", "Промпредприятия", "ОЭС Северо-Запада", "ОЭС Центра"
]
assert len(constants["FUEL_ROWS"]) == 84


def normalize(label):
    return re.sub(r"[^а-яa-z0-9]", "", label.lower().replace("в т.ч.", ""))


aliases = {
    "gas_natural": "естественный газ",
    "coal": "Уголь всего:",
    "khakass": "Хакасский",
    "tuva": "Тувинский (Улуг-хемский)",
    "tarbagatai": "тарабагатайский",
}
payload = {t["slug"]: {} for t in territories}
rows = [(2, "e", "Выработка электроэнергии, млрд.кВт.ч"),
        (3, "q", "Отпуск тепла, тыс.Гкал"),
        (4, "b", "Расход топлива, тыс.тут")]
for number, spec in enumerate(constants["FUEL_ROWS"], 5):
    expected = aliases.get(spec["key"], spec["label"])
    actual = sheet.cell(number, 1).value
    assert normalize(actual) == normalize(expected), (number, actual, expected)
    rows.append((number, constants["FUEL_PARAM_FIELDS"][spec["key"]], actual))

empty_cells = []
for number, field, label in rows:
    for column, territory in enumerate(territories, 2):
        value = sheet.cell(number, column).value
        if value is None:
            empty_cells.append(sheet.cell(number, column).coordinate)
            continue
        assert isinstance(value, (int, float)) and not isinstance(value, bool)
        amount = Decimal(str(value))
        assert amount.is_finite() and amount >= 0
        if field == "e":
            amount *= 1000  # Snapshot stores million kWh, Excel shows billion kWh.
        payload[territory["slug"]][field] = str(amount)

(OUT / "payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
manifest = {
    "source": str(SOURCE), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "database_version_id": 37, "snapshot_id": 65, "year_number": 2024, "scope": "operating",
    "rows": rows, "territories": territories, "empty_cells": empty_cells,
    "numeric_cells": sum(map(len, payload.values())),
    "policy": "Replace entire accepted snapshot; omit empty Excel cells; preserve numeric zero; other territories empty.",
}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: manifest[k] for k in ("numeric_cells", "empty_cells", "source_sha256")}, indent=2))
