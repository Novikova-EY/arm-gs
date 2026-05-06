# -*- coding: utf-8 -*-
"""
PGUMachine model (Компонент ПГУ).
- Сохранены все исходные связи и индексы, включая каскады к родительской Machine.
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin

class PGUMachine(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = 'gs_gen_pgu_machines'
    __table_args__ = (
        Index('ix_pgu_machine_id_parent_machine', 'id_parent_machine'),
        Index('ix_pgu_machine_id_tes_machine_type', 'id_tes_machine_type'),
        Index('ix_pgu_machine_id_condition_type', 'id_condition_type'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_ti = db.Column(db.Integer, nullable=True)

    # FK -> ConditionType
    id_condition_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_condition_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    condition_type = db.relationship('ConditionType', back_populates='pgu_machines')

    # FK -> Machine (родитель)
    id_parent_machine = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.gs_gen_machines.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    parent_machine = db.relationship('Machine', backref=db.backref('pgu_submachines', cascade='all, delete-orphan'))

    machine_number = db.Column(db.String(80), nullable=True, index=True)
    machine_name = db.Column(db.String(1024), nullable=False, index=True)

    # FK -> TesMachineType
    id_tes_machine_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_tes_machine_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    tes_machine_type = db.relationship('TesMachineType', backref='pgu_machines')

    # FK -> PGUTesMachineType (ГТ/ПТ)
    id_pgu_tes_machine_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_pgu_tes_machine_types.id'),
        nullable=True,
        index=True,
    )
    pgu_tes_machine_type = db.relationship('PGUTesMachineType', back_populates='pgu_machines')

    # Children: powers
    pgu_machine_powers = db.relationship(
        'PGUMachinePower',
        back_populates='pgu_machine',
        cascade="all, delete-orphan",
        foreign_keys='PGUMachinePower.id_pgu_machine',
    )

    # Children: names by year (аналог Machine.machine_names)
    pgu_machine_names = db.relationship(
        'PGUMachineName',
        back_populates='pgu_machine_name_rel',
        cascade="all, delete-orphan",
        foreign_keys='PGUMachineName.id_pgu_machine',
    )

    # Даты/поля как в machine_model (165-202)
    # фактический год ввода в эксплуатацию
    date_exploitation = db.Column(db.Integer, nullable=True)
    # фактический год ввода в работу
    date_commission_year = db.Column(db.Integer, nullable=True)
    # ожидаемый год ввода в эксплуатацию
    date_exploitation_expected = db.Column(db.Integer, nullable=True)
    date_commission_fact = db.Column(db.String(10), nullable=True)
    date_joining_expected = db.Column(db.String(10), nullable=True)
    date_joining_fact = db.Column(db.String(10), nullable=True)
    date_detatchment_fact = db.Column(db.String(10), nullable=True)
    date_decompressing_expected = db.Column(db.Integer, nullable=True)
    date_decompressing_fact = db.Column(db.String(10), nullable=True)
    date_modernization_power_change_expected = db.Column(
        "date_modernization_power_change_expected", db.Integer, nullable=True
    )
    date_modernization_no_power_change_expected = db.Column(
        "date_modernization_no_power_change_expected", db.Integer, nullable=True
    )

    # Поля могут содержать несколько дат в текстовом формате
    date_relabing_fact = db.Column(db.String(255), nullable=True)
    date_update_fact = db.Column(db.String(255), nullable=True)
    note = db.Column(db.String(512), nullable=True)

    # Документ-основание для изменения параметров агрегата
    change_document = db.Column(db.Text, nullable=True)
    year_modern = db.Column(db.String(10), nullable=True)
    year_demontaz = db.Column(db.String(10), nullable=True)
    resurs_gas = db.Column(db.String(10), nullable=True)

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<PGUMachine id={self.id} name={self.machine_name!r} parent_id={self.id_parent_machine}>"

    @property
    def commission_display(self) -> str | int | None:
        """
        Отображаемое значение для колонки 'Ввод в работу' на station_list:
        - фактический год ввода в работу (date_commission_year), если указан;
        - иначе ожидаемый год ввода в эксплуатацию (date_exploitation_expected).
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
        либо date_decompressing_expected, либо год из date_decompressing_fact (01.01.год → год-1).
        """
        from app.common.services.help_services import convert_to_date

        if self.date_decompressing_fact:
            dt = convert_to_date(self.date_decompressing_fact)
            if dt is not None:
                if dt.month == 1 and dt.day == 1:
                    return dt.year - 1
                return dt.year
        if self.date_decompressing_expected is not None:
            return self.date_decompressing_expected
        return None

    @property
    def modernization_display(self) -> str | None:
        """
        Отображаемое значение для колонки 'Модерн.' на station_list.

        Берем максимальный год из:
        - ожидаемой модернизации с изменением мощности (date_modernization_power_change_expected);
        - ожидаемой модернизации без изменения мощности (date_modernization_no_power_change_expected);
        - фактических дат перемаркировки (date_relabing_fact) по правилу 01.01.(Y+1) -> Y.
        """
        from app.common.services.help_services import normalize_date_list, convert_to_date

        years: list[int] = []

        if self.date_modernization_power_change_expected is not None:
            years.append(self.date_modernization_power_change_expected)
        if self.date_modernization_no_power_change_expected is not None:
            years.append(self.date_modernization_no_power_change_expected)

        if self.date_relabing_fact:
            normalized = normalize_date_list(self.date_relabing_fact)
            if normalized:
                tokens = [t.strip() for t in normalized.split(",") if t.strip()]
                for token in tokens:
                    dt = convert_to_date(token)
                    if dt is None:
                        continue
                    display_year = dt.year - 1 if dt.month == 1 and dt.day == 1 else dt.year
                    years.append(display_year)

        if not years:
            return None

        return str(max(years))

    @property
    def modernization_power_change_display(self) -> str | None:
        """
        Год для колонки «Модерн. с изм. мощ-ти» на station_list (ПГУ):
        только модернизация с изменением мощности и фактические даты перемаркировки,
        без date_modernization_no_power_change_expected.
        """
        from app.common.services.help_services import normalize_date_list, convert_to_date

        years: list[int] = []

        if self.date_modernization_power_change_expected is not None:
            years.append(self.date_modernization_power_change_expected)

        if self.date_relabing_fact:
            normalized = normalize_date_list(self.date_relabing_fact)
            if normalized:
                tokens = [t.strip() for t in normalized.split(",") if t.strip()]
                for token in tokens:
                    dt = convert_to_date(token)
                    if dt is None:
                        continue
                    display_year = dt.year - 1 if dt.month == 1 and dt.day == 1 else dt.year
                    years.append(display_year)

        if not years:
            return None

        return str(max(years))
