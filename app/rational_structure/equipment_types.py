"""Виды оборудования, для которых загружаются данные Техинспекции."""

EQUIPMENT_TYPES = {
    "steam": "Паровые турбины",
    "gas": "Газовые турбины",
    "hydro": "Гидротурбины",
    "boiler_energy": "Энергетические котлы",
    "boiler_water": "Водогрейные котлы",
}

SHEET_TYPES = {
    "Турбины паровые": "steam",
    "Турбины газовые": "gas",
    "Гидротурбины": "hydro",
    "Энергетические котлы": "boiler_energy",
    "Водогрейные котлы": "boiler_water",
}

# Автоматическое сопоставление с агрегатами выполняется только для турбин.
MATCHABLE_TYPES = frozenset({"steam", "gas", "hydro"})

PAGES = {
    "turbines": {
        "title": "Технические характеристики турбин (Техинспекция)",
        "nav_label": "Турбины",
        "equipment_types": ("steam", "gas"),
        "endpoint": "rational_structure_module_bp.technical_characteristics",
    },
    "hydro": {
        "title": "Технические характеристики гидротурбин (Техинспекция)",
        "nav_label": "Гидротурбины",
        "equipment_types": ("hydro",),
        "endpoint": "rational_structure_module_bp.hydro_technical_characteristics",
    },
    "boiler_energy": {
        "title": "Технические характеристики энергетических котлов (Техинспекция)",
        "nav_label": "Энергетические котлы",
        "equipment_types": ("boiler_energy",),
        "endpoint": "rational_structure_module_bp.energy_boiler_technical_characteristics",
    },
    "boiler_water": {
        "title": "Технические характеристики водогрейных котлов (Техинспекция)",
        "nav_label": "Водогрейные котлы",
        "equipment_types": ("boiler_water",),
        "endpoint": "rational_structure_module_bp.water_boiler_technical_characteristics",
    },
}

DEFAULT_PAGE = "turbines"
