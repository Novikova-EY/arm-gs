# -*- coding: utf-8 -*-
"""
Параметры распределения (аналог таблицы «Параметры-распределения» из Access).
"""
from sqlalchemy.sql import func

from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class DistributionParameter(db.Model):
    __tablename__ = "gs_fue_distribution_parameters"
    __table_args__ = {"schema": SCHEMA_FUEL}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Объединенная энергосистема
    id_union_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_union_energy_systems.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    union_energy_system = db.relationship(
        "UnionEnergySystem",
        foreign_keys=[id_union_energy_system],
    )

    # Расчетный год (id_year)
    id_year = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_years.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    year = db.relationship("Year", foreign_keys=[id_year])

    # Базовый год
    id_base_year = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_years.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    base_year = db.relationship("Year", foreign_keys=[id_base_year])

    # Текст фильтра / можно потому удалить
    filter_text = db.Column(db.Text, nullable=True)

    # Выработка ТЭС
    e = db.Column(db.Numeric(36, 16), nullable=True)

    # Верхняя граница коэффициента загрузки (k+)
    kplus = db.Column(db.Numeric(36, 16), nullable=True)
    # Нижняя граница коэффициента загрузки (k−)
    kmin = db.Column(db.Numeric(36, 16), nullable=True)
    
    # Коэффициент загрузки
    k = db.Column(db.Numeric(36, 16), nullable=True)

    # Вспомогательный номер территоррии для распределения выработки по станциям ОЭС
    bkl = db.Column(db.Numeric(36, 16), nullable=True)

    # Коэффициент загрузки нового оборудования (расчётный)
    kn = db.Column(db.Numeric(36, 16), nullable=True)

    # Коэффициент загрузки нового паросилового оборудования (расчётный)
    knps = db.Column(db.Numeric(36, 16), nullable=True)

    # Коэффициент загрузки нового газотурбинного оборудования (расчётный)
    kngt = db.Column(db.Numeric(36, 16), nullable=True)

    # Коэффициент загрузки нового парогазового оборудования (расчётный)
    knpg = db.Column(db.Numeric(36, 16), nullable=True)

    # ЧЧИУМ нового паросилового оборудования
    hnps = db.Column(db.Numeric(36, 16), nullable=True)

    # ЧЧИУМ нового газотурбинного оборудования
    hngt = db.Column(db.Numeric(36, 16), nullable=True)

    # ЧЧИУМ нового парогазового оборудования
    hnpg = db.Column(db.Numeric(36, 16), nullable=True)

    # Наименование таблицы с обобщенными показателями по станциям
    wname = db.Column(db.String(255), nullable=True)

    # Наименование таблицы с удельными технико-экономическими показателями работы групп оборудования
    uname = db.Column(db.String(255), nullable=True)

    # Название таблицы со структурой топливного баланса групп оборудования
    toplname = db.Column(db.String(255), nullable=True)

    # Наименование таблицы с детализацией видов топлива
    dopname = db.Column(db.String(255), nullable=True)
    
    # Порядковый номер
    numb = db.Column(db.Numeric(36, 16), nullable=True)

    # Коэффициент допустимого отклонения
    doptim = db.Column(db.Numeric(36, 16), nullable=True)

    # Наличие ограничений по выработке для РЭС
    lim = db.Column(db.Integer, nullable=True)

    # Общий ключ копий одной логической строки во всех версиях БД
    ref_uuid = db.Column(db.String(36), nullable=True, index=True)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Подписи колонок списка /fuel/distribution_parameters — совпадают с комментариями к полям выше.
DISTRIBUTION_PARAMETER_LIST_COLUMN_HEADINGS: list[tuple[str, str]] = [
    ("name", "Объединенная энергосистема"),
    ("byear", "Базовый год"),
    ("year", "Расчетный год"),
    ("e", "Выработка ТЭС"),
    ("doptim", "Коэффициент допустимого отклонения"),
    ("k", "Коэффициент загрузки"),
    ("kn", "Коэффициент загрузки нового оборудования (расчётный)"),
    ("knps", "Коэффициент загрузки нового паросилового оборудования (расчётный)"),
    ("kngt", "Коэффициент загрузки нового газотурбинного оборудования (расчётный)"),
    ("knpg", "Коэффициент загрузки нового парогазового оборудования (расчётный)"),
    ("hnps", "ЧЧИУМ нового паросилового оборудования"),
    ("hngt", "ЧЧИУМ нового газотурбинного оборудования"),
    ("hnpg", "ЧЧИУМ нового парогазового оборудования"),
    ("lim", "Наличие ограничений по выработке для РЭС"),
    ("numb", "Порядковый номер"),
    ("bkl", "Вспомогательный номер территоррии для распределения выработки по станциям ОЭС"),
]

DISTRIBUTION_PARAMETER_FIELD_LABELS = dict(DISTRIBUTION_PARAMETER_LIST_COLUMN_HEADINGS)
