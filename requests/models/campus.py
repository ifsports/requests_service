from sqlalchemy import Column, String

from shared.database import Base

class Campus(Base):
    __tablename__ = "campus"

    code: str = Column(String, primary_key=True)