from app import db

# Модель для субъекта РФ
class Region(db.Model):
    __tablename__ = 'region'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    id_fo = db.Column(db.Integer, db.ForeignKey('fo.id'), nullable=True)
    fo = db.relationship('Fo', backref='region')