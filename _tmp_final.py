# -*- coding: utf-8 -*-
import re
from app import create_app
import psycopg2

app = create_app()
conn = psycopg2.connect(host="localhost", port=5432, dbname="gs_gen", user="generation", password="R7fP9wQk")
cur = conn.cursor(); cur.execute("select id from gs_auth.users order by id limit 1")
uid = cur.fetchone()[0]; conn.close()
client = app.test_client()
with client.session_transaction() as sess:
    sess["_user_id"] = str(uid); sess["_fresh"] = True

def sig_digits(text):
    digits = re.sub(r"\D", "", text).lstrip("0").rstrip("0")
    return len(digits)

for label, url in (
    ("zv-vse", "/ecology/analysis/zv-vse/?affiliation_filter=%D0%BE%D1%82%D1%80%D0%B0%D1%81%D0%BB%D1%8C&rounding_digits=0&per_page=all"),
    ("pg-vse", "/ecology/analysis/pg-vse/?rounding_digits=0&per_page=all"),
):
    html = client.get(url).data.decode("utf-8")
    cells = re.findall(r'data-col-key="([^"]+)"[^>]*>\s*([-\u00a0\d\s]*,\d+)\s*</td>', html)
    worst = sorted(cells, key=lambda kv: -sig_digits(kv[1]))[:5]
    print(label, "numeric cells:", len(cells), "max sig digits:", sig_digits(worst[0][1]) if worst else 0)
    for k, v in worst:
        print("   ", k, "=", v.strip(), "| signif:", sig_digits(v))
