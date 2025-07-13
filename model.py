from database import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.String, primary_key=True)  # Clerk user ID
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    projects = db.relationship('Project', backref='user', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(10), nullable=False)  # 'lost' or 'found'
    category = db.Column(db.String(20))  # 'human', 'animal', 'plant'
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    image_url = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String, db.ForeignKey('user.id'))

    likes = db.relationship('Like', backref='project', lazy=True)
    comments = db.relationship('Comment', backref='project', lazy=True)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('user.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    __table_args__ = (db.UniqueConstraint('user_id', 'project_id', name='unique_like'),)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String, db.ForeignKey('user.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
