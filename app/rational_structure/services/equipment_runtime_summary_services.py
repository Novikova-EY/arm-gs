"""Сводка мероприятий по рассчитанным строкам наработки оборудования."""
from collections import defaultdict
from decimal import Decimal

from openpyxl.utils import get_column_letter


def build_runtime_summary(runtime_rows, year, general_scheme_end_year):
    years = range(year + 1, general_scheme_end_year + 1) if general_scheme_end_year is not None else ()
    columns = [
        {"key": key, "label": label, "text": key != "A", "integer": key == "A"}
        for key, label in (("A", "№"), ("B", "Показатель"), ("C", "Единица измерения"))
    ]
    columns.extend({"key": get_column_letter(index), "label": str(number), "text": False, "integer": False}
                   for index, number in enumerate(years, 4))
    groups = defaultdict(list)
    seen = set()
    for row in runtime_rows:
        # Несколько кодов технического освидетельствования не увеличивают мощность агрегата.
        identity = row["machine_id"], row["pgu_machine_id"]
        if identity in seen:
            continue
        seen.add(identity)
        values = row["values"]
        group = values["K"] or "Без группы оборудования"
        fuel = values["AM"] or "Топливо не задано"
        groups[group, fuel].append(values)
    rows = []
    for number, (event, label) in enumerate((("AS", "Первый ресурс"), ("BC", "Второй ресурс")), 1):
        rows.append({"values": {"A": number, "B": label, "C": None}, "formulas": {}, "errors": []})
        for (group, fuel), equipment in sorted(groups.items()):
            annual = defaultdict(Decimal)
            for values in equipment:
                event_year, power = values[event], values["N"]
                if event_year is not None and event_year in years and power is not None:
                    annual[int(event_year)] += Decimal(str(power))
            values = {"A": None, "B": f"{group} ({fuel})", "C": "МВт"}
            total = Decimal(0)
            for index, number in enumerate(years, 4):
                total += annual[number]
                values[get_column_letter(index)] = total if total else None
            rows.append({"values": values, "formulas": {}, "errors": []})
    return {"name": "Сводка по ресурсам", "columns": columns, "rows": rows, "error_count": 0}
