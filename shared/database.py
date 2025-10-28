from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

_engine = None
_SessionLocal = None

Base = declarative_base()

def get_engine():
    """Retorna o engine global, criando-o se não existir."""
    global _engine
    if _engine is None:
        # Pega a URL *agora*, não no import
        SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")
        if SQLALCHEMY_DATABASE_URL is None:
            raise ValueError("SQLALCHEMY_DATABASE_URL não está definida. Verifique seu arquivo .env")

        _engine = create_engine(SQLALCHEMY_DATABASE_URL)
    return _engine

def get_session_local():
    """Retorna o SessionLocal global, criando-o se não existir."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine() # Garante que o engine seja criado primeiro
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal
