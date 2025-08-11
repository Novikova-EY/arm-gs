from app.extensions import db
from config import SCHEMA_REFDATA

# Модель для признаков года
class YearFeature(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'year_features'
    __table_args__ = {"schema": SCHEMA_REFDATA}

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
    __table_args__ = {"schema": SCHEMA_REFDATA}

    # id года
    id = db.Column(db.Integer, primary_key=True)

    # год
    number = db.Column(db.Integer, unique=True, nullable=False, index=True)    
      
    # id признака года
    id_year_feature = db.Column(db.Integer, db.ForeignKey(f'{SCHEMA_REFDATA}.year_features.id', ondelete='RESTRICT'), nullable=True)
    year_feature = db.relationship('YearFeature', back_populates='years')

    # Связь с `StationPower`
    station_powers = db.relationship('StationPower', back_populates='year')

    # Связь с `MachinePower`
    machine_powers = db.relationship('MachinePower', back_populates='year')

    # Связь с `MachineFuel`
    machine_fuels = db.relationship('MachineFuel', back_populates='year')

    # Связь с `MachineTesType`
    machine_tes_types = db.relationship('MachineTesType', back_populates='year', lazy='subquery')