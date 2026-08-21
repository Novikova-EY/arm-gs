# -*- coding: utf-8 -*-
import re

from sqlalchemy import Integer, Numeric, and_, cast

from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam


class AccessFilterAdapter:
    """
    Мини-адаптер фильтров Access -> SQLAlchemy.

    Поддерживаемый поднабор:
    - простые условия вида: field op value
    - скобки вокруг отдельных условий
    - объединение через AND

    Примеры:
    - (oes=3) and (ved>0)
    - obl=54 and oes=6

    Поля справочника EquipmentGroup: oes, obl, dep, er, fo, main, numb.
    Поле ved — из рабочей таблицы Access «Станции(Схема)» → EquipmentGroupFuelParam.ved
    (год задаётся вызывающим кодом через join/exists), НЕ EquipmentGroup.vedomstvo.

    Не поддерживаются на этом этапе: OR, NOT, LIKE, IS NULL, IN, сложная вложенность.
    """

    GROUP_FIELD_MAP = {
        "oes": EquipmentGroup.oes,
        "obl": EquipmentGroup.obl,
        "dep": EquipmentGroup.dep,
        "er": EquipmentGroup.er,
        "fo": EquipmentGroup.fo,
        "main": EquipmentGroup.main,
        "numb": EquipmentGroup.numb,
    }

    # Обратная совместимость имени: только групповые поля (без ved).
    FIELD_MAP = GROUP_FIELD_MAP

    # Рабочее VED Access на строке параметров за год.
    VED_COLUMN = EquipmentGroupFuelParam.ved

    CONDITION_RE = re.compile(
        r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(=|>=|<=|>|<)\s*(.+?)\s*$",
        re.DOTALL,
    )

    @classmethod
    def _normalize_filter_text(cls, filter_text: object) -> str:
        if filter_text is None:
            return ""
        text = str(filter_text).strip()
        text = re.sub(r"\s+", " ", text)
        return text

    @classmethod
    def _strip_outer_parens(cls, part: str) -> str:
        p = part.strip()
        while p.startswith("(") and p.endswith(")"):
            inner = p[1:-1].strip()
            if not inner:
                break
            p = inner
        return p

    @classmethod
    def iter_conditions(cls, filter_text: object):
        """
        Разбирает AND-условия фильтра.
        Yields: (field_name, operator, converted_value)
        """
        text = cls._normalize_filter_text(filter_text)
        if not text:
            return

        parts = re.split(r"\s+and\s+", text, flags=re.IGNORECASE)
        for part in parts:
            part = cls._strip_outer_parens(part)
            if not part:
                continue

            match = cls.CONDITION_RE.match(part)
            if not match:
                raise ValueError(
                    f"Не удалось разобрать условие Access-фильтра: {part!r}"
                )

            field_name, operator, raw_value = match.groups()
            field_name = field_name.strip().lower()
            raw_value = raw_value.strip().strip("'").strip('"')
            value = cls._convert_value(raw_value)
            yield field_name, operator, value

    @classmethod
    def build_expression(cls, filter_text: object):
        """
        Преобразует Access-фильтр в SQLAlchemy expression только по полям EquipmentGroup.
        Условия по ved пропускаются (их накладывает отбор через FuelParam.ved).
        Возвращает None, если после пропуска ved условий не осталось / фильтр пуст.
        """
        expressions = []
        for field_name, operator, value in cls.iter_conditions(filter_text):
            if field_name == "ved":
                continue
            column = cls.GROUP_FIELD_MAP.get(field_name)
            if column is None:
                raise ValueError(
                    f"Поле {field_name!r} не сопоставлено в AccessFilterAdapter.GROUP_FIELD_MAP"
                )
            expressions.append(cls._compare(column, operator, value))

        if not expressions:
            return None
        return and_(*expressions)

    @classmethod
    def build_ved_expression(cls, filter_text: object, *, ved_column=None):
        """
        Условия фильтра по ved → выражение на колонке FuelParam.ved (по умолчанию).
        None, если в фильтре нет ved.
        """
        column = ved_column if ved_column is not None else cls.VED_COLUMN
        expressions = []
        for field_name, operator, value in cls.iter_conditions(filter_text):
            if field_name != "ved":
                continue
            expressions.append(cls._compare(column, operator, value))
        if not expressions:
            return None
        return and_(*expressions)

    @classmethod
    def filter_has_ved_condition(cls, filter_text: object) -> bool:
        for field_name, _op, _val in cls.iter_conditions(filter_text):
            if field_name == "ved":
                return True
        return False

    @classmethod
    def _compare(cls, column, operator: str, value):
        lhs = cls._lhs_for_value(column, value)
        if operator == "=":
            return lhs == value
        if operator == ">":
            return lhs > value
        if operator == "<":
            return lhs < value
        if operator == ">=":
            return lhs >= value
        if operator == "<=":
            return lhs <= value
        raise ValueError(f"Неподдерживаемый оператор: {operator!r}")

    @staticmethod
    def _convert_value(raw_value: str):
        """
        Преобразует значение из Access-фильтра:
        - 10 -> int
        - 10,5 -> float
        - прочее -> str
        """
        raw_value = raw_value.replace(",", ".")
        try:
            if "." in raw_value:
                return float(raw_value)
            return int(raw_value)
        except ValueError:
            return raw_value

    @staticmethod
    def _lhs_for_value(column, value):
        """
        PostgreSQL: при фактическом VARCHAR в колонке (наследие Access/импорта) сравнение
        ``column > 0`` даёт «оператор не найден». Числовые литералы приводим к тому же типу
        через cast на стороне колонки.
        """
        if isinstance(value, bool):
            return column
        if isinstance(value, int):
            return cast(column, Integer)
        if isinstance(value, float):
            return cast(column, Numeric(30, 10))
        return column
