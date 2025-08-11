from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from config import SCHEMA_AUTH

# Модель для ролей пользователей
class Role(db.Model):
    __tablename__ = 'roles'
    __table_args__ = {"schema": SCHEMA_AUTH}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


user_roles = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey(f'{SCHEMA_AUTH}.users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey(f'{SCHEMA_AUTH}.roles.id'), primary_key=True),
    schema=SCHEMA_AUTH
)


# Модель для пользователя
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    __table_args__ = {"schema": SCHEMA_AUTH}
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    roles = db.relationship('Role', secondary=user_roles, backref='users')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def role_names(self):
        return [role.name for role in self.roles]
