import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()  # load environment variables from .env file
DATABASE_URL = os.getenv("DATABASE_URL",None)

if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER", "username")
    DB_PASS = os.getenv("DB_PASS", "password")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "GenEd")
    # ensure charset utf8mb4 for emoji/utf8 support
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# engine and session setup
engine=create_engine(DATABASE_URL)

SessionLocal=sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base=declarative_base()