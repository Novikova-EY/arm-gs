from app import db

# Модель для федеральных округов
class Fo(db.Model):
    __tablename__ = 'fo'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False)