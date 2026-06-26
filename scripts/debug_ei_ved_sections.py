# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from run import app
from app.common.services.database_version_services import get_current_version
from app.electrical_intensity.services.electrical_intensity_services import (
    _refdata_ved_types_for_version,
    _ved_section_display_name,
    _federal_districts_for_page,
    _build_ved_sections_for_fd,
    _load_fd_ei_year_values_map,
    _load_fd_ei_coef_map,
    _load_product_output_values_map,
    _load_ved_consumption_values_map,
    _load_accum_fixed_capital_values_map,
    _ei_current_year_number,
    _refdata_ved_ids,
    build_electrical_intensity_page_context,
)
from app.electrical_intensity.services.electrical_intensity_page_services import (
    parse_electrical_intensity_page_kwargs,
)
from app.economics.models.federal_district_product_output_parameter_model import (
    FederalDistrictProductOutputParameter,
)
from app.economics.models.federal_district_eat_consumption_parameter_model import (
    FederalDistrictEATConsumptionParameter,
)
from app.economics.models.federal_district_accum_fixed_capital_parameter_model import (
    FederalDistrictAccumFixedCapitalParameter,
)

url = "/electrical_intensity_fo/?rounding_digits=1&start_year=2010&end_year=2042"
with app.app_context():
    with app.test_request_context(url):
        vid = get_current_version()
        veds = _refdata_ved_types_for_version(vid)
        print("ved count", len(veds))
        named = [v for v in veds if _ved_section_display_name(v)]
        print("with display name", len(named))
        for v in named[:15]:
            print(" ", v.id, _ved_section_display_name(v))

        kw = parse_electrical_intensity_page_kwargs(rounding_digits=1)
        for k in (
            "data_start_year",
            "data_end_year",
            "lt_ei_initial_visible_years",
            "lt_ei_year_seg_state",
        ):
            kw.pop(k, None)
        ctx = build_electrical_intensity_page_context(**kw)
        fd_block = next(
            b for b in ctx["territory_blocks"] if b.get("territory_kind") == "fd"
        )
        print(
            "page block",
            fd_block.get("abbr"),
            "sections",
            len(fd_block.get("ved_sections") or []),
        )
        for s in fd_block.get("ved_sections") or []:
            print(
                " ",
                s.get("ved_name"),
                "chart",
                bool(s.get("scatter_chart")),
                "has_ei",
                s.get("has_ei_block"),
            )

        fd = _federal_districts_for_page()[0]
        years = list(range(2010, 2043))
        fd_filter = FederalDistrictProductOutputParameter.id_federal_district == fd.id
        product = _load_product_output_values_map(
            version_id=vid,
            model=FederalDistrictProductOutputParameter,
            territory_filter=fd_filter,
        )
        cons = _load_ved_consumption_values_map(
            version_id=vid,
            model=FederalDistrictEATConsumptionParameter,
            territory_filter=FederalDistrictEATConsumptionParameter.id_federal_district
            == fd.id,
        )
        accum = _load_accum_fixed_capital_values_map(
            version_id=vid,
            model=FederalDistrictAccumFixedCapitalParameter,
            territory_filter=FederalDistrictAccumFixedCapitalParameter.id_federal_district
            == fd.id,
        )
        ei = _load_fd_ei_year_values_map(version_id=vid, fd_id=fd.id)
        coef = _load_fd_ei_coef_map(version_id=vid, fd_id=fd.id)
        secs = _build_ved_sections_for_fd(
            ved_types=veds,
            refdata_ved_ids=_refdata_ved_ids(vid),
            product_output_by_ved_year=product,
            consumption_by_ved_year=cons,
            accum_by_ved_year=accum,
            ei_year_by_ved_kind_year=ei,
            coef_by_ved=coef,
            display_years=years,
            rounding_digits=1,
            price_year=2025,
            current_year=_ei_current_year_number(),
        )
        print("direct build sections", len(secs))
        for s in secs:
            print(
                " ",
                s.get("ved_name"),
                "chart",
                bool(s.get("scatter_chart")),
                "has_ei",
                s.get("has_ei_block"),
            )
