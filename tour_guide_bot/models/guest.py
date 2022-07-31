from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from . import Base
from .tour import Tour as _


class BoughtTours(Base):
    __tablename__ = 'bought_tours'
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    guest_id = Column(Integer, ForeignKey("guest.id"), nullable=False, index=True)
    guest = relationship("Guest")
    tour_id = Column(Integer, ForeignKey("tour.id"), nullable=False)
    tour = relationship("Tour")
    is_user_notified = Column(Boolean, nullable=False, default=False, index=True)
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    expire_ts = Column(DateTime, nullable=False)


class Guest(Base):
    __tablename__ = 'guest'
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    phone = Column(String, index=True, unique=True, nullable=False)
    language = Column(String)
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
