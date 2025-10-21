# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.extensions import db
from app import create_app

app = create_app()

with app.app_context():
    result = db.session.execute(db.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'generation' AND table_name = 'stations' "
        "AND column_name = 'id_station_type'"
    ))
    row = result.fetchone()
    if row:
        print("[OK] Столбец id_station_type найден в таблице stations")
    else:
        print("[FAIL] Столбец id_station_type НЕ найден в таблице stations")
    
    # Проверим также столбец в machines
    result2 = db.session.execute(db.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'generation' AND table_name = 'machines' "
        "AND column_name = 'id_station_type'"
    ))
    row2 = result2.fetchone()
    if row2:
        print("[FAIL] Столбец id_station_type все еще есть в таблице machines (ОШИБКА!)")
    else:
        print("[OK] Столбец id_station_type удален из таблицы machines")
