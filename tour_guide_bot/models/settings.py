import enum
from sqlalchemy import Column, String, DateTime, func, Enum
from . import Base


class Key(enum.Enum):
    welcome_message = 1


class Settings(Base):
    __tablename__ = 'settings'
    __mapper_args__ = {"eager_defaults": True}

    key = Column(Enum(Key), primary_key=True)
    language = Column(String)
    value = Column(String, nullable=False)
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
