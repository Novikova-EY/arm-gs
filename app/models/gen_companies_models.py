from app import db

# Модель для генерирующей компании
class GenCompany(db.Model):
    __tablename__ = 'gen_companies'
    
    # id федерального генерирующей компании
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # наименование генерирующей компании
    name = db.Column(db.String(80), unique=True, nullable=False)

    # связь с таблицей "Агрегаты станции"
    machines = db.relationship('Machine', back_populates='gen_company')