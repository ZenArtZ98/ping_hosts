from sqlalchemy import create_engine, Column, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./hosts.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class HostDB(Base):
    __tablename__ = "hosts"
    id = Column(String, primary_key=True, index=True)
    ip = Column(String, unique=True, index=True)
    last_ping = Column(Float, nullable=True)
    delivered_pct = Column(Float, nullable=True)
    lost_pct = Column(Float, nullable=True)
    last_success = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)
