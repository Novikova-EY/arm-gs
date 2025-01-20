from app import db

# Модель для типов ОЭС
class OesType(db.Model):
    __tablename__ = 'oes_type'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

# Модель для ОЭС
class Oes(db.Model):
    __tablename__ = 'oes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    id_oes_type = db.Column(db.Integer, db.ForeignKey('oes_type.id'), nullable=True)

    oes_type = db.relationship('OesType', backref='oes_type')

    def __init__(self, name, id_oes_type=None):
        self.name = name
        self.id_oes_type = id_oes_type

