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
from config import SCHEMA_FUEL, SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.versioned_model import VersionedModelMixin

class Machine(db.Model, VersionedModelMixin):
    __tablename__ = 'machines'
    __table_args__ = (
        Index('ix_machine_id_station', 'id_station'),
        Index('ix_machine_id_condition_type', 'id_condition_type'),
        Index('ix_machine_id_tes_machine_type', 'id_tes_machine_type'),
        Index('ix_machine_id_equipment_group', 'id_equipment_group'),
        Index('ix_machine_equipment_group_set_id', 'equipment_group_set_id'),
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
    machine_name = db.Column(db.String(1024), nullable=False, index=True)
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

    # FK -> EquipmentGroupSet (общая группа оборудования)
    equipment_group_set_id = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_FUEL}.gs_fue_equipment_group_sets.id", ondelete="RESTRICT"
        ),
        nullable=True,
        index=True,
    )
    equipment_group_set = db.relationship('EquipmentGroupSet', back_populates='machines')

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
    machine_names = db.relationship(
        'MachineName',
        back_populates='machine_name_rel',
        cascade="all, delete-orphan",
        foreign_keys='MachineName.id_machine',
    )

    # фактический год ввода в эксплуатацию
    date_exploitation = db.Column(db.Integer, nullable=True)

    # фактический год ввода в работу
    date_commission_year = db.Column(db.Integer, nullable=True)

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
    
    # фактическая дата перемаркировки (может содержать несколько дат)
    date_relabing_fact = db.Column(db.String(255), nullable=True)
    
    # фактическая дата уточнения (может содержать несколько дат)
    date_update_fact = db.Column(db.String(255), nullable=True)

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
    def commission_display(self) -> str | int | None:
        """
        Отображаемое значение для колонки 'Ввод в работу' на station_list:
        Machine.date_commission_year или Machine.date_exploitation_expected.
        """
        if self.date_commission_year is not None:
            return self.date_commission_year
        if self.date_exploitation_expected is not None:
            return self.date_exploitation_expected
        return None

    @property
    def exploitation_display(self) -> int | None:
        """
        Отображаемое значение для колонки 'Ввод в экспл.' на station_list:
        - фактический год ввода в эксплуатацию (date_exploitation), если указан;
        - иначе ожидаемый год ввода в эксплуатацию (date_exploitation_expected).
        """
        if self.date_exploitation is not None:
            return self.date_exploitation
        if self.date_exploitation_expected is not None:
            return self.date_exploitation_expected
        return None

    @property
    def decompressing_display(self) -> str | int | None:
        """
        Отображаемое значение для колонки 'Вывод из экспл.' на station_list:
        Machine.date_decompressing_fact (год) или Machine.date_decompressing_expected.
        """
        from app.common.services.help_services import convert_to_date

        if self.date_decompressing_fact:
            dt = convert_to_date(self.date_decompressing_fact)
            if dt is not None:
                return dt.year
        if self.date_decompressing_expected is not None:
            return self.date_decompressing_expected
        return None

    @property
    def group_rowspan(self):
        return getattr(self, "_group_rowspan", None)

    @group_rowspan.setter
    def group_rowspan(self, value):
        self._group_rowspan = value

    def _relabing_year_for_display(self, dt) -> int | None:
        """
        Для date_relabing_fact: если дата 01.01.год, то отображаемый год = год-1.
        Иначе — год как есть.
        """
        if dt is None:
            return None
        if dt.month == 1 and dt.day == 1:
            return dt.year - 1
        return dt.year

    @property
    def modernization_display(self) -> str | None:
        """
        Отображаемое значение для колонки 'Модерн.' на station_list.

        Требование:
        - показывать один год:
          * либо ожидаемый год модернизации (date_modernization_expected),
          * либо максимальный год, полученный из поля фактической даты(дат) перемаркировки
            (date_relabing_fact) с учётом правила:
              - если дата 01.01.год → отображаемый год = год-1.
        - если есть и ожидаемый год модернизации, и годы из перемаркировок,
          берём максимальный год из всех.
        """
        from app.common.services.help_services import normalize_date_list, convert_to_date

        years: list[int] = []

        # 1) ожидаемый год модернизации
        if self.date_modernization_expected is not None:
            years.append(self.date_modernization_expected)

        # 2) годы из фактических дат перемаркировки (может быть несколько дат)
        if self.date_relabing_fact:
            normalized = normalize_date_list(self.date_relabing_fact)
            if normalized:
                tokens = [t.strip() for t in normalized.split(",") if t.strip()]
                for token in tokens:
                    dt = convert_to_date(token)
                    if dt is None:
                        continue
                    display_year = self._relabing_year_for_display(dt)
                    if display_year is not None:
                        years.append(display_year)

        if not years:
            return None

        # Возвращаем максимальный год среди всех возможных источников
        return str(max(years))

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
        """
        Основной тип топлива агрегата для сводной таблицы.

        Логика:
        - учитываем только годы, где есть ненулевая мощность (p_ust/p_ogr/p_rasp);
        - игнорируем техническое значение «не указано»;
        - если по всем годам только «не указано» при нулевых мощностях — считаем, что топлива нет.
        """
        from decimal import Decimal, InvalidOperation
        from app.common.services.database_version_filter import get_current_db_version_id

        current_version_id = get_current_db_version_id()

        def _is_zero_or_none(value) -> bool:
            if value is None:
                return True
            try:
                return Decimal(value) == 0
            except (InvalidOperation, TypeError):
                try:
                    return float(value) == 0.0
                except (TypeError, ValueError):
                    return False

        # Карта мощностей по годам с учётом версии БД
        powers_by_year: dict[int, object] = {}
        for mp in getattr(self, "machine_powers", []) or []:
            if current_version_id is not None:
                if getattr(mp, "database_version_id", None) != current_version_id:
                    continue
            else:
                if getattr(mp, "database_version_id", None) is not None:
                    continue
            if mp.year_number is not None:
                powers_by_year[mp.year_number] = mp

        def _has_nonzero_power(year: int) -> bool:
            mp = powers_by_year.get(year)
            if mp is None:
                return False
            return not (
                _is_zero_or_none(getattr(mp, "p_ust", None))
                and _is_zero_or_none(getattr(mp, "p_ogr", None))
                and _is_zero_or_none(getattr(mp, "p_rasp", None))
            )

        fuel_names = set()
        for mf in self.machine_fuels:
            # Фильтрация по версии БД
            if current_version_id is not None:
                if getattr(mf, "database_version_id", None) != current_version_id:
                    continue
            else:
                if getattr(mf, "database_version_id", None) is not None:
                    continue

            year = getattr(mf, "year_number", None)
            if not year or not _has_nonzero_power(year):
                # Нет ненулевой мощности в этом году — топливо считаем неиспользуемым
                continue

            fuel_obj = getattr(mf, "fuel", None)
            fuel_type = getattr(fuel_obj, "fuel_type", None) if fuel_obj else None
            fuel_type_name = getattr(fuel_type, "name", None)
            if fuel_type_name and fuel_type_name.lower() != "не указано":
                fuel_names.add(fuel_type_name)

        return ", ".join(sorted(fuel_names)) if fuel_names else None

    @property
    def fuel_type_by_year(self):
        """
        Возвращает словарь {год: тип_топлива} для отображения в таблице/экспорте.
        
        Учитывает текущую отображаемую версию БД:
        - если выбрана версия, берём только записи с этим database_version_id;
        - если версия не выбрана, берём только записи без версии (NULL).
        """
        from decimal import Decimal, InvalidOperation
        from app.common.services.database_version_filter import get_current_db_version_id
        from app.common.services.choices_cache_service import choices_cache
        from app.refdata.models.fuels.fuel_model import Fuel

        current_version_id = get_current_db_version_id()
        result: dict[int, str] = {}

        def _is_zero_or_none(value) -> bool:
            if value is None:
                return True
            try:
                return Decimal(value) == 0
            except (InvalidOperation, TypeError):
                try:
                    return float(value) == 0.0
                except (TypeError, ValueError):
                    return False

        # Карта мощностей по годам для оценки «есть ли реальная мощность»
        powers_by_year: dict[int, object] = {}
        for mp in getattr(self, "machine_powers", []) or []:
            if current_version_id is not None:
                if getattr(mp, "database_version_id", None) != current_version_id:
                    continue
            else:
                if getattr(mp, "database_version_id", None) is not None:
                    continue
            if mp.year_number is not None:
                powers_by_year[mp.year_number] = mp

        def _has_nonzero_power(year: int) -> bool:
            mp = powers_by_year.get(year)
            if mp is None:
                return False
            return not (
                _is_zero_or_none(getattr(mp, "p_ust", None))
                and _is_zero_or_none(getattr(mp, "p_ogr", None))
                and _is_zero_or_none(getattr(mp, "p_rasp", None))
            )

        # Определяем ID «технического» топлива "не указано" (если оно есть в справочнике)
        try:
            fuel_names = dict(choices_cache.get_choices(Fuel, Fuel.id))
            default_fuel_id = None
            for value, label in fuel_names.items():
                if isinstance(label, str) and label.strip().lower() == "не указано":
                    default_fuel_id = value
                    break
        except Exception:
            default_fuel_id = None

        for mf in self.machine_fuels:
            # Фильтрация по версии БД
            if current_version_id is not None:
                if getattr(mf, "database_version_id", None) != current_version_id:
                    continue
            else:
                # При отсутствии выбранной версии показываем только записи без версии
                if getattr(mf, "database_version_id", None) is not None:
                    continue

            year = getattr(mf, "year_number", None)
            fuel_obj = getattr(mf, "fuel", None)
            fuel_type = getattr(fuel_obj, "fuel_type", None) if fuel_obj else None
            if not year or not fuel_type:
                continue

            # Если по году все мощности = 0 и топливо установлено в техническое "не указано",
            # трактуем это как отсутствие топлива (прочерк в таблице).
            if default_fuel_id is not None and getattr(mf, "id_fuel", None) == default_fuel_id:
                if not _has_nonzero_power(year):
                    continue

            fuel_type_name = getattr(fuel_type, "name", None)
            if not fuel_type_name:
                continue

            # Для всех остальных случаев (в т.ч. когда "не указано" выбрано при ненулевой мощности)
            # используем наименование типа топлива как есть (часто это "прочее").
            result[year] = fuel_type_name

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
    
    # Получаем external_code группы оборудования (если есть)
    equipment_group_set_code = None
    
    # Пытаемся получить через связь, если она загружена
    if target.equipment_group_set and hasattr(target.equipment_group_set, 'external_code'):
        equipment_group_set_code = target.equipment_group_set.external_code
    
    # Если связь не загружена, загружаем через SQL-запрос
    if not equipment_group_set_code and target.equipment_group_set_id:
        result = connection.execute(
            sql_text(
                f"SELECT external_code FROM {SCHEMA_FUEL}.gs_fue_equipment_group_sets "
                "WHERE id = :id"
            ),
            {"id": target.equipment_group_set_id}
        )
        row = result.fetchone()
        if row:
            equipment_group_set_code = row[0]
    
    # Если группа оборудования не указана, используем fallback
    if not equipment_group_set_code:
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
        equipment_group_set_code = str(uuid.uuid5(uuid.NAMESPACE_URL, seg_key))
    
    # Формируем ключ для трехсторонней привязки: станция-группа оборудования-агрегат
    machine_key = (
        f"machine|equipment_group_set|{equipment_group_set_code}|"
        f"ti|{target.id_ti or ''}|num|{target.machine_number or ''}|name|{target.machine_name or ''}"
    )
    
    # Генерируем детерминированный UUID5
    target.external_code = str(uuid.uuid5(uuid.NAMESPACE_URL, machine_key))
