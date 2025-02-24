from app import db

# Модель для видов топлива
class FuelType(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'fuel_types'

    # id типа вида топлива
    id = db.Column(db.Integer, primary_key=True)

    # наименование вида топлива
    name = db.Column(db.String(80), unique=True, nullable=False)

    # связь с таблицей "Типы топлива"
    fuels = db.relationship(
        'Fuel', 
        back_populates='fuel_type')

# Модель для типов топлива
class Fuel(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'fuels'

    # id типа топлива
    id = db.Column(db.Integer, primary_key=True)
    
    # наименование типа топлива
    name = db.Column(db.String(80), unique=True, nullable=False)
    
    # id вида топлива
    id_fuel_type = db.Column(
        db.Integer, 
        db.ForeignKey('fuel_types.id', ondelete='RESTRICT'), 
        nullable=True)
    fuel_type = db.relationship(
        'FuelType', 
        back_populates='fuels')
    
    # связь с таблицей топлив агрегатов электростанции
    machine_fuels = db.relationship(
        'MachineFuel', 
        back_populates='fuel')
    


# Модель для категории топлива
class FuelCategory(db.Model):
     # название таблицы в базе данных
    __tablename__ = 'fuel_categories'

    # id категории топлива
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # наименование категории топлива
    name = db.Column(db.String(80), unique=True, nullable=False)
