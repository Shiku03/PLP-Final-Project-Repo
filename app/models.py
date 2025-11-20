from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import func
from database import Base

class User(Base):
    __tablename__='users'

    id=Column(Integer, primary_key=True, index=True)
    fullname=Column(String(100), nullable=False)
    username=Column(String(50), unique=True, nullable=False)
    email=Column(String(100), unique=True, nullable=False)
    password=Column(String(128), nullable=False)
    created_at=Column(DateTime(timezone=True), server_default=func.now())
    updated_at=Column(DateTime(timezone=True), onupdate=func.now())