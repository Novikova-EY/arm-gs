# -*- coding: utf-8 -*-
"""
Association table: regional_district <-> regional_energy_system (многие-ко-многим).
- Таблица лежит в схеме refdata (SCHEMA_REFDATA).
- Никакой собственной модели не требуется — используем db.Table.
"""
from app.extensions import db
from config import SCHEMA_REFDATA

regional_district_regional_energy_system = db.Table(
    'gs_sys_regional_district_regional_energy_system',
    db.Column('regional_district_id', db.Integer,
              db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_regional_districts.id', ondelete='RESTRICT'),
              primary_key=True, index=True),
    db.Column('regional_energy_system_id', db.Integer,
              db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id', ondelete='RESTRICT'),
              primary_key=True, index=True),
    schema=SCHEMA_REFDATA
)
