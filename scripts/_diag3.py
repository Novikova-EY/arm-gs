# -*- coding: utf-8 -*-
from zipfile import ZipFile
import re

EXP15 = r"c:\Users\novikova-eyu\Downloads\elektroemkost (15).xlsx"
EXP14 = r"c:\Users\novikova-eyu\Downloads\elektroemkost (14).xlsx"

for label, path in [("14", EXP14), ("15", EXP15)]:
    with ZipFile(path) as z:
        print(f"\n=== {label} ===")
        for fn in [
            "xl/drawings/_rels/drawing1.xml.rels",
            "[Content_Types].xml",
        ]:
            if fn in z.namelist():
                data = z.read(fn).decode("utf-8")
                print(fn, "len", len(data))
                if "drawing" in fn:
                    print(data[:1500])
        xml = z.read("xl/charts/chart1.xml").decode("utf-8")
        # extract valAx blocks
        for m in re.finditer(r"<valAx>.*?</valAx>", xml, re.S):
            block = m.group(0)
            print("valAx snippet:", block[:600])
