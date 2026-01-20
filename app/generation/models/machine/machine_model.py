# -*- coding: utf-8 -*-
"""
Machine model (Агрегат электростанции).
- Сохранены все исходные связи и индексы.
- Добавлены серверные таймстемпы (UTC).
"""
import uuid
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from sqlalchemy import event
from sqlalchemy.sql import text as sql_text
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.versioned_model import VersionedModelMixin

class Machine(db.Model, VersionedModelMixin):
    __tablename__ = 'machines'
    __table_args__ = (
        Index('ix_machine_id_station', 'id_station'),
        Index('ix_machine_id_condition_type', 'id_condition_type'),
        Index('ix_machine_id_tes_machine_type', 'id_tes_machine_type'),
        Index('ix_machine_id_equipment_group', 'id_equipment_group'),
        Index('ix_machine_station_equipment_group_id', 'station_equipment_group_id'),
        Index('ix_machine_id_gen_company', 'id_gen_company'),
        Index('ix_machine_id_energy_area', 'id_energy_area'),
        Index('ix_machine_external_code', 'external_code'),
        Index('ix_machine_date_exploitation', 'date_exploitation'),
        Index('ix_machine_date_decompressing_expected', 'date_decompressing_expected'),
        Index('ix_machine_date_modernization_expected', 'date_modernization_expected'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Универсальный внешний код для трехсторонней привязки:
    # станция - группа оборудования - агрегат
    external_code = db.Column(
        db.String(36),
        nullable=False,
    )
    id_ti = db.Column(db.Integer, nullable=True)

    # FK -> ConditionType
    id_condition_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_condition_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    condition_type = db.relationship('ConditionType', back_populates='machines')

    # FK -> GenCompany
    id_gen_company = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_companies.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    gen_company = db.relationship('GenCompany', back_populates='machines')

    # FK -> Station
    id_station = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.stations.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    machine_station = db.relationship('Station', back_populates='machines')

    # FK -> EnergyArea
    id_energy_area = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_energy_areas.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    energy_area = db.relationship('EnergyArea', back_populates='machines')

    # Основные атрибуты
    machine_number = db.Column(db.String(80), nullable=False, index=True)
    machine_name = db.Column(db.String(255), nullable=False, index=True)
    machine_group = db.Column(db.String(255), nullable=True)
    fuel_so = db.Column(db.String(255), nullable=True)

    # FK -> MachineType
    id_machine_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_machine_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    machine_type = db.relationship('MachineType', back_populates='machines')

    # FK -> TesMachineType
    id_tes_machine_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_tes_machine_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    tes_machine_type = db.relationship('TesMachineType', back_populates='machines')

    # FK -> TechnologyAvailability  
    id_technology_availability = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_technology_availabilities.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    technology_availability = db.relationship('TechnologyAvailability', back_populates='machines')

    # FK -> TechnologyType 
    id_technology_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_technology_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    technology_type = db.relationship('TechnologyType', back_populates='machines')

    # FK -> EquipmentGroup
    id_equipment_group = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_equipment_groups.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    equipment_group = db.relationship('EquipmentGroup', back_populates='machines')

    # FK -> StationEquipmentGroup (группа оборудования на конкретной станции)
    station_equipment_group_id = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.station_equipment_groups.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    station_equipment_group = db.relationship('StationEquipmentGroup', back_populates='machines')

    # Children: powers / fuels / tes_types
    machine_powers = db.relationship(
        'MachinePower',
        back_populates='machine_power',
        cascade="all, delete-orphan",
        foreign_keys='MachinePower.id_machine',
    )
    machine_fuels = db.relationship(
        'MachineFuel',
        back_populates='machine_fuel',
        cascade="all, delete-orphan",
        foreign_keys='MachineFuel.id_machine',
    )
    machine_tes_types = db.relationship(
        'MachineTesType',
        back_populates='machine_tes_type',
        cascade="all, delete-orphan",
        foreign_keys='MachineTesType.id_machine',
    )

    # фактический год ввода в эксплуатацию
    date_exploitation = db.Column(db.Integer, nullable=True)

    # ожидаемый год ввода в эксплуатацию
    date_exploitation_expected = db.Column(db.Integer, nullable=True)

    # фактическая дата ввода в работу
    date_commission_fact = db.Column(db.String(10), nullable=True)
    
    # фактическая дата вывода из эксплуатации
    date_decompressing_fact = db.Column(db.String(10), nullable=True)
    
    # ожидаемый год вывода из эксплуатации
    date_decompressing_expected = db.Column(db.Integer, nullable=True)

    # фактическая дата присоединения
    date_joining_fact = db.Column(db.String(10), nullable=True)
    
    # ожидаемая дата присоединения
    date_joining_expected = db.Column(db.String(10), nullable=True)

    # фактическая дата отсоединения
    date_detatchment_fact = db.Column(db.String(10), nullable=True)

    # ожидаемый год модернизации
    date_modernization_expected = db.Column(db.Integer, nullable=True)
    
    # фактическая дата перемаркировки
    date_relabing_fact = db.Column(db.String(10), nullable=True)
    
    # фактическая дата уточнения
    date_update_fact = db.Column(db.String(10), nullable=True)

    # примечание
    note = db.Column(db.String(512), nullable=True)

    # Документ-основание для изменения параметров агрегата
    change_document = db.Column(db.Text, nullable=True)  

    year_modern = db.Column(db.String(10), nullable=True)
    year_demontaz = db.Column(db.String(10), nullable=True)
    resurs_coal = db.Column(db.String(10), nullable=True)
    resurs_gas = db.Column(db.String(10), nullable=True)

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # version для оптимистической блокировки (определен в VersionedModelMixin)
    # version = db.Column(db.Integer, nullable=False, default=1)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # ----- Runtime helpers (не маппятся в БД) -----
    @property
    def group_rowspan(self):
        return getattr(self, "_group_rowspan", None)

    @group_rowspan.setter
    def group_rowspan(self, value):
        self._group_rowspan = value

    @property
    def fuel_rowspan(self):
        return getattr(self, "_fuel_rowspan", None)

    @fuel_rowspan.setter
    def fuel_rowspan(self, value):
        self._fuel_rowspan = value

    @property
    def tes_types(self):
        tes_type_names = {
            mtt.tes_type.name
            for mtt in self.machine_tes_types
            if mtt.tes_type and mtt.tes_type.name and mtt.tes_type.name.lower() != "не указано"
        }
        return ", ".join(sorted(tes_type_names)) if tes_type_names else None

    @property
    def primary_fuel_type(self):
        fuel_names = {
            mf.fuel.fuel_type.name
            for mf in self.machine_fuels
            if mf.fuel and mf.fuel.fuel_type and mf.fuel.fuel_type.name.lower() != "не указано"
        }
        return ", ".join(sorted(fuel_names)) if fuel_names else None

    @property
    def fuel_type_by_year(self):
        """
        Возвращает словарь {год: тип_топлива} для отображения в таблице/экспорте.
        
        Учитывает текущую отображаемую версию БД:
        - если выбрана версия, берём только записи с этим database_version_id;
        - если версия не выбрана, берём только записи без версии (NULL).
        """
        from app.common.services.database_version_filter import get_current_db_version_id

        current_version_id = get_current_db_version_id()
        result = {}

        for mf in self.machine_fuels:
            # Фильтрация по версии БД
            if current_version_id is not None:
                if mf.database_version_id != current_version_id:
                    continue
            else:
                # При отсутствии выбранной версии показываем только записи без версии
                if mf.database_version_id is not None:
                    continue

            if mf.year_number and mf.fuel and mf.fuel.fuel_type:
                fuel_type_name = mf.fuel.fuel_type.name
                # Пропускаем "Не указано"
                if fuel_type_name and fuel_type_name.lower() != "не указано":
                    result[mf.year_number] = fuel_type_name

        return result

    @property
    def id_regional_energy_system(self):
        """
        Вычисляемый id РЭС для агрегата.
        Берём со станции (Station.id_regional_energy_system), при отсутствии — пытаемся получить через субъект РФ.

        ВАЖНО: это НЕ колонка БД, а runtime-helper для группировки/отображения.
        """
        st = getattr(self, "machine_station", None)
        if not st:
            return None
        direct = getattr(st, "id_regional_energy_system", None)
        if direct:
            return direct
        rd = getattr(st, "regional_district", None)
        ress = getattr(rd, "regional_energy_systems", None) if rd else None
        if ress:
            first = ress[0]
            return getattr(first, "id", None)
        return None

    def __repr__(self) -> str:
        return f"<Machine id={self.id} name={self.machine_name!r} station_id={self.id_station}>"


@event.listens_for(Machine, 'before_insert')
def generate_external_code_before_insert(mapper, connection, target):
    """
    Генерирует external_code для агрегата перед вставкой записи.
    Трехсторонняя привязка: станция - группа оборудования - агрегат
    """
    # Если код уже есть, не меняем его
    if target.external_code:
        return
    
    # Получаем external_code связки станция-группа оборудования
    station_equipment_group_code = None
    
    # Пытаемся получить через связь, если она загружена
    if target.station_equipment_group and hasattr(target.station_equipment_group, 'external_code'):
        station_equipment_group_code = target.station_equipment_group.external_code
    
    # Если связь не загружена, загружаем через SQL-запрос
    if not station_equipment_group_code and target.station_equipment_group_id:
        result = connection.execute(
            sql_text(f"SELECT external_code FROM {SCHEMA_GENERATION}.station_equipment_groups WHERE id = :id"),
            {"id": target.station_equipment_group_id}
        )
        row = result.fetchone()
        if row:
            station_equipment_group_code = row[0]
    
    # Если связка станция-группа оборудования не указана, используем fallback
    if not station_equipment_group_code:
        # Получаем external_code станции
        station_code = None
        if target.machine_station and hasattr(target.machine_station, 'external_code'):
            station_code = target.machine_station.external_code
        elif target.id_station:
            result = connection.execute(
                sql_text(f"SELECT external_code FROM {SCHEMA_GENERATION}.stations WHERE id = :id"),
                {"id": target.id_station}
            )
            row = result.fetchone()
            if row:
                station_code = row[0]
        
        # external_code группы оборудования НЕ используем; берем только ID группы оборудования
        equipment_group_id = target.id_equipment_group or 0

        # Fallback на ID, если external_code станции ещё не заполнен
        station_code = station_code or f"station_id_{target.id_station}"
        
        # Формируем ключ связки станция-группа оборудования (через ID группы оборудования)
        seg_key = f"station_equipment_group|station|{station_code}|equipment_group_id|{equipment_group_id}"
        station_equipment_group_code = str(uuid.uuid5(uuid.NAMESPACE_URL, seg_key))
    
    # Формируем ключ для трехсторонней привязки: станция-группа оборудования-агрегат
    machine_key = (
        f"machine|station_equipment_group|{station_equipment_group_code}|"
        f"ti|{target.id_ti or ''}|num|{target.machine_number or ''}|name|{target.machine_name or ''}"
    )
    
    # Генерируем детерминированный UUID5
    target.external_code = str(uuid.uuid5(uuid.NAMESPACE_URL, machine_key))
