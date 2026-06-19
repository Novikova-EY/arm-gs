# -*- coding: utf-8 -*-
from zipfile import ZipFile
import re

EXP14 = r"c:\Users\novikova-eyu\Downloads\elektroemkost (14).xlsx"
with ZipFile(EXP14) as z:
    theme = z.read("xl/theme/theme1.xml").decode("utf-8")
    open(r"c:\arm_gs\scripts\_exp14_theme.xml", "w", encoding="utf-8").write(theme)
    print("len", len(theme))
    print("accent tags", len(re.findall("accent", theme)))
