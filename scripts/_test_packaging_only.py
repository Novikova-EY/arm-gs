# -*- coding: utf-8 -*-
import sys
from io import BytesIO

sys.path.insert(0, r"c:\arm_gs")
from app.energy_consumption.electrical_intensity.services.electrical_intensity_export_services import (
    _apply_ei_chart_excel_packaging,
)

EXP14 = r"c:\Users\novikova-eyu\Downloads\elektroemkost (14).xlsx"
with open(EXP14, "rb") as f:
    patched = _apply_ei_chart_excel_packaging(BytesIO(f.read()))
open(r"c:\arm_gs\scripts\_14_packaged_only.xlsx", "wb").write(patched.getvalue())
print("written _14_packaged_only.xlsx", len(patched.getvalue()))
