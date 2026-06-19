# -*- coding: utf-8 -*-
from zipfile import ZipFile
from openpyxl import load_workbook
import re
import os

EXP15 = r"c:\Users\novikova-eyu\Downloads\elektroemkost (15).xlsx"
EXP14 = r"c:\Users\novikova-eyu\Downloads\elektroemkost (14).xlsx"
REF = r"c:\arm_gs\02.06.26 Расчет электроемкости. Таблица 1.xlsx"

for label, path in [("15", EXP15), ("14", EXP14), ("REF", REF)]:
    if not os.path.exists(path):
        print(label, "MISSING", path)
        continue
    print(f"\n{'='*60}\n{label} size={os.path.getsize(path)}")
    with ZipFile(path) as z:
        names = z.namelist()
        charts = [n for n in names if re.match(r"xl/charts/chart\d+\.xml$", n)]
        rels = [n for n in names if "/_rels/chart" in n]
        drawings = [n for n in names if "drawing" in n and n.endswith(".xml")]
        print("charts", len(charts), "chart rels", len(rels), "drawings", drawings)
        theme = z.read("xl/theme/theme1.xml").decode("utf-8", errors="replace")
        accents = re.findall(r'<a:accent(\d)><a:srgbClr val="([^"]+)"', theme)
        print("theme accents", accents)
        if charts:
            c1 = z.read(charts[0]).decode("utf-8", errors="replace")
            print("chart1 len", len(c1), "start", c1[:200].replace("\n", " "))
            if rels:
                print("chart1 rels:", z.read(rels[0]).decode("utf-8")[:300])
        if "xl/drawings/drawing1.xml" in names:
            d = z.read("xl/drawings/drawing1.xml").decode("utf-8", errors="replace")
            print("drawing anchors", len(re.findall(r"<xdr:twoCellAnchor", d)), "chart refs", len(re.findall(r"r:id=", d)))
    try:
        wb = load_workbook(path)
        ws = wb.active
        print("openpyxl sheet", repr(ws.title), "charts on sheet", len(ws._charts))
        if ws._charts:
            c = ws._charts[0]
            print("  first chart series", len(c.series), "size", c.width, c.height)
    except Exception as e:
        print("openpyxl ERROR", type(e).__name__, e)

# validate XML well-formedness of chart1 and drawing1 in file 15
import xml.etree.ElementTree as ET
with ZipFile(EXP15) as z:
    for fn in ["xl/charts/chart1.xml", "xl/drawings/drawing1.xml", "[Content_Types].xml"]:
        if fn in z.namelist():
            data = z.read(fn)
            try:
                ET.fromstring(data)
                print(f"XML OK: {fn}")
            except ET.ParseError as e:
                print(f"XML BAD: {fn}: {e}")
