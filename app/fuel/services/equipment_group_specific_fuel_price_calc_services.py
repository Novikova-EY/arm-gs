# -*- coding: utf-8 -*-
"""
Расчёт полей xxx_c модели EquipmentGroupSpecificFuelPrice по формулам.

Формула: xxx_c = cost.xxx / quantity, если quantity > 0, иначе 0.

Источники quantity (знаменатель):
- FROM_EQUIPMENT_GROUP: EquipmentGroupFuelParam (основные топливные параметры)
- FROM_EXTRA_FUEL: EquipmentGroupExtraFuelParam (дополнительные виды топлива)

Числитель (cost) всегда из EquipmentGroupSpecificFuelCost.
"""
from decimal import Decimal

# Поля, для которых quantity берётся из EquipmentGroupFuelParam (STAN)
FROM_EQUIPMENT_GROUP = [
    "gaz",
    "mazut",
    "torf",
    "isk_gaz",
    "proch",
    "don",
    "podm",
    "pech",
    "kuzn",
    "ural",
    "bashk",
    "kazah",
    "kan",
    "irkut",
    "tung",
    "hak",
    "tuv",
    "bur",
    "chit",
    "amur",
    "urg",
    "ushum",
    "prim",
    "yakut",
    "mag",
    "chukot",
    "kamch",
    "sah",
]

# Поля, для которых quantity берётся из EquipmentGroupExtraFuelParam (DUG)
FROM_EXTRA_FUEL = [
    "gazpp",
    "gaz_prir",
    "disel",
    "maztop",
    "gtt",
    "nft_proch",
    "domen_g",
    "koks_g",
    "prochgaz",
    "tvproch",
    "szh_gaz",
    "inoe",
    "vork",
    "intin",
    "kuzngd",
    "kuznt",
    "kuznss",
    "kuznun",
    "sver",
    "chel",
    "kizel",
    "ekib",
    "maikub",
    "karag",
    "karajyra",
    "teniz",
    "nazar",
    "ibor",
    "berez",
    "per",
    "irbei",
    "kansk",
    "azey",
    "mug",
    "cher",
    "jer",
    "karab",
    "gusin",
    "tugn",
    "okino",
    "har",
    "urt",
    "tataur",
    "tarbag",
    "zab_kam",
    "rai",
    "erk",
    "ogodj",
    "svo",
    "bikin",
    "razdol",
    "hankai",
    "neru",
    "zyryan",
    "pyak",
    "anad",
    "bering",
]


def _nz(value):
    """Аналог Nz(value, 0) из Access."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return Decimal("0")


def _calc_specific_cost(cost_value, qty_value):
    """
    Удельная стоимость = стоимость / количество.
    Если количество <= 0, возвращает 0.
    """
    cost = _nz(cost_value)
    qty = _nz(qty_value)
    if qty <= 0:
        return Decimal("0")
    return cost / qty


def calc_specific_fuel_price_fields(fuel_param, extra_fuel_param, cost):
    """
    Вычисляет все поля xxx_c для EquipmentGroupSpecificFuelPrice.

    Args:
        fuel_param: EquipmentGroupFuelParam или None
        extra_fuel_param: EquipmentGroupExtraFuelParam или None
        cost: EquipmentGroupSpecificFuelCost или None

    Returns:
        dict: {attr_c: Decimal, ...} для всех расчётных полей
    """
    result = {}
    if cost is None:
        return result

    for field in FROM_EQUIPMENT_GROUP:
        qty = getattr(fuel_param, field, None) if fuel_param else None
        cost_val = getattr(cost, field, None)
        result[f"{field}_c"] = _calc_specific_cost(cost_val, qty)

    for field in FROM_EXTRA_FUEL:
        qty = getattr(extra_fuel_param, field, None) if extra_fuel_param else None
        cost_val = getattr(cost, field, None)
        result[f"{field}_c"] = _calc_specific_cost(cost_val, qty)

    return result


def fill_specific_fuel_price_from_calc(price_record, fuel_param, extra_fuel_param, cost):
    """
    Заполняет поля xxx_c на объекте EquipmentGroupSpecificFuelPrice
    вычисленными значениями.

    Args:
        price_record: экземпляр EquipmentGroupSpecificFuelPrice
        fuel_param: EquipmentGroupFuelParam или None
        extra_fuel_param: EquipmentGroupExtraFuelParam или None
        cost: EquipmentGroupSpecificFuelCost или None
    """
    computed = calc_specific_fuel_price_fields(fuel_param, extra_fuel_param, cost)
    for attr, val in computed.items():
        if hasattr(price_record, attr):
            setattr(price_record, attr, val)
