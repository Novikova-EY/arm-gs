# -*- coding: utf-8 -*-
from zipfile import ZipFile
import re

EXP15 = r"c:\Users\novikova-eyu\Downloads\elektroemkost (15).xlsx"
EXP14 = r"c:\Users\novikova-eyu\Downloads\elektroemkost (14).xlsx"

for label, path in [("14", EXP14), ("15", EXP15)]:
    with ZipFile(path) as z:
        xml = z.read("xl/charts/chart1.xml").decode("utf-8")
        drawing = z.read("xl/drawings/drawing1.xml").decode("utf-8")
        print(f"\n=== {label} chart1 ===")
        for pat in [
            r"noFill",
            r"solidFill",
            r"dispUnits",
            r"roundedCorners",
            r"plotVisOnly",
            r"schemeClr",
            r"srgbClr",
        ]:
            print(pat, xml.count(pat))
        # fact series block
        parts = re.split(r"<ser>|</ser>", xml)
        for i, p in enumerate(parts[1:3], 1):
            print(f"  ser fragment {i}:", p[:500])
        print(f"\n=== {label} drawing snippet ===")
        print(drawing[:800])
