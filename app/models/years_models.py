from app import db
from app.models.stations_models import machine_power_year_association, machine_fuel_year_association, machine_tes_type_year_association

# Модель для признаков года
class YearFeature(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'year_features'
    
    # id признака года
    id = db.Column(db.Integer, primary_key=True)

    # наименование признака года
    name = db.Column(db.String(80), unique=True, nullable=False)

    # связь с таблицей "Годы"
    years = db.relationship('Year', back_populates='year_feature')


# Модель для года
class Year(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'years'
    
    # id года
    id = db.Column(db.Integer, primary_key=True)

    # год
    number = db.Column(db.Integer, unique=True, nullable=False, index=True)    
      
    # id признака года
    id_year_feature = db.Column(db.Integer, db.ForeignKey('year_features.id', ondelete='RESTRICT'), nullable=True)
    year_feature = db.relationship('YearFeature', back_populates='years')

    # связь с таблицей "Мощность агрегатов электростанций"
    machine_powers = db.relationship(
        'MachinePower', 
        secondary=machine_power_year_association,
        back_populates='years'
    )

    # связь с таблицей "Топливо агрегатов электростанций"
    machine_fuels = db.relationship(
        'MachineFuel',
        secondary=machine_fuel_year_association,
        back_populates='years'
    )

    machine_tes_types = db.relationship(
        'MachineTesType',
        secondary=machine_tes_type_year_association,
        back_populates='years'
    )