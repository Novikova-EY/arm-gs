from app.extensions import db
from config import SCHEMA_GENERATION


# Модель для котла электростанции
class Boiler(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'boilers'
    __table_args__ = {"schema": SCHEMA_GENERATION}
    
    # id котла
    id = db.Column(db.Integer, primary_key=True)

    # наименование котла
    name = db.Column(db.String(80), unique=True, nullable=False)

    # id электростанции
    id_station = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_GENERATION}.stations.id', ondelete='RESTRICT'), nullable=True)
    boiler_station = db.relationship(
        'Station', 
        back_populates='boilers')