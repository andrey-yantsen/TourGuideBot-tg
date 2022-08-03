from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from . import Base
from .guide import Guest as _
from .admin import Admin as _


class TelegramUser(Base):
    __tablename__ = 'telegram_user'
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True, autoincrement=False)
    phone = Column(String)
    language = Column(String)
    guest_id = Column(Integer, ForeignKey('guest.id'))
    guest = relationship("Guest")
    admin_id = Column(Integer, ForeignKey('admin.id'))
    admin = relationship("Admin")
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
