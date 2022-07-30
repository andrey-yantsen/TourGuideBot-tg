import enum
from sqlalchemy import Column, Index, Integer, String, DateTime, func, Enum
from . import Base


class SettingsKey(enum.Enum):
    guide_welcome_message = 1


class Settings(Base):
    __tablename__ = 'settings'
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    key = Column(Enum(SettingsKey), nullable=False)
    language = Column(String)
    value = Column(String, nullable=False)
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('ix_settings_key_language', 'key', 'language', unique=True),
    )
