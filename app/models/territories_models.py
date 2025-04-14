from app import db
from .energy_systems_models import regional_district_regional_energy_system


# Модель для федеральных округов
class FederalDistrict(db.Model):
    __tablename__ = 'federal_districts'

    # id федерального округа
    id = db.Column(db.Integer, primary_key=True)

    # наименование федерального округа (например, "Центральный ФО")
    name = db.Column(db.String(80), unique=True, nullable=False)

    # полное наименование федерального округа (например, "Центральный федеральный округ")
    name_full = db.Column(db.String(80), unique=True, nullable=True)

    # сокращенное наименование федерального округа (например, "ЦФО")
    name_abr = db.Column(db.String(80), unique=True, nullable=True)

    # связь с таблицей "Субъекты РФ"
    regional_districts = db.relationship(
        'RegionalDistrict', 
        back_populates='federal_district')
    
    def __repr__(self):
        return f"<FederalDistrict(id={self.id}, name={self.name})>"

    def __str__(self):
        return self.name


# Модель для субъекта РФ
class RegionalDistrict(db.Model):
    __tablename__ = 'regional_districts'

    # id субъекта РФ
    id = db.Column(db.Integer, primary_key=True)

    # наименование субъекта РФ (например, "Чукотский АО")
    name = db.Column(db.String(80), unique=True, nullable=False)

    # полное наименование субъекта округа (например, "Чукотский автономный округ")
    name_full = db.Column(db.String(80), unique=True, nullable=True)

    # id федерального округа (связь с таблицей "Федеральные округа")
    id_federal_district = db.Column(
        db.Integer, 
        db.ForeignKey('federal_districts.id', ondelete='RESTRICT'), 
        nullable=True)
    federal_district = db.relationship(
        'FederalDistrict', 
        back_populates='regional_districts')

    # связь с таблицей зависимостей "Субъект РФ - Региональная энергосистема"
    regional_energy_systems = db.relationship(
        "RegionalEnergySystem",
        secondary=regional_district_regional_energy_system,
        back_populates="regional_districts"
    )

    # связь с таблицей "Электростанции"
    stations = db.relationship(
        'Station', 
        back_populates='regional_district')
    
    # связь с таблицей "Энергорайоны""
    energy_areas = db.relationship(
        'EnergyArea',
        back_populates='regional_district',
        cascade='all, delete-orphan'
    )

    # связь с таблицей "Энергоузлы""
    energy_units = db.relationship(
        'EnergyUnit',
        back_populates='regional_district',
        cascade='all, delete-orphan'
    )