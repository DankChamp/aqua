from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from aqua.config import load_config

config = load_config()
engine = create_engine(f"sqlite:///{config['db_path']}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
