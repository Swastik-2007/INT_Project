from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .database import DATABASE_URL, Base

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

