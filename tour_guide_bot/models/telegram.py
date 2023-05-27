from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, relationship

from . import Base
from .admin import Admin
from .guide import Guest


class TelegramUser(Base):
    __tablename__ = "telegram_user"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=False)
    phone: Mapped[Optional[str]] = Column(String)
    language: Mapped[Optional[str]] = Column(String)
    guest_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("guest.id"))
    guest: Mapped[Optional[Guest]] = relationship("Guest")
    admin_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("admin.id"))
    admin: Mapped[Optional[Admin]] = relationship("Admin")
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
