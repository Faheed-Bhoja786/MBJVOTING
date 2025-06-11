from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from flask_sqlalchemy import SQLAlchemy

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class Voter(db.Model):
    __tablename__ = 'voters'
    
    id = Column(Integer, primary_key=True)
    voter_id = Column(String(9), unique=True, nullable=False)
    voted_at = Column(DateTime, default=func.now())
    party = Column(String(50), nullable=True)
    
    def __repr__(self):
        return f'<Voter {self.voter_id}>'

class Vote(db.Model):
    __tablename__ = 'votes'
    
    id = Column(Integer, primary_key=True)
    party = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f'<Vote for {self.party}>'

class Admin(db.Model):
    __tablename__ = 'admins'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    
    def __repr__(self):
        return f'<Admin {self.username}>'
        
class ElectionStatus(db.Model):
    __tablename__ = 'election_status'
    
    id = Column(Integer, primary_key=True)
    is_open = Column(Boolean, default=True)
    message = Column(Text, nullable=True)
    countdown_end = Column(DateTime, nullable=True)
    winner = Column(String(50), nullable=True)
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f'<ElectionStatus open={self.is_open}>'