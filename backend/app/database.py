import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.declarative import declarative_base

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".." / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/lpu_wayfinder")

Base = declarative_base()
