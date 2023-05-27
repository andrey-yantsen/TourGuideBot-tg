import enum

from sqlalchemy import Column, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped

from . import Base


class AdminPermissions(enum.Enum):
    full = 1


class Admin(Base):
    __tablename__ = "admin"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = Column(Integer, primary_key=True)
    phone: Mapped[str] = Column(String, index=True, unique=True, nullable=False)
    permissions: Mapped[AdminPermissions] = Column(
        Enum(AdminPermissions), nullable=False
    )
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
