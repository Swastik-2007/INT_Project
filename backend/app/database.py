import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.declarative import declarative_base

BASE_DIR = Path(__file__).resolve().parent.parent

# Only load .env if DATABASE_URL is not pre-configured in environment (e.g. for test isolation)
if "DATABASE_URL" not in os.environ:
    load_dotenv(BASE_DIR / ".." / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/lpu_wayfinder")

Base = declarative_base()
