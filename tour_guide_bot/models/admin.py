import enum
from sqlalchemy import Column, Integer, String, DateTime, func, Enum
from . import Base


class AdminPermissions(enum.Enum):
    full = 1


class Admin(Base):
    __tablename__ = 'admin'
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    phone = Column(String, index=True, unique=True, nullable=False)
    permissions = Column(Enum(AdminPermissions))
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
