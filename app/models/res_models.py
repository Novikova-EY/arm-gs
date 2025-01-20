from app import db

# Модель для региональной ЭС
class Res(db.Model):
    __tablename__ = 'res'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    id_oes = db.Column(db.Integer, db.ForeignKey('oes.id'), nullable=True)

    oes = db.relationship('Oes', backref='related_res')
    regions = db.relationship('ResRegion', back_populates='res', cascade='all, delete-orphan', lazy='dynamic')

    def __init__(self, name, id_oes=None):
        self.name = name
        self.id_oes = id_oes

class ResRegion(db.Model):
    __tablename__ = 'res_region'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_res = db.Column(db.Integer, db.ForeignKey('res.id'), nullable=False)
    id_region = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=False)

    res = db.relationship('Res', back_populates='regions')
    region = db.relationship('Region')

    def __init__(self, id_res, id_region):
        self.id_res = id_res
        self.id_region = id_region