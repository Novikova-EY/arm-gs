# -*- coding: utf-8 -*-
"""
Machine model (Агрегат электростанции).
- Сохранены все исходные связи и индексы.
- Добавлены серверные таймстемпы (UTC).
"""
import re
import uuid
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from sqlalchemy import event
from sqlalchemy.sql import text as sql_text
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin

class Machine(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = 'gs_gen_machines'
    __table_args__ = (
        Index('ix_machine_id_station', 'id_station'),
        Index('ix_machine_id_condition_type', 'id_condition_type'),
        Index('ix_machine_id_tes_machine_type', 'id_tes_machine_type'),
        Index('ix_machine_id_equipment_group', 'id_equipment_group'),
        Index('ix_machine_id_gen_company', 'id_gen_company'),
        Index('ix_machine_id_energy_area', 'id_energy_area'),
        Index('ix_machine_external_code', 'external_code'),
        Index('ix_machine_date_exploitation', 'date_exploitation'),
        Index('ix_machine_date_decompressing_expected', 'date_decompressing_expected'),
        Index('ix_machine_date_modernization_power_change_expected', 'date_modernization_power_change_expected'),
        Index('ix_machine_date_modernization_no_power_change_expected', 'date_modernization_no_power_change_expected'),
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
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_condition_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    condition_type = db.relationship('ConditionType', back_populates='machines')

    # FK -> GenCompany
    id_gen_company = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_companies.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    gen_company = db.relationship('GenCompany', back_populates='machines')

    # FK -> Station
    id_station = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.gs_gen_stations.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    machine_station = db.relationship('Station', back_populates='machines')

    # FK -> EnergyArea
    id_energy_area = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_energy_areas.id', ondelete='RESTRICT'),
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
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_machine_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    machine_type = db.relationship('MachineType', back_populates='machines')

    # FK -> TesMachineType
    id_tes_machine_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_tes_machine_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    tes_machine_type = db.relationship('TesMachineType', back_populates='machines')

    # FK -> TechnologyAvailability  
    id_technology_availability = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_technology_availabilities.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    technology_availability = db.relationship('TechnologyAvailability', back_populates='machines')

    # FK -> TechnologyType 
    id_technology_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_technology_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    technology_type = db.relationship('TechnologyType', back_populates='machines')

    # FK -> EquipmentGroupType
    id_equipment_group = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_equipment_groups.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    equipment_group = db.relationship('EquipmentGroupType', back_populates='machines')

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

    # Связь с топливными данными агрегата (схема gs_fue)
    machine_fuel_param = db.relationship(
        'MachineFuelParam',
        back_populates='machine',
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
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

    # ожидаемый год модернизации с изменением мощности
    date_modernization_power_change_expected = db.Column(
        "date_modernization_power_change_expected", db.Integer, nullable=True
    )
    # ожидаемый год модернизации без изменения мощности
    date_modernization_no_power_change_expected = db.Column(
        "date_modernization_no_power_change_expected", db.Integer, nullable=True
    )

    # фактическая дата перемаркировки (может содержать несколько дат)
    date_relabing_fact = db.Column(db.String(255), nullable=True)

    # вид изменений: окончательный вывод / замена / новый ввод
    relabing_outcome = db.Column(db.String(64), nullable=True)
    
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
        Отображаемое значение для колонки 'Год вывода' на station_details:
        либо Ожидаемый год вывода из эксплуатации (date_decompressing_expected),
        либо год из фактической даты (date_decompressing_fact), при этом 01.01.год → год-1.
        """
        from app.common.services.help_services import convert_to_date

        if self.date_decompressing_fact:
            dt = convert_to_date(self.date_decompressing_fact)
            if dt is not None:
                # 01.01.год — считается годом -1
                if dt.month == 1 and dt.day == 1:
                    return dt.year - 1
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
          * либо ожидаемый год модернизации с изменением мощности (date_modernization_power_change_expected),
          * либо ожидаемый год модернизации без изменения мощности (date_modernization_no_power_change_expected),
          * либо максимальный год, полученный из поля фактической даты(дат) перемаркировки
            (date_relabing_fact) с учетом правила:
              - если дата 01.01.год → отображаемый год = год-1.
        - если есть и ожидаемый год модернизации, и годы из перемаркировок,
          берем максимальный год из всех.
        """
        from app.common.services.help_services import normalize_date_list, convert_to_date

        years: list[int] = []

        # 1) ожидаемые годы модернизации (с/без изменения мощности)
        if self.date_modernization_power_change_expected is not None:
            years.append(self.date_modernization_power_change_expected)
        if self.date_modernization_no_power_change_expected is not None:
            years.append(self.date_modernization_no_power_change_expected)

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

        # Карта мощностей по годам с учетом версии БД
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
        - если выбрана версия, берем только записи с этим database_version_id;
        - если версия не выбрана, берем только записи без версии (NULL).
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
        Берем со станции (Station.id_regional_energy_system), при отсутствии — пытаемся получить через субъект РФ.

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


def _normalize_machine_key_part(value: str | None) -> str:
    """Номер: '01', '1', '001' -> '1' для стабильности между версиями."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if s.isdigit():
        return str(int(s))
    return s


# Варианты скобок: (), （）, []
_PAREN_PATTERN = re.compile(r"\s*[(\uff08\u005b][^)\uff09\u005d]*[)\uff09\u005d]\s*$")


def _normalize_machine_name_for_key(value: str | None) -> str:
    """
    Нормализация названия: убираем лишние пробелы и trailing часть в скобках.
    ПТ-60-130/13 и ПТ-60-130/13 (ПТ-80) считаются одинаковыми.
    Поддержка: (), （）, [].
    """
    if value is None:
        return ""
    s = " ".join(str(value).split())
    while True:
        s2 = _PAREN_PATTERN.sub("", s).strip()
        if s2 == s:
            break
        s = s2
    return s


def _make_new_machine_external_code() -> str:
    """
    Новый external_code должен быть постоянным идентификатором машины,
    а не функцией от изменяемых полей. Поэтому для genuinely new machine
    выдаём uuid4 один раз и потом больше его не пересчитываем.
    """
    return str(uuid.uuid4())


def _resolve_station_external_code_for_machine(connection, target) -> str:
    station_code = None
    if target.machine_station and hasattr(target.machine_station, 'external_code'):
        station_code = target.machine_station.external_code
    elif target.id_station:
        result = connection.execute(
            sql_text(f"SELECT external_code FROM {SCHEMA_GENERATION}.gs_gen_stations WHERE id = :id"),
            {"id": target.id_station}
        )
        row = result.fetchone()
        if row:
            station_code = row[0]
    return (station_code or f"station_id_{target.id_station}").strip()


def _pick_single_external_code(rows) -> str | None:
    codes = [
        (row.external_code or "").strip()
        for row in rows
        if row.external_code and str(row.external_code).strip()
    ]
    if not codes:
        return None
    distinct_codes = set(codes)
    if len(distinct_codes) == 1:
        return next(iter(distinct_codes))
    return None


def _find_existing_machine_external_code_by_id_ti(connection, target) -> str | None:
    if getattr(target, "id_ti", None) is None:
        return None
    rows = connection.execute(
        sql_text(
            f"""
            SELECT m.external_code
            FROM {SCHEMA_GENERATION}.gs_gen_machines m
            WHERE m.id_ti = :id_ti
              AND trim(COALESCE(m.external_code, '')) <> ''
            """
        ),
        {"id_ti": target.id_ti},
    ).fetchall()
    return _pick_single_external_code(rows)


def _find_existing_machine_external_code_by_signature(
    connection,
    *,
    station_external_code: str,
    machine_number: str,
    machine_name: str,
    date_exploitation,
) -> str | None:
    if not station_external_code or not machine_number:
        return None

    params = {
        "station_external_code": station_external_code,
        "machine_number": machine_number,
        "machine_name": machine_name,
        "date_exploitation": date_exploitation,
    }
    rows = connection.execute(
        sql_text(
            f"""
            SELECT m.external_code
            FROM {SCHEMA_GENERATION}.gs_gen_machines m
            JOIN {SCHEMA_GENERATION}.gs_gen_stations s ON s.id = m.id_station
            WHERE trim(COALESCE(m.external_code, '')) <> ''
              AND trim(COALESCE(s.external_code, '')) = :station_external_code
              AND trim(COALESCE(m.machine_number, '')) = :machine_number
              AND trim(COALESCE(m.machine_name, '')) = :machine_name
              AND (
                    (m.date_exploitation IS NULL AND :date_exploitation IS NULL)
                    OR m.date_exploitation = :date_exploitation
                  )
            """
        ),
        params,
    ).fetchall()
    return _pick_single_external_code(rows)


def _find_existing_machine_external_code(connection, target) -> str | None:
    """
    Возвращает уже существующий external_code для логически той же машины.

    Приоритет:
    1. По id_ti, если он есть и однозначен.
    2. По жёсткой сигнатуре внутри семейства станции:
       station.external_code + machine_number + machine_name + date_exploitation.

    Если однозначного матча нет, считаем машину genuinely new и генерируем
    новый UUID, не зависящий от изменяемых бизнес-полей.
    """
    by_id_ti = _find_existing_machine_external_code_by_id_ti(connection, target)
    if by_id_ti:
        return by_id_ti

    station_external_code = _resolve_station_external_code_for_machine(connection, target)
    return _find_existing_machine_external_code_by_signature(
        connection,
        station_external_code=station_external_code,
        machine_number=" ".join(str(getattr(target, "machine_number", None) or "").split()),
        machine_name=" ".join(str(getattr(target, "machine_name", None) or "").split()),
        date_exploitation=getattr(target, "date_exploitation", None),
    )


@event.listens_for(Machine, 'before_insert')
def generate_external_code_before_insert(mapper, connection, target):
    """
    Генерирует/наследует external_code для агрегата перед вставкой записи.

    external_code больше не должен пересчитываться из текущих параметров машины:
    это постоянный identity-key логического агрегата между версиями БД.
    Поэтому при вставке сначала пытаемся найти уже существующий код семейства,
    а если машины ещё нигде нет — выдаём новый UUID один раз.
    """
    if target.external_code:
        return

    existing_external_code = _find_existing_machine_external_code(connection, target)
    if existing_external_code:
        target.external_code = existing_external_code
        return

    target.external_code = _make_new_machine_external_code()
