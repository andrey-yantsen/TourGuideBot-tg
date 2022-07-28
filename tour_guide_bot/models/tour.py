from sqlalchemy import Column, ForeignKey, Integer, SmallInteger, DateTime, String, func
from sqlalchemy.orm import relationship, object_session
from tour_guide_bot.models import Base


class Tour(Base):
    __tablename__ = 'tour'
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    translation = relationship("TourTranslation", back_populates="tour")
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    def sections(self, language):
        return object_session(self).query(TourSection).with_parent(TourTranslation).filter(TourTranslation.language == language).all


class TourTranslation(Base):
    __tablename__ = 'tour_translation'
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    language = Column(String, nullable=False)
    tour_id = Column(Integer, ForeignKey("tour.id"), nullable=False)
    title = Column(String, nullable=False)
    tour = relationship("Tour", back_populates="translation")
    section = relationship("TourSection")
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class TourSection(Base):
    __tablename__ = 'tour_section'
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    tour_translation_id = Column(Integer, ForeignKey("tour_translation.id"), nullable=False)
    position = Column(SmallInteger, nullable=False)
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
