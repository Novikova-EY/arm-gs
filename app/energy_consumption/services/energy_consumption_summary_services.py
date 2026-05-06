from __future__ import annotations

import copy
import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy.orm import selectinload

from app.common.services.get_services.years.years_get_services import get_year_feature_dict
from app.common.services.help_services import format_decimal_trim_for_display
from app.energy_consumption.models.energy_systems.ees_energy_consumption_parameter_model import (
    EesDemandParameter,
)
from app.energy_consumption.models.energy_systems.centralized_zone_energy_consumption_parameter_model import (
    CentralizedZoneDemandParameter,
)
from app.energy_consumption.models.energy_systems.ees_russia_energy_consumption_parameter_model import (
    EesRussiaDemandParameter,
)
from app.energy_consumption.models.energy_systems.ees_russia_with_nt_energy_consumption_parameter_model import (
    EesRussiaWithNtDemandParameter,
)
from app.energy_consumption.models.energy_systems.energy_system_type_energy_consumption_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.energy_consumption.models.energy_systems.energy_unit_energy_consumption_parameter_model import (
    EnergyUnitDemandParameter,
)
from app.energy_consumption.models.energy_systems.regional_energy_system_energy_consumption_parameter_model import (
    RegionalEnergySystemDemandParameter,
)
from app.energy_consumption.models.energy_systems.synchronous_area_energy_consumption_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.energy_consumption.models.territories.federal_district_energy_consumption_parameter_model import (
    FederalDistrictDemandParameter,
)
from app.energy_consumption.models.territories.regional_district_energy_consumption_parameter_model import (
    RegionalDistrictDemandParameter,
)
from app.energy_consumption.models.territories.russia_federation_energy_consumption_parameter_model import (
    RussiaFederationDemandParameter,
)
from app.energy_consumption.models.territories.russia_federation_with_nt_energy_consumption_parameter_model import (
    RussiaFederationWithNtDemandParameter,
)
from app.energy_consumption.services import energy_consumption_parameter_services as dps
from app.energy_consumption.models.energy_systems.energy_zone_energy_consumption_parameter_model import (
    EnergyZoneDemandParameter,
)
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict


PLACEHOLDER_NAMES = {"не указано", "не указано2"}

# Не показывать в сводке по ФО (экран и Excel).
_FEDERAL_DISTRICT_SUMMARY_EXCLUDED_NAMES_CF = frozenset({"новые территории"})


def _federal_district_excluded_from_summary(fd: FederalDistrict) -> bool:
    name = (getattr(fd, "name", None) or "").strip()
    cf = name.casefold()
    for prefix in ("фо - ", "фо — "):
        p = prefix.casefold()
        if cf.startswith(p):
            cf = cf[len(prefix) :].strip()
            break
    return cf in _FEDERAL_DISTRICT_SUMMARY_EXCLUDED_NAMES_CF

# Округление из URL влияет только на эти показатели; полная точность — в title/data-db-full.
_NUMERIC_ROUNDING_TOOLTIP_KEYS = frozenset(
    {
        "max_power",
        "combined_on_oes",
        "combined_on_ees",
        "combined_on_es",
        "combined_on_ez",
        "combined_on_fo",
        "combined_on_cz",
        "calculated_max_power_mw",
        "calculated_combined_on_ees_mw",
    }
)

BASE_PARAMETERS: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
)
# Строка объединённой энергосистемы (ОЭС) в сводке «по энергосистемам».
PARAMETERS_UES_OES: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("calculated_max_power_mw", "Расчетный максимум ОЭС, МВт"),
    ("combined_on_ees", "Совмещенный на ЕЭС, МВт"),
    ("calculated_combined_on_ees_mw", "Расчетный совмещенный на ЕЭС, МВт"),
)
PARAMETERS_WITH_OES_AND_EES: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_oes", "Совмещенный на ОЭС, МВт"),
    ("combined_on_ees", "Совмещенный на ЕЭС, МВт"),
)
PARAMETERS_WITH_OES_EES_AND_ES: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_oes", "Совмещенный на ОЭС, МВт"),
    ("combined_on_ees", "Совмещенный на ЕЭС, МВт"),
    ("combined_on_es", "Совмещенный на ЭС, МВт"),
)
# Федеральный округ
PARAMETERS_FEDERAL_DISTRICT: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_cz", "Совмещенный на централизованную зону, МВт"),
)
# Субъект РФ на сводке по ФО: без ОЭС / ЕЭС / ЭС / ценовой зоны (только базовые + «на ФО»)
PARAMETERS_SUBJECT_FD_SUMMARY: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_fo", "Совмещенный на ФО, МВт"),
)
# Региональная энергосистема на сводке по энергозонам: «на энергозону» (ОЭС/ЕЭС — на странице по ОЭС)
PARAMETERS_RES: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_ez", "Совмещенный на энергозону, МВт"),
)
# Энергозона (в модели только базовые показатели + совмещённый на ЕЭС)
PARAMETERS_ENERGY_ZONE: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_ees", "Совмещенный на ЕЭС, МВт"),
)


@dataclass(slots=True)
class SummaryEntity:
    label: str
    depth: int
    parameters: tuple[tuple[str, str], ...]
    demand_rows: list[Any]
    entity_kind: str = "default"
    children: list["SummaryEntity"] = field(default_factory=list)
    # Имя класса модели SQLAlchemy (whitelist в save_demand_summary_cell).
    demand_model_name: str | None = None
    # Для создания строки без существующего среза: колонка FK и id родителя (как в get_demand_rows).
    parent_fk_column: str | None = None
    parent_id: int | None = None
    # Справочные id для фильтров сводки (ветка ЕЭС / ФО / энергозоны).
    id_union_energy_system: int | None = None
    id_regional_energy_system: int | None = None
    id_regional_district: int | None = None
    id_energy_unit: int | None = None
    id_federal_district: int | None = None
    id_energy_zone: int | None = None
    id_synchronous_area: int | None = None


def _synchronous_area_display_label(sa: SynchronousArea) -> str:
    num = (getattr(sa, "number", None) or "").strip()
    name = (getattr(sa, "name", None) or "").strip()
    if num:
        return f"{num} — {name}"
    return name


def _shift_summary_entity_depth(e: SummaryEntity, delta: int) -> SummaryEntity:
    d = int(e.depth) if e.depth is not None else 0
    new_d = max(0, d + delta)
    new_children = [_shift_summary_entity_depth(c, delta) for c in e.children]
    return replace(e, depth=new_d, children=new_children)


def _oes_promote_subjects_only_under_ees_russia(
    entities: list[SummaryEntity],
    f_rd: frozenset[int],
) -> list[SummaryEntity]:
    """При фильтре по субъекту — под «ЕЭС России (без НТ)» только субъекты (без уровней ОЭС и РЭС)."""
    if not f_rd:
        return entities
    ues_dn = UnionEnergySystemDemandParameter.__name__
    rd_dn = RegionalDistrictDemandParameter.__name__
    out: list[SummaryEntity] = []
    for e in entities:
        if e.entity_kind != "group-root" or e.label != "ЕЭС России (без НТ)":
            out.append(e)
            continue
        promoted: list[SummaryEntity] = []
        for child in e.children:
            if child.entity_kind == "synchronous_area":
                continue
            if child.demand_model_name != ues_dn:
                promoted.append(child)
                continue
            for res in child.children:
                for sub in res.children:
                    if sub.demand_model_name != rd_dn:
                        continue
                    rid = sub.id_regional_district
                    if rid is None or rid not in f_rd:
                        continue
                    promoted.append(_shift_summary_entity_depth(sub, -2))
        out.append(replace(e, children=promoted))
    return out


def _oes_promote_energy_units_only_under_ees_russia(
    entities: list[SummaryEntity],
    f_eu: frozenset[int],
) -> list[SummaryEntity]:
    """При фильтре по энергоузлу — под «ЕЭС России (без НТ)» только энергоузлы (без ОЭС, РЭС, субъекта)."""
    if not f_eu:
        return entities
    eu_dn = EnergyUnitDemandParameter.__name__

    def walk_collect(node: SummaryEntity, promoted: list[SummaryEntity]) -> None:
        if node.demand_model_name == eu_dn:
            euid = node.id_energy_unit
            if euid is not None and euid in f_eu:
                d = int(node.depth) if node.depth is not None else 0
                delta = -(d - 1) if d > 1 else 0
                promoted.append(_shift_summary_entity_depth(node, delta))
                return
        for c in node.children:
            walk_collect(c, promoted)

    out: list[SummaryEntity] = []
    for e in entities:
        if e.entity_kind != "group-root" or e.label != "ЕЭС России (без НТ)":
            out.append(e)
            continue
        promoted: list[SummaryEntity] = []
        for child in e.children:
            if child.entity_kind == "synchronous_area":
                continue
            walk_collect(child, promoted)
        out.append(replace(e, children=promoted))
    return out


def _oes_promote_res_only_under_ees_russia(
    entities: list[SummaryEntity],
    f_res: frozenset[int],
) -> list[SummaryEntity]:
    """При фильтре по РЭС — только строки РЭС (без ОЭС, субъектов и энергоузлов)."""
    if not f_res:
        return entities
    ues_dn = UnionEnergySystemDemandParameter.__name__
    res_dn = RegionalEnergySystemDemandParameter.__name__
    out: list[SummaryEntity] = []
    for e in entities:
        if e.entity_kind != "group-root" or e.label != "ЕЭС России (без НТ)":
            out.append(e)
            continue
        promoted: list[SummaryEntity] = []
        for child in e.children:
            if child.entity_kind == "synchronous_area":
                continue
            if child.demand_model_name != ues_dn:
                continue
            for res in child.children:
                if res.demand_model_name != res_dn:
                    continue
                rid = res.id_regional_energy_system
                if rid is None or rid not in f_res:
                    continue
                d = int(res.depth) if res.depth is not None else 0
                delta = -(d - 1) if d > 1 else 0
                promoted.append(replace(_shift_summary_entity_depth(res, delta), children=[]))
        out.append(replace(e, children=promoted))
    return out


def _build_oes_raw_entities(
    *,
    always_show_subject_row_under_res: bool = False,
) -> list[SummaryEntity]:
    """Полное дерево сводки по ОЭС без территориальных фильтров (для объединения выборов и «без фильтра»)."""
    entities: list[SummaryEntity] = [
        _standalone_entity(
            "Россия (с НТ)",
            RussiaFederationWithNtDemandParameter,
            BASE_PARAMETERS,
            entity_kind="oes_top_aggregate",
        ),
        _standalone_entity(
            "Россия (без НТ)",
            RussiaFederationDemandParameter,
            BASE_PARAMETERS,
            entity_kind="oes_top_aggregate",
        ),
        _standalone_entity(
            "ЭЭС",
            EesDemandParameter,
            BASE_PARAMETERS,
            entity_kind="oes_top_aggregate",
        ),
        _standalone_entity(
            "ЕЭС России (с НТ)",
            EesRussiaWithNtDemandParameter,
            BASE_PARAMETERS,
            entity_kind="oes_top_aggregate",
        ),
    ]

    ees_without_nt = _standalone_entity(
        "ЕЭС России (без НТ)",
        EesRussiaDemandParameter,
        BASE_PARAMETERS,
        entity_kind="group-root",
    )
    ees_without_nt.children = (
        _build_synchronous_area_entities(depth=1)
        + _build_ues_entities_filtered(
            _is_ees_branch,
            always_show_subject_row_under_res=always_show_subject_row_under_res,
        )
    )
    entities.append(ees_without_nt)

    tites_entity = _build_tites_entity()
    if tites_entity is not None:
        entities.append(tites_entity)
    return entities


def _strip_oes_ees_russia_nt_parent_aggregate(entities: list[SummaryEntity]) -> list[SummaryEntity]:
    """Убирает строки-показатели у агрегата «ЕЭС России (без НТ)» при территориальном фильтре."""
    out: list[SummaryEntity] = []
    for e in entities:
        if e.entity_kind == "group-root" and e.label == "ЕЭС России (без НТ)":
            out.append(
                replace(
                    e,
                    parameters=tuple(),
                    demand_rows=[],
                    demand_model_name=None,
                    parent_fk_column=None,
                    parent_id=None,
                )
            )
        else:
            out.append(e)
    return out


def build_oes_summary_context(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    oes_territory_ordered: tuple[list[int], list[int], list[int], list[int]] | None = None,
    avg_temp_uses_global_rounding: bool = False,
) -> dict[str, Any]:
    """Сводка по ОЭС (GET ds_ues, ds_res, ds_rd, ds_eu).

    Набор строк показателей по каждой сущности не урезается территориальными фильтрами; скрытие
    отдельных параметров — только через модальное окно «Наименование параметров» (и ``visible_rows`` при выгрузке).

    При сочетании фильтров нижний уровень сужается **отдельно в каждой ветке родителя** (как на
    сводках по ФО и энергозонам): например, выбранные субъекты РФ относятся только к одной ОЭС —
    под остальными выбранными ОЭС показываются все РЭС/субъекты/энергорайоны этой ветки; то же
    для РЭС ↔ субъектов и субъектов ↔ энергорайонов.

    Ровно один id: для одной РЭС, одного субъекта или одного энергорайона — прежнее поднятие
    строки под «ЕЭС России (без НТ)»; для одной ОЭС — полное поддерево (РЭС и ниже).
    """
    years = list(range(start_year, end_year + 1))
    ues_l, res_l, rd_l, eu_l = ([], [], [], [])
    if oes_territory_ordered is not None:
        ues_l, res_l, rd_l, eu_l = oes_territory_ordered

    has_territory_selection = bool(ues_l or res_l or rd_l or eu_l)

    if has_territory_selection:
        base_entities = copy.deepcopy(
            _build_oes_raw_entities(always_show_subject_row_under_res=bool(rd_l))
        )
        base_entities = _strip_oes_ees_russia_nt_parent_aggregate(base_entities)
        f_ues = frozenset(ues_l)
        f_res = frozenset(res_l)
        f_rd = frozenset(rd_l)
        f_eu = frozenset(eu_l)
        ent = prune_summary_entities_oes(base_entities, f_ues, f_res, f_rd, f_eu, frozenset())
        total_ids = len(ues_l) + len(res_l) + len(rd_l) + len(eu_l)
        # Только ОЭС в URL — полное поддерево (РЭС → субъект → энергорайон), без «поднятия» одной строки ОЭС.
        if total_ids == 1:
            if eu_l:
                ent = _oes_promote_energy_units_only_under_ees_russia(ent, f_eu)
            elif rd_l:
                ent = _oes_promote_subjects_only_under_ees_russia(ent, f_rd)
            elif res_l:
                ent = _oes_promote_res_only_under_ees_russia(ent, f_res)
        summary_rows = _flatten_entities(
            ent, years, rounding_digits, avg_temp_uses_global_rounding=avg_temp_uses_global_rounding
        )
        ctx = _build_summary_context(
            entities=[],
            page_title="Максимумы потребления мощности по энергосистемам",
            active_summary="oes",
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            filter_year_list=filter_year_list,
            avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        )
        ctx["summary_rows"] = summary_rows
        return ctx

    entities = _build_oes_raw_entities(always_show_subject_row_under_res=False)
    return _build_summary_context(
        entities=entities,
        page_title="Максимумы потребления мощности по энергосистемам",
        active_summary="oes",
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )


def build_federal_district_summary_context(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    fo_filter_sets: tuple[frozenset[int], frozenset[int]] | None = None,
    avg_temp_uses_global_rounding: bool = False,
) -> dict[str, Any]:
    """Сводка по ФО и субъектам РФ (GET ds_fd, ds_rd).

    Набор строк показателей по сущности не урезается территориальными фильтрами; скрытие
    параметров — модальное окно «Наименование параметров» и ``visible_rows`` при выгрузке.

    Без фильтров — ЦЗ и полное дерево по всем ФО со всеми субъектами.

    Только ``ds_fd`` — каждая выбранная строка ФО и **все** субъекты этих округов.

    ``ds_fd`` + ``ds_rd`` — строка по каждому выбранному ФО; субъекты сужаются **отдельно по
    каждому округу**: если в ``ds_rd`` есть субъекты этого ФО — показываются только они, если
    все отмеченные субъекты из других ФО — под данным ФО выводятся **все** его субъекты.

    Только ``ds_rd`` (без ``ds_fd``) — плоский список строк по субъектам без уровня ФО (как в Excel).
    """
    entities: list[SummaryEntity] = [
        _standalone_entity(
            "Централизованная зона",
            CentralizedZoneDemandParameter,
            BASE_PARAMETERS,
            entity_kind="centralized_zone",
        ),
    ]
    entities.extend(_build_federal_district_entities())

    if fo_filter_sets is not None:
        f_fd, f_rd = fo_filter_sets
        if f_fd or f_rd:
            entities = prune_summary_entities_fo(entities, f_fd, f_rd)

    return _build_summary_context(
        entities=entities,
        page_title="Максимумы потребления мощности по ФО",
        active_summary="fo",
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )


def _build_ez_raw_entities() -> list[SummaryEntity]:
    entities: list[SummaryEntity] = [
        _standalone_entity(
            "Централизованная зона",
            CentralizedZoneDemandParameter,
            BASE_PARAMETERS,
            entity_kind="centralized_zone",
        ),
    ]
    entities.extend(_build_energy_zone_entities())
    return entities


def build_energy_zones_summary_context(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    ez_territory_ordered: tuple[list[int], list[int]] | None = None,
    avg_temp_uses_global_rounding: bool = False,
) -> dict[str, Any]:
    """Сводка по энергозонам (GET ds_ez, ds_res).

    Набор строк показателей по сущности не урезается территориальными фильтрами; скрытие
    параметров — модальное окно «Наименование параметров» и ``visible_rows`` при выгрузке.

    Без фильтров — ЦЗ и полное дерево энергозона → РЭС → …

    Только ``ds_ez`` — выбранные зоны со всеми РЭС внутри.

    ``ds_ez`` + ``ds_res`` — каждая выбранная зона; РЭС сужаются **по зоне**: если в ``ds_res``
    есть РЭС из этой зоны — только они, иначе все РЭС зоны (как на сводке по ФО).

    Только ``ds_res`` (без ``ds_ez``) — плоский список по выбранным РЭС без строки энергозоны.
    """
    years = list(range(start_year, end_year + 1))
    ez_l: list[int] = []
    res_l: list[int] = []
    if ez_territory_ordered is not None:
        ez_l, res_l = ez_territory_ordered

    if ez_l or res_l:
        base_entities = copy.deepcopy(_build_ez_raw_entities())
        f_ez = frozenset(ez_l)
        f_res = frozenset(res_l)
        ent = prune_summary_entities_ez(base_entities, f_ez, f_res)
        if _ez_res_only_flat_mode(f_ez, f_res):
            ent = _flatten_energy_zone_parents_when_res_filtered(ent)
        summary_rows = _flatten_entities(
            ent, years, rounding_digits, avg_temp_uses_global_rounding=avg_temp_uses_global_rounding
        )
        ctx = _build_summary_context(
            entities=[],
            page_title="Максимумы потребления мощности по энергозонам",
            active_summary="ez",
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            filter_year_list=filter_year_list,
            avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        )
        ctx["summary_rows"] = summary_rows
        return ctx

    entities = _build_ez_raw_entities()
    return _build_summary_context(
        entities=entities,
        page_title="Максимумы потребления мощности по энергозонам",
        active_summary="ez",
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )


def build_oes_summary_context_coeff(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    oes_territory_ordered: tuple[list[int], list[int], list[int], list[int]] | None = None,
) -> dict[str, Any]:
    """Те же данные и логика, что у «Максимумы по энергосистемам»; отдельный экран и заголовок."""
    ctx = build_oes_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        oes_territory_ordered=oes_territory_ordered,
        avg_temp_uses_global_rounding=True,
    )
    ctx["page_title"] = "Коэффициенты и совмещенные максимумы по энергосистемам"
    return ctx


def build_federal_district_summary_context_coeff(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    fo_filter_sets: tuple[frozenset[int], frozenset[int]] | None = None,
) -> dict[str, Any]:
    ctx = build_federal_district_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        fo_filter_sets=fo_filter_sets,
        avg_temp_uses_global_rounding=True,
    )
    ctx["page_title"] = "Коэффициенты и совмещенные максимумы по ФО"
    return ctx


def build_energy_zones_summary_context_coeff(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    ez_territory_ordered: tuple[list[int], list[int]] | None = None,
) -> dict[str, Any]:
    ctx = build_energy_zones_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        ez_territory_ordered=ez_territory_ordered,
        avg_temp_uses_global_rounding=True,
    )
    ctx["page_title"] = "Коэффициенты и совмещенные максимумы по энергозонам"
    return ctx


def _build_summary_context(
    *,
    entities: list[SummaryEntity],
    page_title: str,
    active_summary: str,
    rounding_digits: int,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    avg_temp_uses_global_rounding: bool = False,
) -> dict[str, Any]:
    years = list(range(start_year, end_year + 1))
    _yf = get_year_feature_dict() or {}
    year_is_plan: dict[int, bool] = {}
    for y in years:
        nm = _yf.get(y)
        year_is_plan[y] = (
            str(nm).strip().lower().replace(" ", "") == "план" if nm is not None else False
        )
    return {
        "page_title": page_title,
        "summary_rows": _flatten_entities(
            entities, years, rounding_digits, avg_temp_uses_global_rounding=avg_temp_uses_global_rounding
        ),
        "years": years,
        "year_features": _yf,
        "year_is_plan": year_is_plan,
        "rounding_digits": rounding_digits,
        "active_summary": active_summary,
        "start_year": start_year,
        "end_year": end_year,
        "filter_year_list": filter_year_list,
    }


OES_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_oes",
        "calculated_max_power_mw",
        "combined_on_ees",
        "calculated_combined_on_ees_mw",
        "combined_on_es",
    }
)
FO_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_cz",
        "combined_on_fo",
    }
)
EZ_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_ez",
        "combined_on_ees",
    }
)


def filter_summary_rows_for_parameter_keys(
    summary_rows: list[dict[str, Any]],
    visible_keys: frozenset[str],
) -> list[dict[str, Any]]:
    """Усечение по выбору пользователя (GET ``visible_rows`` при экспорте Excel), не по территории."""
    if not visible_keys:
        return list(summary_rows)
    keys = visible_keys
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        block = summary_rows[i : i + block_size]
        filtered_block = [r for r in block if (r.get("parameter_key") or "") in keys]
        for j, r in enumerate(filtered_block):
            rc = dict(r)
            rc["show_entity_cell"] = j == 0
            rc["entity_rowspan"] = len(filtered_block)
            out.append(rc)
        i += block_size
    return out


def _parse_summary_cell_float(value: Any) -> float | None:
    """Разбор числа из ячейки сводки (как на экране: пробелы, запятая)."""
    if value in (None, ""):
        return None
    s = str(value).strip()
    if s in ("—", "-"):
        return None
    s = s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    s = s.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        x = float(s)
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def _union_energy_system_id_from_flat_row(row: dict[str, Any]) -> int | None:
    """id ОЭС в строке сводки: id_union_energy_system или parent_id при parent_fk = id_union_energy_system."""
    raw = row.get("id_union_energy_system")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    if row.get("parent_fk_column") == "id_union_energy_system" and row.get("parent_id") is not None:
        try:
            return int(row["parent_id"])
        except (TypeError, ValueError):
            pass
    return None


def _coeff_union_res_sum_year(y: int, coeff_base_year: int) -> bool:
    """Год входит в отчётный интервал (N−9…N) или среднесрочный (N+1…N+6) сводки коэффициентов."""
    return (
        (coeff_base_year - 9) <= y <= coeff_base_year
        or (coeff_base_year + 1) <= y <= (coeff_base_year + 6)
    )


def slice_coeff_summary_for_lazy_long_segment(
    context: dict[str, Any],
    coeff_n: int,
    *,
    include_long: bool,
) -> None:
    """
    Без coeff_include_long в URL на «Коэффициенты…» не отдаём долгосрочные годы (N+7…N+18) в разметке.
    Полный диапазон остаётся в экспорте и при coeff_include_long=1.
    """
    context["coeff_include_long"] = include_long
    if include_long:
        return
    years_full: list[int] = list(context.get("years") or [])
    if not years_full:
        return
    cutoff = int(coeff_n) + 6
    keep_idx = [i for i, y in enumerate(years_full) if int(y) <= cutoff]
    if len(keep_idx) == len(years_full):
        return
    new_years = [years_full[i] for i in keep_idx]
    context["years"] = new_years
    yip = context.get("year_is_plan") or {}
    context["year_is_plan"] = {y: bool(yip.get(y, False)) for y in new_years}
    context["start_year"] = min(new_years)
    context["end_year"] = max(new_years)
    slice_keys = (
        "year_values",
        "year_row_ids",
        "year_numeric_tooltips",
        "year_k_values",
        "year_k_full_tooltips",
    )
    for row in context.get("summary_rows") or []:
        if not isinstance(row, dict):
            continue
        for key in slice_keys:
            lst = row.get(key)
            if not isinstance(lst, list) or not keep_idx:
                continue
            if len(lst) == len(years_full):
                row[key] = [lst[i] for i in keep_idx]
            elif all(i < len(lst) for i in keep_idx):
                row[key] = [lst[i] for i in keep_idx]


def _aggregate_res_combined_on_oes_mw_sum_by_union_for_medium_years(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    coeff_base_year: int,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный на ОЭС, МВт» по строкам РЭС внутри каждого ОЭС (отчётный N−9…N и среднесрочный N+1…N+6).

    На УЭС для «Расчетный максимум ОЭС, МВт» эти годы задаются этой суммой.
    """
    n_y = len(years)
    out: dict[int, list[float | None]] = {}

    def _tot(uid: int) -> list[float | None]:
        if uid not in out:
            out[uid] = [None] * n_y
        return out[uid]

    dm_res = RegionalEnergySystemDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_res:
            continue
        if r.get("parameter_key") != "combined_on_oes":
            continue
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is None:
            continue
        row_tot = _tot(uid)
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if not _coeff_union_res_sum_year(y, coeff_base_year):
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            if row_tot[j] is None:
                row_tot[j] = float(add)
            else:
                row_tot[j] = float(row_tot[j]) + float(add)
    return out


def _aggregate_res_combined_on_ees_mw_sum_by_union_for_medium_years(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    coeff_base_year: int,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный на ЕЭС, МВт» по строкам РЭС внутри каждого ОЭС (отчётный N−9…N и среднесрочный N+1…N+6).

    На УЭС для «Расчетный совмещенный на ЕЭС, МВт» эти годы задаются этой суммой.
    """
    n_y = len(years)
    out: dict[int, list[float | None]] = {}

    def _tot(uid: int) -> list[float | None]:
        if uid not in out:
            out[uid] = [None] * n_y
        return out[uid]

    dm_res = RegionalEnergySystemDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_res:
            continue
        if r.get("parameter_key") != "combined_on_ees":
            continue
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is None:
            continue
        row_tot = _tot(uid)
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if not _coeff_union_res_sum_year(y, coeff_base_year):
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            if row_tot[j] is None:
                row_tot[j] = float(add)
            else:
                row_tot[j] = float(row_tot[j]) + float(add)
    return out


def enrich_summary_rows_coeff_k_columns(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    year_is_plan: dict[int, bool],
    *,
    coeff_base_year: int | None = None,
) -> None:
    """k = значение показателя / макс. мощность того же года (строка max_power в блоке — знаменатель; для самой строки max_power k не считается)."""
    n_y = len(years)
    res_ees_sum_by_union: dict[int, list[float | None]] = {}
    res_oes_sum_by_union: dict[int, list[float | None]] = {}
    if coeff_base_year is not None:
        res_ees_sum_by_union = _aggregate_res_combined_on_ees_mw_sum_by_union_for_medium_years(
            summary_rows, years, coeff_base_year
        )
        res_oes_sum_by_union = _aggregate_res_combined_on_oes_mw_sum_by_union_for_medium_years(
            summary_rows, years, coeff_base_year
        )
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        block = summary_rows[i : i + block_size]
        max_row = next((r for r in block if r.get("parameter_key") == "max_power"), None)
        denoms: list[float | None] = [None] * n_y
        if max_row is not None:
            yv = max_row.get("year_values") or []
            denoms = [
                _parse_summary_cell_float(yv[j] if j < len(yv) else None) for j in range(n_y)
            ]

        block_uid = _union_energy_system_id_from_flat_row(block[0])
        for r in block:
            pk = r.get("parameter_key") or ""
            dm_n_pre = r.get("demand_model_name")
            if (
                coeff_base_year is not None
                and dm_n_pre == UnionEnergySystemDemandParameter.__name__
                and pk == "calculated_max_power_mw"
                and block_uid is not None
            ):
                mids = res_oes_sum_by_union.get(block_uid)
                if mids is None:
                    mids = [None] * n_y
                yv_p = list(r.get("year_values") or [])
                ynt_p = list(r.get("year_numeric_tooltips") or [])
                while len(yv_p) < n_y:
                    yv_p.append("—")
                while len(ynt_p) < n_y:
                    ynt_p.append("")
                for j in range(n_y):
                    yt = years[j]
                    if not _coeff_union_res_sum_year(yt, coeff_base_year):
                        continue
                    s = mids[j]
                    if s is not None:
                        yv_p[j] = _format_numeric(s, rounding_digits)
                        ynt_p[j] = _format_full_numeric_tooltip(s)
                    else:
                        yv_p[j] = "—"
                        ynt_p[j] = ""
                r["year_values"] = yv_p
                r["year_numeric_tooltips"] = ynt_p
            if (
                coeff_base_year is not None
                and dm_n_pre == UnionEnergySystemDemandParameter.__name__
                and pk == "calculated_combined_on_ees_mw"
                and block_uid is not None
            ):
                mids = res_ees_sum_by_union.get(block_uid)
                if mids is None:
                    mids = [None] * n_y
                yv_p = list(r.get("year_values") or [])
                ynt_p = list(r.get("year_numeric_tooltips") or [])
                while len(yv_p) < n_y:
                    yv_p.append("—")
                while len(ynt_p) < n_y:
                    ynt_p.append("")
                for j in range(n_y):
                    yt = years[j]
                    if not _coeff_union_res_sum_year(yt, coeff_base_year):
                        continue
                    s = mids[j]
                    if s is not None:
                        yv_p[j] = _format_numeric(s, rounding_digits)
                        ynt_p[j] = _format_full_numeric_tooltip(s)
                    else:
                        yv_p[j] = "—"
                        ynt_p[j] = ""
                r["year_values"] = yv_p
                r["year_numeric_tooltips"] = ynt_p
            yvals = r.get("year_values") or []
            k_list: list[str] = []
            k_tt: list[str] = []
            for j in range(n_y):
                y = years[j]
                dm_n = r.get("demand_model_name")
                res_oes_or_ees_medium = (
                    coeff_base_year is not None
                    and (coeff_base_year + 1) <= y <= (coeff_base_year + 6)
                    and pk in ("combined_on_oes", "combined_on_ees")
                    and dm_n == "RegionalEnergySystemDemandParameter"
                )
                ues_plan_k_exempt = False
                if (
                    coeff_base_year is not None
                    and dm_n == UnionEnergySystemDemandParameter.__name__
                ):
                    if pk in ("calculated_max_power_mw", "calculated_combined_on_ees_mw"):
                        ues_plan_k_exempt = _coeff_union_res_sum_year(y, coeff_base_year)
                    elif pk == "combined_on_ees":
                        ues_plan_k_exempt = (
                            (coeff_base_year + 1) <= y <= (coeff_base_year + 6)
                        )
                yrsk = r.get("year_coeff_k_stored") or []
                sk_val = yrsk[j] if j < len(yrsk) else None
                sk_parsed = (
                    _parse_summary_cell_float(sk_val)
                    if sk_val not in (None, "", "—")
                    else None
                )
                if sk_parsed is not None and pk not in (
                    "peak_datetime",
                    "avg_temp",
                    "max_power",
                ):
                    if dm_n == "RegionalEnergySystemDemandParameter" and pk in (
                        "combined_on_oes",
                        "combined_on_ees",
                    ):
                        k_list.append(_format_numeric(sk_parsed, rounding_digits))
                        k_tt.append(_format_full_numeric_tooltip(sk_parsed))
                        continue
                    if dm_n == "UnionEnergySystemDemandParameter" and pk in (
                        "calculated_max_power_mw",
                        "combined_on_ees",
                        "calculated_combined_on_ees_mw",
                    ):
                        if (
                            coeff_base_year is not None
                            and pk
                            in (
                                "calculated_max_power_mw",
                                "calculated_combined_on_ees_mw",
                            )
                            and _coeff_union_res_sum_year(y, coeff_base_year)
                        ):
                            # МВт для этих лет только что заданы суммой по РЭС (см. выше).
                            # Старый coeff_k из БД мог относиться к другой семантике — пересчитываем k из year_values/max_power.
                            pass
                        else:
                            k_list.append(_format_numeric(sk_parsed, rounding_digits))
                            k_tt.append(_format_full_numeric_tooltip(sk_parsed))
                            continue
                if (
                    year_is_plan.get(y)
                    and pk != "max_power"
                    and not res_oes_or_ees_medium
                    and not ues_plan_k_exempt
                ):
                    k_list.append("—")
                    k_tt.append("")
                    continue
                if pk in ("peak_datetime", "avg_temp", "max_power"):
                    k_list.append("—")
                    k_tt.append("")
                    continue
                num = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
                d = denoms[j] if j < len(denoms) else None
                if num is not None and d is not None and d > 0:
                    ratio = num / d
                    k_list.append(_format_numeric(ratio, rounding_digits))
                    k_tt.append(_format_full_numeric_tooltip(ratio))
                else:
                    k_list.append("—")
                    k_tt.append("")
            r["year_k_values"] = k_list
            r["year_k_full_tooltips"] = k_tt
            if (
                coeff_base_year is not None
                and r.get("demand_model_name") == UnionEnergySystemDemandParameter.__name__
                and (r.get("parameter_key") or "")
                in ("calculated_max_power_mw", "calculated_combined_on_ees_mw")
            ):
                yc = list(r.get("year_coeff_k_stored") or [])
                if len(yc) < n_y:
                    yc.extend(["—"] * (n_y - len(yc)))
                for j in range(n_y):
                    yt = years[j]
                    if _coeff_union_res_sum_year(yt, coeff_base_year):
                        yc[j] = k_list[j] if j < len(k_list) else "—"
                r["year_coeff_k_stored"] = yc
            dm_block = r.get("demand_model_name")
            pk_medium_res = ("combined_on_oes", "combined_on_ees")
            pk_medium_ues_sync = (
                "calculated_max_power_mw",
                "combined_on_ees",
            )
            if coeff_base_year is not None and dm_block == "RegionalEnergySystemDemandParameter" and pk in pk_medium_res:
                yv_mw = list(r.get("year_values") or [])
                if len(yv_mw) < n_y:
                    yv_mw.extend(["—"] * (n_y - len(yv_mw)))
                ynt = list(r.get("year_numeric_tooltips") or [])
                if len(ynt) < n_y:
                    ynt.extend([""] * (n_y - len(ynt)))
                for j in range(n_y):
                    y = years[j]
                    if not ((coeff_base_year + 1) <= y <= (coeff_base_year + 6)):
                        continue
                    k_parsed = _parse_summary_cell_float(k_list[j] if j < len(k_list) else None)
                    d = denoms[j] if j < len(denoms) else None
                    if k_parsed is None or d is None or not (d > 0):
                        continue
                    prod = k_parsed * d
                    yv_mw[j] = _format_numeric(prod, rounding_digits)
                    ynt[j] = _format_full_numeric_tooltip(prod)
                r["year_values"] = yv_mw
                r["year_numeric_tooltips"] = ynt
            elif coeff_base_year is not None and dm_block == "UnionEnergySystemDemandParameter" and pk in pk_medium_ues_sync:
                yv_mw = list(r.get("year_values") or [])
                if len(yv_mw) < n_y:
                    yv_mw.extend(["—"] * (n_y - len(yv_mw)))
                ynt = list(r.get("year_numeric_tooltips") or [])
                if len(ynt) < n_y:
                    ynt.extend([""] * (n_y - len(ynt)))
                for j in range(n_y):
                    y = years[j]
                    if not _coeff_union_res_sum_year(y, coeff_base_year):
                        continue
                    k_parsed = _parse_summary_cell_float(k_list[j] if j < len(k_list) else None)
                    d = denoms[j] if j < len(denoms) else None
                    if k_parsed is None or d is None or not (d > 0):
                        continue
                    prod = k_parsed * d
                    yv_mw[j] = _format_numeric(prod, rounding_digits)
                    ynt[j] = _format_full_numeric_tooltip(prod)
                r["year_values"] = yv_mw
                r["year_numeric_tooltips"] = ynt
        i += block_size


def _flatten_entities(
    entities: list[SummaryEntity],
    years: list[int],
    rounding_digits: int,
    *,
    avg_temp_uses_global_rounding: bool = False,
) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for entity in entities:
        flattened.extend(
            _flatten_entity(
                entity,
                years,
                rounding_digits,
                avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
            )
        )
    return flattened


def _slice_row_ids(demand_rows: list[Any]) -> dict[Any, int]:
    """Ключ среза «hist» или номер года → id строки параметров."""
    out: dict[Any, int] = {}
    for row in demand_rows:
        if getattr(row, "is_historical_maximum", False):
            sk: Any = "hist"
        else:
            sk = getattr(row, "year_number", None)
        if sk is not None:
            rid = getattr(row, "id", None)
            if rid is not None:
                out[sk] = int(rid)
    return out


def _indexed_demand_rows_by_slice(demand_rows: list[Any]) -> dict[Any, Any]:
    """hist → объект строки; календарный год → объект строки."""
    out: dict[Any, Any] = {}
    for row in demand_rows:
        if getattr(row, "is_historical_maximum", False):
            out["hist"] = row
        else:
            yn = getattr(row, "year_number", None)
            if yn is not None:
                out[int(yn)] = row
    return out


_COEFF_PARAM_TO_K_ATTR = {
    "combined_on_oes": "coeff_k_combined_on_oes",
    "combined_on_ees": "coeff_k_combined_on_ees",
    "calculated_max_power_mw": "coeff_k_calculated_max_power_mw",
    "calculated_combined_on_ees_mw": "coeff_k_calculated_combined_on_ees_mw",
}


def _year_coeff_k_stored_for_flat(
    *,
    parameter_key: str,
    demand_model_name: str | None,
    years: list[int],
    by_slice: dict[Any, Any],
    rounding_digits: int,
) -> list[str]:
    """Подписи сохранённого k для строки параметра сводки (совпадают с округлением столбца k)."""
    if demand_model_name not in (
        "RegionalEnergySystemDemandParameter",
        "UnionEnergySystemDemandParameter",
    ):
        return []
    attr = _COEFF_PARAM_TO_K_ATTR.get(parameter_key)
    if attr is None:
        return []
    if demand_model_name == "RegionalEnergySystemDemandParameter":
        if parameter_key not in ("combined_on_oes", "combined_on_ees"):
            return []
    elif demand_model_name == "UnionEnergySystemDemandParameter":
        if parameter_key not in (
            "calculated_max_power_mw",
            "combined_on_ees",
            "calculated_combined_on_ees_mw",
        ):
            return []
    out: list[str] = []
    for year in years:
        row = by_slice.get(year)
        if row is None:
            out.append("—")
            continue
        v = getattr(row, attr, None)
        if v is None:
            out.append("—")
        else:
            out.append(_format_numeric(v, rounding_digits))
    return out


def _flatten_entity(
    entity: SummaryEntity,
    years: list[int],
    rounding_digits: int,
    *,
    avg_temp_uses_global_rounding: bool = False,
) -> list[dict[str, Any]]:
    entity_rows: list[dict[str, Any]] = []
    parameter_maps, tooltip_maps = _build_parameter_maps(
        entity.demand_rows,
        entity.parameters,
        rounding_digits,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    slice_ids = _slice_row_ids(entity.demand_rows)
    dm_name = entity.demand_model_name
    demand_by_slice = _indexed_demand_rows_by_slice(entity.demand_rows)
    ues_id_flat = getattr(entity, "id_union_energy_system", None)
    if (
        ues_id_flat is None
        and getattr(entity, "parent_fk_column", None) == "id_union_energy_system"
        and getattr(entity, "parent_id", None) is not None
    ):
        ues_id_flat = entity.parent_id

    hist_note_row = next(
        (r for r in entity.demand_rows if getattr(r, "is_historical_maximum", False)),
        None,
    )
    entity_note_rid = getattr(hist_note_row, "id", None) if hist_note_row is not None else None
    raw_note = getattr(hist_note_row, "note", None) if hist_note_row is not None else None
    entity_note_text = "" if raw_note in (None, "") else str(raw_note)

    for index, (parameter_key, parameter_label) in enumerate(entity.parameters):
        values = parameter_maps.get(parameter_key, {})
        tt = tooltip_maps.get(parameter_key, {})
        year_row_ids = [slice_ids.get(year) for year in years]
        entity_rows.append(
            {
                "entity_label": entity.label,
                "entity_rowspan": len(entity.parameters),
                "entity_depth": entity.depth,
                "entity_kind": entity.entity_kind,
                "show_entity_cell": index == 0,
                "parameter_key": parameter_key,
                "parameter_label": parameter_label,
                "demand_model_name": dm_name,
                "parent_fk_column": entity.parent_fk_column,
                "parent_id": entity.parent_id,
                "hist_row_id": slice_ids.get("hist"),
                "year_row_ids": year_row_ids,
                "hist_value": values.get("hist", "—"),
                "year_values": [values.get(year, "—") for year in years],
                "hist_numeric_tooltip": tt.get("hist", ""),
                "year_numeric_tooltips": [tt.get(year, "") for year in years],
                "id_union_energy_system": ues_id_flat,
                "year_coeff_k_stored": _year_coeff_k_stored_for_flat(
                    parameter_key=parameter_key,
                    demand_model_name=dm_name,
                    years=years,
                    by_slice=demand_by_slice,
                    rounding_digits=rounding_digits,
                ),
                "entity_note_text": entity_note_text,
                "entity_note_row_id": entity_note_rid,
                "show_entity_note_cell": index == 0,
            }
        )

    for child in entity.children:
        entity_rows.extend(
            _flatten_entity(
                child,
                years,
                rounding_digits,
                avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
            )
        )
    return entity_rows


def _format_full_numeric_tooltip(value: Any) -> str:
    """Полное отображение числа для title (как format_decimal_trim(0) на странице demand_edit)."""
    if value in (None, ""):
        return ""
    s = format_decimal_trim_for_display(value, digits=0)
    return s if s else ""


def _build_parameter_maps(
    demand_rows: list[Any],
    parameters: tuple[tuple[str, str], ...],
    rounding_digits: int,
    *,
    avg_temp_uses_global_rounding: bool = False,
) -> tuple[dict[str, dict[Any, str]], dict[str, dict[Any, str]]]:
    result: dict[str, dict[Any, str]] = {param_key: {} for param_key, _ in parameters}
    param_keys = {pk for pk, _ in parameters}
    tooltip_keys = param_keys & _NUMERIC_ROUNDING_TOOLTIP_KEYS
    tooltips: dict[str, dict[Any, str]] = {pk: {} for pk in tooltip_keys}
    if avg_temp_uses_global_rounding and "avg_temp" in param_keys:
        tooltips["avg_temp"] = {}

    for row in demand_rows:
        slice_key = "hist" if getattr(row, "is_historical_maximum", False) else getattr(row, "year_number", None)
        if slice_key is None:
            continue

        if "max_power" in result:
            result["max_power"][slice_key] = _format_numeric(
                getattr(row, "max_power_consumption_mw", None),
                rounding_digits,
            )
        if "max_power" in tooltips:
            tooltips["max_power"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "max_power_consumption_mw", None)
            )
        if "peak_datetime" in result:
            result["peak_datetime"][slice_key] = _dash(
                dps.format_peak_datetime_for_slice(
                    getattr(row, "peak_datetime_msk", None),
                    slice_key == "hist",
                )
            )
        if "avg_temp" in result:
            result["avg_temp"][slice_key] = _format_numeric(
                getattr(row, "avg_daily_air_temp_c", None),
                rounding_digits if avg_temp_uses_global_rounding else 0,
            )
        if "avg_temp" in tooltips:
            tooltips["avg_temp"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "avg_daily_air_temp_c", None)
            )
        if "combined_on_oes" in result:
            result["combined_on_oes"][slice_key] = _format_numeric(
                getattr(row, "combined_on_oes", None),
                rounding_digits,
            )
        if "combined_on_oes" in tooltips:
            tooltips["combined_on_oes"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_oes", None)
            )
        if "combined_on_ees" in result:
            result["combined_on_ees"][slice_key] = _format_numeric(
                getattr(row, "combined_on_ees", None),
                rounding_digits,
            )
        if "combined_on_ees" in tooltips:
            tooltips["combined_on_ees"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_ees", None)
            )
        if "calculated_max_power_mw" in result:
            result["calculated_max_power_mw"][slice_key] = _format_numeric(
                getattr(row, "calculated_max_power_mw", None),
                rounding_digits,
            )
        if "calculated_max_power_mw" in tooltips:
            tooltips["calculated_max_power_mw"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "calculated_max_power_mw", None)
            )
        if "calculated_combined_on_ees_mw" in result:
            result["calculated_combined_on_ees_mw"][slice_key] = _format_numeric(
                getattr(row, "calculated_combined_on_ees_mw", None),
                rounding_digits,
            )
        if "calculated_combined_on_ees_mw" in tooltips:
            tooltips["calculated_combined_on_ees_mw"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "calculated_combined_on_ees_mw", None)
            )
        if "combined_on_es" in result:
            result["combined_on_es"][slice_key] = _format_numeric(
                getattr(row, "combined_on_es", None),
                rounding_digits,
            )
        if "combined_on_es" in tooltips:
            tooltips["combined_on_es"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_es", None)
            )
        if "combined_on_ez" in result:
            result["combined_on_ez"][slice_key] = _format_numeric(
                getattr(row, "combined_on_ez", None),
                rounding_digits,
            )
        if "combined_on_ez" in tooltips:
            tooltips["combined_on_ez"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_ez", None)
            )
        if "combined_on_fo" in result:
            result["combined_on_fo"][slice_key] = _format_numeric(
                getattr(row, "combined_on_fo", None),
                rounding_digits,
            )
        if "combined_on_fo" in tooltips:
            tooltips["combined_on_fo"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_fo", None)
            )
        if "combined_on_cz" in result:
            result["combined_on_cz"][slice_key] = _format_numeric(
                getattr(row, "combined_on_cz", None),
                rounding_digits,
            )
        if "combined_on_cz" in tooltips:
            tooltips["combined_on_cz"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_cz", None)
            )

    return result, tooltips


def _format_numeric(value: Any, digits: int) -> str:
    return _dash(format_decimal_trim_for_display(value, digits=digits))


def _dash(value: Any) -> str:
    if value in (None, ""):
        return "—"
    return str(value)


def _standalone_entity(
    label: str,
    demand_model: Any,
    parameters: tuple[tuple[str, str], ...],
    *,
    entity_kind: str = "default",
) -> SummaryEntity:
    return SummaryEntity(
        label=label,
        depth=0,
        parameters=parameters,
        demand_rows=dps.get_demand_rows(demand_model, None, None),
        entity_kind=entity_kind,
        demand_model_name=demand_model.__name__,
        parent_fk_column=None,
        parent_id=None,
    )


def _build_ues_entities_filtered(
    ues_predicate: Callable[[UnionEnergySystem], bool],
    *,
    always_show_subject_row_under_res: bool = False,
) -> list[SummaryEntity]:
    query = UnionEnergySystem.query.options(
        selectinload(UnionEnergySystem.regional_energy_systems).selectinload(
            RegionalEnergySystem.regional_districts
        ).selectinload(
            RegionalDistrict.energy_units
        ),
        selectinload(UnionEnergySystem.regional_energy_systems).selectinload(
            RegionalEnergySystem.energy_units
        ),
        selectinload(UnionEnergySystem.energy_system_type),
    )
    query = dps.filter_parents_by_version(query, UnionEnergySystem)
    query = query.order_by(
        UnionEnergySystem.display_order.asc().nullslast(),
        UnionEnergySystem.name.asc(),
        UnionEnergySystem.id.asc(),
    )

    entities: list[SummaryEntity] = []
    for ues in query.all():
        if not _is_valid_named_item(ues):
            continue
        if not ues_predicate(ues):
            continue

        child_entities = [
            _build_regional_energy_system_entity(
                res,
                ues_id=ues.id,
                always_show_subject_row_under_res=always_show_subject_row_under_res,
            )
            for res in sorted(ues.regional_energy_systems, key=_sort_by_name)
            if _is_valid_named_item(res)
        ]
        entities.append(
            SummaryEntity(
                label=ues.name,
                depth=1,
                parameters=PARAMETERS_UES_OES,
                demand_rows=dps.get_demand_rows(
                    UnionEnergySystemDemandParameter,
                    "id_union_energy_system",
                    ues.id,
                ),
                entity_kind="group",
                children=child_entities,
                demand_model_name=UnionEnergySystemDemandParameter.__name__,
                parent_fk_column="id_union_energy_system",
                parent_id=ues.id,
                id_union_energy_system=ues.id,
            )
        )
    return entities


def _build_regional_energy_system_entity(
    res,
    *,
    ues_id: int,
    always_show_subject_row_under_res: bool = False,
) -> SummaryEntity:
    regional_districts = [
        regional_district
        for regional_district in sorted(res.regional_districts, key=_sort_by_name)
        if _is_valid_named_item(regional_district)
    ]
    # Один субъект в РЭС: строки субъекта в дереве не дублируем (сразу ЭУ), но id субъекта нужен
    # для фильтров сводки ds_rd и для согласованного матчинга листьев при ds_res+ds_rd.
    single_rd_id: int | None = regional_districts[0].id if len(regional_districts) == 1 else None

    subject_children: list[SummaryEntity]
    if len(regional_districts) > 1:
        # «Совмещенный на ЭС» — пока в РЭС несколько субъектов (эта ветка — уже ≥2 после фильтра имени).
        # Сводка по ОЭС: для субъектов РФ не показываем «на ФО» и «на централизованную зону»
        subject_children = [
            _build_regional_district_entity(
                regional_district,
                depth=3,
                energy_units=_filter_energy_units_for_res(
                    regional_district.energy_units,
                    res.id,
                ),
                parameters=PARAMETERS_WITH_OES_EES_AND_ES,
                ues_id=ues_id,
                res_id=res.id,
            )
            for regional_district in regional_districts
        ]
    elif (
        len(regional_districts) == 1
        and always_show_subject_row_under_res
    ):
        rd0 = regional_districts[0]
        subject_children = [
            _build_regional_district_entity(
                rd0,
                depth=3,
                energy_units=_filter_energy_units_for_res(
                    rd0.energy_units,
                    res.id,
                ),
                parameters=PARAMETERS_WITH_OES_EES_AND_ES,
                ues_id=ues_id,
                res_id=res.id,
            )
        ]
    else:
        subject_children = _build_energy_unit_entities(
            _filter_valid_items(res.energy_units),
            depth=3,
            id_union_energy_system=ues_id,
            id_regional_energy_system=res.id,
            id_regional_district=single_rd_id,
        )

    return SummaryEntity(
        label=res.name,
        depth=2,
        parameters=PARAMETERS_WITH_OES_AND_EES,
        demand_rows=dps.get_demand_rows(
            RegionalEnergySystemDemandParameter,
            "id_regional_energy_system",
            res.id,
        ),
        entity_kind="child",
        children=subject_children,
        demand_model_name=RegionalEnergySystemDemandParameter.__name__,
        parent_fk_column="id_regional_energy_system",
        parent_id=res.id,
        id_union_energy_system=ues_id,
        id_regional_energy_system=res.id,
        id_regional_district=single_rd_id,
    )


def _build_regional_energy_system_entity_for_energy_zone(
    res: RegionalEnergySystem,
    regional_districts_in_zone: list[RegionalDistrict],
    *,
    energy_zone_id: int,
) -> SummaryEntity:
    """РЭС внутри энергозоны: при одном субъекте в зоне — ЭС под субъектом; при нескольких — только ЭС без строк субъектов."""
    regional_districts = sorted(
        [rd for rd in regional_districts_in_zone if _is_valid_named_item(rd)],
        key=_sort_by_name,
    )
    subject_children: list[SummaryEntity]
    if len(regional_districts) > 1:
        # Сводка по энергозонам: при нескольких субъектах в РЭС не показываем строки по субъектам —
        # только энергоузлы РЭС в зоне (как при одном субъекте), без промежуточного уровня «субъект».
        combined_eus: list[EnergyUnit] = []
        seen_eu_ids: set[int] = set()
        for regional_district in regional_districts:
            for eu in _filter_energy_units_for_res(
                regional_district.energy_units,
                res.id,
            ):
                euid = getattr(eu, "id", None)
                if euid is None or euid in seen_eu_ids:
                    continue
                seen_eu_ids.add(euid)
                combined_eus.append(eu)
        subject_children = _build_energy_unit_entities(
            combined_eus,
            depth=2,
            id_energy_zone=energy_zone_id,
            id_regional_energy_system=res.id,
        )
    elif len(regional_districts) == 1:
        subject_children = _build_energy_unit_entities(
            _filter_energy_units_for_res(regional_districts[0].energy_units, res.id),
            depth=2,
            id_energy_zone=energy_zone_id,
            id_regional_energy_system=res.id,
            id_regional_district=regional_districts[0].id,
        )
    else:
        subject_children = []

    return SummaryEntity(
        label=res.name,
        depth=1,
        parameters=PARAMETERS_RES,
        demand_rows=dps.get_demand_rows(
            RegionalEnergySystemDemandParameter,
            "id_regional_energy_system",
            res.id,
        ),
        entity_kind="child",
        children=subject_children,
        demand_model_name=RegionalEnergySystemDemandParameter.__name__,
        parent_fk_column="id_regional_energy_system",
        parent_id=res.id,
        id_energy_zone=energy_zone_id,
        id_regional_energy_system=res.id,
    )


def _build_energy_zone_entities() -> list[SummaryEntity]:
    ez_query = EnergyZone.query.options(selectinload(EnergyZone.regional_districts))
    ez_query = dps.filter_parents_by_version(ez_query, EnergyZone)
    zones = sorted(
        [z for z in ez_query.all() if _is_valid_named_item(z)],
        key=_energy_zone_number_sort_key,
    )

    res_query = RegionalEnergySystem.query.options(
        selectinload(RegionalEnergySystem.regional_districts).selectinload(
            RegionalDistrict.energy_units
        ),
        selectinload(RegionalEnergySystem.energy_units),
    )
    res_query = dps.filter_parents_by_version(res_query, RegionalEnergySystem)
    all_res = [r for r in res_query.all() if _is_valid_named_item(r)]

    entities: list[SummaryEntity] = []
    for ez in zones:
        zone_rd_ids = {rd.id for rd in ez.regional_districts}
        res_children: list[SummaryEntity] = []
        for res in sorted(all_res, key=_sort_by_name):
            rds_in_zone = [rd for rd in res.regional_districts if rd.id in zone_rd_ids]
            if not rds_in_zone:
                continue
            res_children.append(
                _build_regional_energy_system_entity_for_energy_zone(
                    res, rds_in_zone, energy_zone_id=ez.id
                )
            )
        entities.append(
            SummaryEntity(
                label=f"{ez.number} — {ez.name}",
                depth=0,
                parameters=PARAMETERS_ENERGY_ZONE,
                demand_rows=dps.get_demand_rows(
                    EnergyZoneDemandParameter,
                    "id_energy_zone",
                    ez.id,
                ),
                entity_kind="group",
                children=res_children,
                demand_model_name=EnergyZoneDemandParameter.__name__,
                parent_fk_column="id_energy_zone",
                parent_id=ez.id,
                id_energy_zone=ez.id,
            )
        )
    return entities


def _build_synchronous_area_entities(*, depth: int = 0) -> list[SummaryEntity]:
    """Строки сводки по ОЭС: одна сущность на каждую синхронную зону (как энергозона по показателям).

    В сводке по ОЭС вложены под «ЕЭС России (без НТ)» — depth=1, чтобы шли после агрегата и перед ОЭС.
    """
    query = SynchronousArea.query
    query = dps.filter_parents_by_version(query, SynchronousArea)
    query = query.order_by(
        SynchronousArea.display_order.asc().nullslast(),
        SynchronousArea.name.asc(),
        SynchronousArea.id.asc(),
    )
    entities: list[SummaryEntity] = []
    for sa in query.all():
        if not _is_valid_named_item(sa):
            continue
        entities.append(
            SummaryEntity(
                label=_synchronous_area_display_label(sa),
                depth=depth,
                parameters=PARAMETERS_ENERGY_ZONE,
                demand_rows=dps.get_demand_rows(
                    SynchronousAreaDemandParameter,
                    "id_synchronous_area",
                    sa.id,
                ),
                entity_kind="synchronous_area",
                demand_model_name=SynchronousAreaDemandParameter.__name__,
                parent_fk_column="id_synchronous_area",
                parent_id=sa.id,
                id_synchronous_area=sa.id,
            )
        )
    return entities


def _build_tites_entity() -> SummaryEntity | None:
    energy_system_type = _get_energy_system_type_by_name("ТИТЭС")
    children = _build_ues_entities_filtered(_is_tites_branch)
    if energy_system_type is None and not children:
        return None

    if energy_system_type is None:
        return SummaryEntity(
            label="ТИТЭС",
            depth=0,
            parameters=BASE_PARAMETERS,
            demand_rows=[],
            entity_kind="group-root",
            children=children,
            demand_model_name=None,
            parent_fk_column=None,
            parent_id=None,
        )

    return SummaryEntity(
        label=getattr(energy_system_type, "name", None) or "ТИТЭС",
        depth=0,
        parameters=BASE_PARAMETERS,
        demand_rows=dps.get_demand_rows(
            EnergySystemTypeDemandParameter,
            "id_energy_system_type",
            energy_system_type.id,
        ),
        entity_kind="group-root",
        children=children,
        demand_model_name=EnergySystemTypeDemandParameter.__name__,
        parent_fk_column="id_energy_system_type",
        parent_id=energy_system_type.id,
    )


def _build_regional_district_entity(
    regional_district: RegionalDistrict,
    *,
    depth: int,
    energy_units: list[EnergyUnit] | None = None,
    parameters: tuple[tuple[str, str], ...] = PARAMETERS_WITH_OES_EES_AND_ES,
    ues_id: int | None = None,
    res_id: int | None = None,
) -> SummaryEntity:
    return SummaryEntity(
        label=regional_district.name,
        depth=depth,
        parameters=parameters,
        demand_rows=dps.get_demand_rows(
            RegionalDistrictDemandParameter,
            "id_regional_district",
            regional_district.id,
        ),
        entity_kind="child",
        children=_build_energy_unit_entities(
            energy_units if energy_units is not None else _filter_valid_items(regional_district.energy_units),
            depth=depth + 1,
            id_union_energy_system=ues_id,
            id_regional_energy_system=res_id,
            id_regional_district=regional_district.id,
        ),
        demand_model_name=RegionalDistrictDemandParameter.__name__,
        parent_fk_column="id_regional_district",
        parent_id=regional_district.id,
        id_union_energy_system=ues_id,
        id_regional_energy_system=res_id,
        id_regional_district=regional_district.id,
    )


def _build_energy_unit_entities(
    energy_units: list[EnergyUnit],
    *,
    depth: int,
    id_union_energy_system: int | None = None,
    id_regional_energy_system: int | None = None,
    id_regional_district: int | None = None,
    id_energy_zone: int | None = None,
) -> list[SummaryEntity]:
    out: list[SummaryEntity] = []
    for energy_unit in _filter_valid_items(energy_units):
        ues = id_union_energy_system
        if ues is None:
            res_obj = getattr(energy_unit, "regional_energy_system", None)
            ues_obj = getattr(res_obj, "union_energy_system", None) if res_obj else None
            ues = getattr(ues_obj, "id", None)
        res_id = id_regional_energy_system or getattr(
            energy_unit, "id_regional_energy_system", None
        )
        rd_id = id_regional_district or getattr(energy_unit, "id_regional_district", None)
        out.append(
            SummaryEntity(
                label=energy_unit.name,
                depth=depth,
                parameters=PARAMETERS_WITH_OES_AND_EES,
                demand_rows=dps.get_demand_rows(
                    EnergyUnitDemandParameter,
                    "id_energy_unit",
                    energy_unit.id,
                ),
                entity_kind="child",
                demand_model_name=EnergyUnitDemandParameter.__name__,
                parent_fk_column="id_energy_unit",
                parent_id=energy_unit.id,
                id_union_energy_system=ues,
                id_regional_energy_system=res_id,
                id_regional_district=rd_id,
                id_energy_unit=energy_unit.id,
                id_energy_zone=id_energy_zone,
            )
        )
    return out


def _build_federal_district_entities() -> list[SummaryEntity]:
    query = FederalDistrict.query.options(selectinload(FederalDistrict.regional_districts))
    query = dps.filter_parents_by_version(query, FederalDistrict)
    query = query.order_by(
        FederalDistrict.display_order.asc().nullslast(),
        FederalDistrict.name.asc(),
        FederalDistrict.id.asc(),
    )

    entities: list[SummaryEntity] = []
    for federal_district in query.all():
        if not _is_valid_named_item(federal_district):
            continue
        if _federal_district_excluded_from_summary(federal_district):
            continue

        child_entities = [
            SummaryEntity(
                label=regional_district.name,
                depth=1,
                parameters=PARAMETERS_SUBJECT_FD_SUMMARY,
                demand_rows=dps.get_demand_rows(
                    RegionalDistrictDemandParameter,
                    "id_regional_district",
                    regional_district.id,
                ),
                entity_kind="child",
                demand_model_name=RegionalDistrictDemandParameter.__name__,
                parent_fk_column="id_regional_district",
                parent_id=regional_district.id,
                id_federal_district=federal_district.id,
                id_regional_district=regional_district.id,
            )
            for regional_district in sorted(federal_district.regional_districts, key=_sort_by_name)
            if _is_valid_named_item(regional_district)
        ]
        entities.append(
            SummaryEntity(
                label=federal_district.name,
                depth=0,
                parameters=PARAMETERS_FEDERAL_DISTRICT,
                demand_rows=dps.get_demand_rows(
                    FederalDistrictDemandParameter,
                    "id_federal_district",
                    federal_district.id,
                ),
                entity_kind="group",
                children=child_entities,
                demand_model_name=FederalDistrictDemandParameter.__name__,
                parent_fk_column="id_federal_district",
                parent_id=federal_district.id,
                id_federal_district=federal_district.id,
            )
        )
    return entities


def _is_ees_branch(ues: UnionEnergySystem) -> bool:
    type_name = ((getattr(ues.energy_system_type, "name", None) or "").strip()).upper()
    return "ЕЭС" in type_name and "ТИТЭС" not in type_name


def _is_tites_branch(ues: UnionEnergySystem) -> bool:
    type_name = ((getattr(ues.energy_system_type, "name", None) or "").strip()).upper()
    return "ТИТЭС" in type_name


def _filter_energy_units_for_res(
    energy_units: list[EnergyUnit],
    regional_energy_system_id: int,
) -> list[EnergyUnit]:
    return _filter_valid_items(
        [
            energy_unit
            for energy_unit in energy_units
            if getattr(energy_unit, "id_regional_energy_system", None) == regional_energy_system_id
        ]
    )


def _get_energy_system_type_by_name(name: str) -> EnergySystemType | None:
    query = EnergySystemType.query
    query = dps.filter_parents_by_version(query, EnergySystemType)
    return query.filter(EnergySystemType.name == name).first()


def _is_valid_named_item(item: Any) -> bool:
    name = (getattr(item, "name", None) or "").strip()
    return bool(name) and name.casefold() not in PLACEHOLDER_NAMES


def _filter_valid_items(items: list[Any]) -> list[Any]:
    return [item for item in sorted(items, key=_sort_by_name) if _is_valid_named_item(item)]


def _energy_zone_number_sort_key(ez: EnergyZone) -> tuple[int, Any, int]:
    """Номер энергозоны как целое: 1, 2, …, 10, а не лексикографически 1, 10, 2."""
    raw = (getattr(ez, "number", None) or "").strip()
    eid = getattr(ez, "id", 0)
    if not raw:
        return (2, 0, eid)
    try:
        return (0, int(raw), eid)
    except ValueError:
        return (1, raw.casefold(), eid)


def _sort_by_name(item: Any) -> tuple[str, int]:
    return ((getattr(item, "name", None) or "").casefold(), getattr(item, "id", 0))


def _oes_territory_filters_active(
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    f_eu: frozenset[int],
) -> bool:
    """Хотя бы один территориальный фильтр сводки по ОЭС задан в URL."""
    return bool(f_ues or f_res or f_rd or f_eu)


def prune_summary_entities_oes(
    entities: list[SummaryEntity],
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    f_eu: frozenset[int],
    f_sa: frozenset[int],
) -> list[SummaryEntity]:
    """См. :func:`build_oes_summary_context` и ослабление фильтров в :func:`_prune_one_oes`."""
    out: list[SummaryEntity] = []
    for e in entities:
        pe = _prune_one_oes(e, f_ues, f_res, f_rd, f_eu, f_sa)
        if pe is not None:
            out.append(pe)
    return out


def _oes_leaf_matches_filters(
    e: SummaryEntity,
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    f_eu: frozenset[int],
) -> bool:
    if f_ues:
        if e.id_union_energy_system is None or e.id_union_energy_system not in f_ues:
            return False
    if f_res:
        if e.id_regional_energy_system is None or e.id_regional_energy_system not in f_res:
            return False
    if f_rd:
        if e.id_regional_district is None or e.id_regional_district not in f_rd:
            return False
    if f_eu:
        if e.id_energy_unit is None or e.id_energy_unit not in f_eu:
            return False
    return True


def _oes_is_union_energy_system_group(e: SummaryEntity) -> bool:
    return (
        e.entity_kind == "group"
        and e.demand_model_name == UnionEnergySystemDemandParameter.__name__
        and e.id_union_energy_system is not None
    )


def _oes_is_regional_energy_system_node(e: SummaryEntity) -> bool:
    return (
        e.demand_model_name == RegionalEnergySystemDemandParameter.__name__
        and e.id_regional_energy_system is not None
    )


def _oes_is_regional_district_node(e: SummaryEntity) -> bool:
    return (
        e.demand_model_name == RegionalDistrictDemandParameter.__name__
        and e.id_regional_district is not None
    )


def _oes_res_scope_for_ues_subtree(
    f_ues: frozenset[int],
    f_res: frozenset[int],
    ues_children: list[SummaryEntity],
) -> frozenset[int]:
    """Сужение ds_res на уровне узла ОЭС (аналог :func:`_ez_res_scope_for_energy_zone_subtree`)."""
    if not f_res:
        return frozenset()
    if not f_ues:
        return f_res
    child_res_ids = {
        c.id_regional_energy_system for c in ues_children if c.id_regional_energy_system is not None
    }
    if not child_res_ids:
        return f_res
    inter = f_res & child_res_ids
    return inter if inter else frozenset()


def _oes_rd_scope_for_res_subtree(
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    res_children: list[SummaryEntity],
) -> frozenset[int]:
    """Сужение ds_rd на уровне узла РЭС (прямые потомки — субъекты РФ или энергорайоны)."""
    if not f_rd:
        return frozenset()
    if not f_ues and not f_res:
        return f_rd
    child_rd_ids: set[int] = set()
    for c in res_children:
        if c.id_regional_district is not None:
            child_rd_ids.add(int(c.id_regional_district))
    if not child_rd_ids:
        return f_rd
    inter = f_rd & child_rd_ids
    return inter if inter else frozenset()


def _oes_eu_scope_for_rd_subtree(
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    f_eu: frozenset[int],
    rd_children: list[SummaryEntity],
) -> frozenset[int]:
    """Сужение ds_eu (энергорайон) на уровне узла субъекта РФ."""
    if not f_eu:
        return frozenset()
    if not f_ues and not f_res and not f_rd:
        return f_eu
    child_eu_ids = {c.id_energy_unit for c in rd_children if c.id_energy_unit is not None}
    if not child_eu_ids:
        return f_eu
    inter = f_eu & child_eu_ids
    return inter if inter else frozenset()


def _prune_one_oes(
    e: SummaryEntity,
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    f_eu: frozenset[int],
    f_sa: frozenset[int],
) -> SummaryEntity | None:
    filters_on = _oes_territory_filters_active(f_ues, f_res, f_rd, f_eu)
    if e.entity_kind == "synchronous_area":
        # Синхронные зоны только без территориального фильтра; при выборе ОЭС/РЭС/субъекта/ЭУ — скрываем
        if filters_on:
            return None
        if f_sa and (e.id_synchronous_area is None or e.id_synchronous_area not in f_sa):
            return None
        return e
    # Верхние агрегаты по стране/ЕЭС без привязки к ОЭС/РЭС — при фильтрах не показываем
    if e.entity_kind == "oes_top_aggregate":
        return None if filters_on else e
    # «ЕЭС России (без НТ)», «ТИТЭС»: агрегат по стране + дочерняя территориальная ветка
    if e.entity_kind == "group-root":
        new_ch: list[SummaryEntity] = []
        for c in e.children:
            pc = _prune_one_oes(c, f_ues, f_res, f_rd, f_eu, f_sa)
            if pc is not None:
                new_ch.append(pc)
        if filters_on and not new_ch:
            return None
        return replace(e, children=new_ch)
    res_c, rd_c, eu_c = f_res, f_rd, f_eu
    if f_ues and _oes_is_union_energy_system_group(e) and e.children:
        res_c = _oes_res_scope_for_ues_subtree(f_ues, f_res, e.children)
    elif (f_ues or f_res) and _oes_is_regional_energy_system_node(e) and e.children:
        rd_c = _oes_rd_scope_for_res_subtree(f_ues, f_res, f_rd, e.children)
    elif (f_ues or f_res or f_rd) and _oes_is_regional_district_node(e) and e.children:
        eu_c = _oes_eu_scope_for_rd_subtree(f_ues, f_res, f_rd, f_eu, e.children)
    new_ch: list[SummaryEntity] = []
    for c in e.children:
        pc = _prune_one_oes(c, f_ues, res_c, rd_c, eu_c, f_sa)
        if pc is not None:
            new_ch.append(pc)
    e2 = replace(e, children=new_ch)
    if new_ch:
        return e2
    if _oes_leaf_matches_filters(e2, f_ues, f_res, f_rd, f_eu):
        return replace(e2, children=[])
    return None


def _fo_subjects_only_flat_mode(f_fd: frozenset[int], f_rd: frozenset[int]) -> bool:
    """Только ``ds_rd`` без ``ds_fd``: строки субъектов без родительской строки ФО."""
    return bool(f_rd) and not bool(f_fd)


def prune_summary_entities_fo(
    entities: list[SummaryEntity],
    f_fd: frozenset[int],
    f_rd: frozenset[int],
) -> list[SummaryEntity]:
    """См. :func:`build_federal_district_summary_context`.

    Режим «плоско по субъектам» включается только в :func:`_fo_subjects_only_flat_mode`;
    при непустом ``f_fd`` строки ФО сохраняются; ``f_rd`` сужает субъектов **внутри каждого ФО**
    через :func:`_fo_rd_scope_for_fd_subtree` (пустой ``f_rd`` = все субъекты выбранных ФО).
    """
    promote_subjects_without_fd_row = _fo_subjects_only_flat_mode(f_fd, f_rd)
    out: list[SummaryEntity] = []
    for e in entities:
        pe = _prune_one_fo(e, f_fd, f_rd)
        if pe is None:
            continue
        if (
            promote_subjects_without_fd_row
            and pe.entity_kind == "group"
            and pe.id_federal_district is not None
            and pe.children
        ):
            for c in pe.children:
                d = int(c.depth) if c.depth is not None else 0
                out.append(replace(c, depth=max(0, d - 1)))
            continue
        out.append(pe)
    return out


def _fo_leaf_matches(e: SummaryEntity, f_fd: frozenset[int], f_rd: frozenset[int]) -> bool:
    """Совпадение листа/узла с фильтром.

    Пустой ``f_rd`` не ограничивает субъекты: при заданном ``f_fd`` остаются все субъекты
    выбранных ФО. Непустой ``f_rd`` сужает до перечисленных субъектов; при этом ``f_fd``,
    если задан, дополнительно ограничивает по округу (субъект должен принадлежать одному из ФО).
    """
    if not f_fd and not f_rd:
        return True
    if f_fd:
        if e.id_federal_district is None or e.id_federal_district not in f_fd:
            return False
    if f_rd:
        if e.id_regional_district is None or e.id_regional_district not in f_rd:
            return False
    return True


def _fo_rd_scope_for_fd_subtree(
    f_fd: frozenset[int],
    f_rd: frozenset[int],
    fd_children: list[SummaryEntity],
) -> frozenset[int]:
    """Ограничение по субъектам для прямых потомков одного узла ФО.

    При выбранных в URL ``ds_fd`` и ``ds_rd``: если среди отмеченных субъектов есть хотя бы один
    из этого ФО — показываем только пересечение; иначе (все отмеченные из других ФО) —
    для этого ФО поддерева фильтр по субъектам снимаем — все субъекты округа.

    Режим только ``ds_rd`` (пустой ``f_fd``): без ослабления — глобальный список субъектов.
    """
    if not f_rd:
        return frozenset()
    if not f_fd:
        return f_rd
    child_rd_ids = {c.id_regional_district for c in fd_children if c.id_regional_district is not None}
    if not child_rd_ids:
        return f_rd
    inter = f_rd & child_rd_ids
    return inter if inter else frozenset()


def _prune_one_fo(e: SummaryEntity, f_fd: frozenset[int], f_rd: frozenset[int]) -> SummaryEntity | None:
    filters_on = bool(f_fd or f_rd)
    if e.entity_kind == "centralized_zone":
        return None if filters_on else e
    rd_for_children = f_rd
    if f_fd and e.entity_kind == "group" and e.id_federal_district is not None and e.children:
        rd_for_children = _fo_rd_scope_for_fd_subtree(f_fd, f_rd, e.children)
    new_ch: list[SummaryEntity] = []
    for c in e.children:
        pc = _prune_one_fo(c, f_fd, rd_for_children)
        if pc is not None:
            new_ch.append(pc)
    e2 = replace(e, children=new_ch)
    if new_ch:
        return e2
    if _fo_leaf_matches(e2, f_fd, f_rd):
        return replace(e2, children=[])
    return None


def prune_summary_entities_ez(
    entities: list[SummaryEntity],
    f_ez: frozenset[int],
    f_res: frozenset[int],
) -> list[SummaryEntity]:
    """См. :func:`build_energy_zones_summary_context` и :func:`_ez_res_scope_for_energy_zone_subtree`."""
    out: list[SummaryEntity] = []
    for e in entities:
        pe = _prune_one_ez(e, f_ez, f_res)
        if pe is not None:
            out.append(pe)
    return out


def _ez_res_only_flat_mode(f_ez: frozenset[int], f_res: frozenset[int]) -> bool:
    """Только ``ds_res`` без ``ds_ez``: строки РЭС без родительской строки энергозоны."""
    return bool(f_res) and not bool(f_ez)


def _ez_res_scope_for_energy_zone_subtree(
    f_ez: frozenset[int],
    f_res: frozenset[int],
    ez_children: list[SummaryEntity],
) -> frozenset[int]:
    """Ограничение по РЭС для прямых потомков одной энергозоны (аналог :func:`_fo_rd_scope_for_fd_subtree`)."""
    if not f_res:
        return frozenset()
    if not f_ez:
        return f_res
    child_res_ids = {
        c.id_regional_energy_system for c in ez_children if c.id_regional_energy_system is not None
    }
    if not child_res_ids:
        return f_res
    inter = f_res & child_res_ids
    return inter if inter else frozenset()


def _flatten_energy_zone_parents_when_res_filtered(
    entities: list[SummaryEntity],
) -> list[SummaryEntity]:
    """
    При фильтре по РЭС (ds_res) не показывать строку-агрегат энергозоны — только РЭС и ниже,
    аналогично сводке по ФО при фильтре по субъектам.
    """
    out: list[SummaryEntity] = []
    for e in entities:
        if e.entity_kind == "group" and e.id_energy_zone is not None and e.children:
            for c in e.children:
                d = int(c.depth) if c.depth is not None else 0
                out.append(replace(c, depth=max(0, d - 1)))
            continue
        out.append(e)
    return out


def _ez_leaf_matches(e: SummaryEntity, f_ez: frozenset[int], f_res: frozenset[int]) -> bool:
    if e.entity_kind == "centralized_zone":
        return True
    if not f_ez and not f_res:
        return True
    if f_ez:
        if e.id_energy_zone is None or e.id_energy_zone not in f_ez:
            return False
    if f_res:
        if e.id_regional_energy_system is None or e.id_regional_energy_system not in f_res:
            return False
    return True


def _prune_one_ez(e: SummaryEntity, f_ez: frozenset[int], f_res: frozenset[int]) -> SummaryEntity | None:
    filters_on = bool(f_ez or f_res)
    if e.entity_kind == "centralized_zone":
        return None if filters_on else e
    res_for_children = f_res
    if f_ez and e.entity_kind == "group" and e.id_energy_zone is not None and e.children:
        res_for_children = _ez_res_scope_for_energy_zone_subtree(f_ez, f_res, e.children)
    new_ch: list[SummaryEntity] = []
    for c in e.children:
        pc = _prune_one_ez(c, f_ez, res_for_children)
        if pc is not None:
            new_ch.append(pc)
    e2 = replace(e, children=new_ch)
    if new_ch:
        return e2
    if _ez_leaf_matches(e2, f_ez, f_res):
        return replace(e2, children=[])
    return None


def get_demand_summary_filter_refdata() -> dict[str, Any]:
    """Справочники для multiselect-фильтров сводки (как на station_list)."""
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_list_full,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_system_list_full,
    )
    from app.common.services.get_services.territories.regional_district_get_services import (
        get_regional_district_list_full,
    )
    from app.common.services.get_services.energy_systems.energy_unit_get_services import (
        get_energy_unit_list_full,
    )
    from app.common.services.get_services.territories.federal_district_get_services import (
        get_federal_district_list_full,
    )
    from app.common.services.get_services.energy_systems.energy_zone_get_services import (
        get_energy_zone_list_full,
    )

    ues_objs = get_union_energy_system_list_full()
    union_energy_system_list = [{"id": x.id, "name": x.name} for x in ues_objs]

    res_objs = get_regional_energy_system_list_full()
    regional_energy_system_list = [{"id": x.id, "name": x.name} for x in res_objs]

    rd_tuples = get_regional_district_list_full()
    regional_district_list = [{"id": rid, "name": rname} for rid, rname in rd_tuples]

    eu_objs = get_energy_unit_list_full()
    energy_unit_list = [{"id": x.id, "name": x.name} for x in eu_objs]

    fd_objs = get_federal_district_list_full()
    federal_district_list = [{"id": x.id, "name": x.name} for x in fd_objs]

    ez_objs = get_energy_zone_list_full()
    ez_objs_sorted = sorted(ez_objs, key=_energy_zone_number_sort_key)
    energy_zone_list = [{"id": x.id, "name": f"{x.number} — {x.name}"} for x in ez_objs_sorted]

    return {
        "union_energy_system_list": union_energy_system_list,
        "regional_energy_system_list": regional_energy_system_list,
        "regional_district_list": regional_district_list,
        "energy_unit_list": energy_unit_list,
        "federal_district_list": federal_district_list,
        "energy_zone_list": energy_zone_list,
    }


def get_energy_consumption_oes_filter_cascade_data() -> dict[str, Any]:
    """
    Списки и маппинги для каскадных фильтров сводки по ОЭС (как station_list / filters-data).
    Дополнительно — связи энергорайонов (EnergyUnit) с ОЭС/РЭС/субъектом.
    """
    from collections import defaultdict

    from app.common.services.get_services.energy_systems.energy_unit_get_services import (
        get_energy_unit_list_full,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_res_to_ues_id_map,
    )
    from app.generation.services.station_services.filters_services import (
        get_territorial_filter_reference_data,
    )

    t = get_territorial_filter_reference_data()
    res_to_ues_one = get_res_to_ues_id_map()

    ues_to_eu: dict[int, list[int]] = defaultdict(list)
    res_to_eu: dict[int, list[int]] = defaultdict(list)
    rd_to_eu: dict[int, list[int]] = defaultdict(list)
    eu_to_res: dict[int, int] = {}
    eu_to_rd: dict[int, int] = {}
    eu_to_ues: dict[int, int] = {}

    eu_objs = get_energy_unit_list_full()
    for eu in eu_objs:
        eid = int(eu.id)
        res_id = int(eu.id_regional_energy_system)
        rd_id = int(eu.id_regional_district)
        res_to_eu[res_id].append(eid)
        rd_to_eu[rd_id].append(eid)
        eu_to_res[eid] = res_id
        eu_to_rd[eid] = rd_id
        ues_id = res_to_ues_one.get(res_id)
        if ues_id is not None:
            ues_to_eu[int(ues_id)].append(eid)
            eu_to_ues[eid] = int(ues_id)

    return {
        "union_energy_system_list": t["union_energy_system_list"],
        "regional_energy_system_list": t["regional_energy_system_list"],
        "regional_district_list": t["regional_district_list"],
        "energy_unit_list": [{"id": x.id, "name": x.name} for x in eu_objs],
        "ues_to_res_mapping": t["regional_energy_system_mapping"],
        "ues_to_rd_mapping": t["ues_to_rd_mapping"],
        "res_to_rd_mapping": t["res_to_rd_mapping"],
        "res_to_ues_mapping_one": t["res_to_ues_mapping_one"],
        "rd_to_res_mapping": t["rd_to_res_mapping"],
        "rd_to_ues_mapping": t["rd_to_ues_mapping"],
        "ues_to_eu_ids": {str(k): v for k, v in ues_to_eu.items()},
        "res_to_eu_ids": {str(k): v for k, v in res_to_eu.items()},
        "rd_to_eu_ids": {str(k): v for k, v in rd_to_eu.items()},
        "eu_to_res_id": {str(k): v for k, v in eu_to_res.items()},
        "eu_to_rd_id": {str(k): v for k, v in eu_to_rd.items()},
        "eu_to_ues_id": {str(k): v for k, v in eu_to_ues.items()},
        "skip_territory_filter_cascade": False,
    }


def get_energy_consumption_fo_filter_cascade_data() -> dict[str, Any]:
    """
    Списки и маппинги для каскадных фильтров сводки по ФО (ФО ↔ субъект РФ),
    те же связи, что в get_territorial_filter_reference_data / выгрузке Excel.
    """
    from app.generation.services.station_services.filters_services import (
        get_territorial_filter_reference_data,
    )

    t = get_territorial_filter_reference_data()
    fd_to_rd = t["fd_to_rd_mapping"]
    rd_to_fd_one = t["rd_to_fd_mapping_one"]
    return {
        "federal_district_list": t["federal_district_list"],
        "regional_district_list": t["regional_district_list"],
        "fd_to_rd_mapping": {
            str(k): (v if isinstance(v, list) else list(v)) for k, v in fd_to_rd.items()
        },
        "rd_to_fd_mapping_one": {str(k): int(v) for k, v in rd_to_fd_one.items()},
        "skip_territory_filter_cascade": False,
    }


def get_energy_consumption_ez_filter_cascade_data() -> dict[str, Any]:
    """
    Каскад энергозона ↔ РЭС для сводки по энергозонам (связь как при построении дерева сводки).
    """
    from collections import defaultdict

    from sqlalchemy.orm import selectinload

    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_system_list_full,
    )
    from app.refdata.models.energy_systems.energy_zone_model import EnergyZone

    ez_query = EnergyZone.query.options(selectinload(EnergyZone.regional_districts))
    ez_query = dps.filter_parents_by_version(ez_query, EnergyZone)
    zones = sorted(
        [z for z in ez_query.all() if _is_valid_named_item(z)],
        key=_energy_zone_number_sort_key,
    )

    res_query = RegionalEnergySystem.query.options(
        selectinload(RegionalEnergySystem.regional_districts)
    )
    res_query = dps.filter_parents_by_version(res_query, RegionalEnergySystem)
    all_res = [r for r in res_query.all() if _is_valid_named_item(r)]

    ez_to_res: dict[int, list[int]] = {}
    res_to_ez_ids: dict[int, list[int]] = defaultdict(list)

    for ez in zones:
        zone_rd_ids = {rd.id for rd in getattr(ez, "regional_districts", []) or []}
        res_ids: list[int] = []
        for res in all_res:
            rds_in_zone = [rd for rd in res.regional_districts if rd.id in zone_rd_ids]
            if not rds_in_zone:
                continue
            rid = int(res.id)
            res_ids.append(rid)
            eid = int(ez.id)
            lst = res_to_ez_ids[rid]
            if eid not in lst:
                lst.append(eid)
        ez_to_res[int(ez.id)] = res_ids

    res_objs = get_regional_energy_system_list_full()
    regional_energy_system_list = [{"id": x.id, "name": x.name} for x in res_objs]

    energy_zone_list = [{"id": x.id, "name": f"{x.number} — {x.name}"} for x in zones]

    return {
        "energy_zone_list": energy_zone_list,
        "regional_energy_system_list": regional_energy_system_list,
        "ez_to_res_mapping": {str(k): v for k, v in ez_to_res.items()},
        "res_to_ez_mapping": {str(k): v for k, v in res_to_ez_ids.items()},
        "skip_territory_filter_cascade": False,
    }
