# -*- coding: utf-8 -*-
"""
API маршруты для работы с external_code (универсальными внешними кодами).
Позволяют внешним системам получать данные по стабильным идентификаторам,
независимо от версии базы данных.
"""

from flask import jsonify, request
from app.extensions import db
from app.generation.routes.stations import station_bp
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.common.models.database_version_model import DatabaseVersion
from sqlalchemy.orm import joinedload


@station_bp.route('/api/external_codes/station/<external_code>', methods=['GET'])
def get_station_by_external_code(external_code):
    """
    Получить данные станции по external_code.
    
    Пример запроса:
        GET /api/external_codes/station/abc-123-def-456
    
    Возвращает:
        {
            "type": "Электростанция",
            "external_code": "abc-123-def-456",
            "database_version_id": 7,
            "database_version": "Наименование версии базы данных",
            "id": 123,
            "name": "Название станции",
            "regional_district": "Наименование субъекта",
            "station_type": "Наименование типа станции",
            "gen_company": "Наименование генерирующей компании",
        }
    """
    station = db.session.query(Station).options(
        joinedload(Station.regional_district),
        joinedload(Station.station_type),
        joinedload(Station.machines).joinedload(Machine.gen_company)
    ).filter_by(external_code=external_code).first_or_404()
    
    # Получаем наименование версии базы данных
    database_version_name = None
    if station.database_version_id:
        db_version = db.session.query(DatabaseVersion).filter_by(id=station.database_version_id).first()
        if db_version:
            database_version_name = db_version.name
    
    # Получаем наименования генерирующих компаний через агрегаты
    gen_companies = {machine.gen_company.name for machine in station.machines if machine.gen_company}
    gen_company = ", ".join(sorted(gen_companies)) if gen_companies else None
    
    # Сохраняем порядок полей как в документации
    return jsonify({
        "type": "Электростанция",
        "external_code": station.external_code,
        "database_version_id": station.database_version_id,
        "database_version": database_version_name,
        "id_station": station.id,
        "name_station": station.name,
        "regional_district": station.regional_district.name if station.regional_district else None,
        "station_type": station.station_type.name if station.station_type else None,
        "gen_company": gen_company,
    })


@station_bp.route('/api/external_codes/machine/<external_code>', methods=['GET'])
def get_machine_by_external_code(external_code):
    """
    Получить данные агрегата по external_code.
    
    Пример запроса:
        GET /api/external_codes/machine/machine-code-123
    
    Возвращает:
        {
            "type": "Агрегат",
            "external_code": "machine-code-123",
            "database_version_id": 7,
            "database_version": "Наименование версии базы данных",
            "id": 789,
            "machine_number": "1",
            "machine_name": "Название агрегата",
            "id_station": 123,
            "station_external_code": "abc-123-def-456",
            "equipment_group": "Наименование группы оборудования",
            "regional_district": "Наименование субъекта",
            "gen_company": "Наименование генерирующей компании",
        }
    """
    machine = db.session.query(Machine).options(
        joinedload(Machine.machine_station).joinedload(Station.regional_district),
        joinedload(Machine.equipment_group),
        joinedload(Machine.gen_company)
    ).filter_by(external_code=external_code).first_or_404()
    
    # Получаем наименование версии базы данных
    database_version_name = None
    if machine.database_version_id:
        db_version = db.session.query(DatabaseVersion).filter_by(id=machine.database_version_id).first()
        if db_version:
            database_version_name = db_version.name
    
    # Получаем regional_district через станцию
    regional_district_name = None
    if machine.machine_station and machine.machine_station.regional_district:
        regional_district_name = machine.machine_station.regional_district.name
    
    result = {
        "type": "Агрегат",
        "external_code": machine.external_code,
        "database_version_id": machine.database_version_id,
        "database_version": database_version_name,
        "id_machine": machine.id,
        "machine_number": machine.machine_number,
        "machine_name": machine.machine_name,
        "id_station": machine.id_station,
        "station_external_code": machine.machine_station.external_code if machine.machine_station else None,
        "equipment_group": machine.equipment_group.name if machine.equipment_group else None,
        "regional_district": regional_district_name,
        "gen_company": machine.gen_company.name if machine.gen_company else None,
    }
    
    return jsonify(result)


@station_bp.route('/api/external_codes/batch', methods=['POST'])
def get_multiple_by_external_codes():
    """
    Получить данные сразу для нескольких external_code (batch запрос).
    
    Полезно для внешних систем, которым нужно получить данные для множества сущностей
    за один запрос.
    
    Пример запроса:
        POST /api/external_codes/batch
        {
            "stations": ["code1", "code2"],
            "machines": ["code4", "code5"]
        }
    
    Возвращает:
        {
            "stations": [...],
            "machines": [...]
        }
    """
    data = request.get_json() or {}
    
    result = {
        "stations": [],
        "machines": []
    }
    
    # Получаем станции
    station_codes = data.get("stations", [])
    if station_codes:
        stations = db.session.query(Station).filter(Station.external_code.in_(station_codes)).all()
        result["stations"] = [
            {
                "external_code": s.external_code,
                "id": s.id,
                "name": s.name,
                "name_so": s.name_so,
            }
            for s in stations
        ]
    
    # Получаем агрегаты
    machine_codes = data.get("machines", [])
    if machine_codes:
        machines = db.session.query(Machine).filter(Machine.external_code.in_(machine_codes)).all()
        result["machines"] = [
            {
                "external_code": m.external_code,
                "id": m.id,
                "machine_name": m.machine_name,
                "machine_number": m.machine_number,
            }
            for m in machines
        ]
    
    return jsonify(result)
