from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from . import Base
from .admin import Admin as _  # noqa: F401, F811
from .guide import Guest as _  # noqa: F401, F811


class TelegramUser(Base):
    __tablename__ = "telegram_user"
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True, autoincrement=False)
    phone = Column(String)
    language = Column(String)
    guest_id = Column(Integer, ForeignKey("guest.id"))
    guest = relationship("Guest")
    admin_id = Column(Integer, ForeignKey("admin.id"))
    admin = relationship("Admin")
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
