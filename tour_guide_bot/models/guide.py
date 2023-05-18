import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import object_session, relationship

from . import Base


class Tour(Base):
    __tablename__ = "tour"
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    translation = relationship(
        "TourTranslation", back_populates="tour", cascade="all, delete-orphan"
    )
    purchases = relationship(
        "Subscription", cascade="all, delete-orphan", back_populates="tour"
    )
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    def sections(self, language):
        return (
            object_session(self)
            .query(TourSection)
            .with_parent(TourTranslation)
            .filter(TourTranslation.language == language)
            .all
        )


class TourTranslation(Base):
    __tablename__ = "tour_translation"
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    language = Column(String, nullable=False)
    tour_id = Column(Integer, ForeignKey("tour.id"), nullable=False)
    title = Column(String, nullable=False)
    tour = relationship("Tour", back_populates="translation")
    section = relationship(
        "TourSection", cascade="all, delete-orphan", order_by="TourSection.position"
    )
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )


class MessageType(enum.Enum):
    text = 1
    location = 2
    audio = 3
    voice = 4
    video = 5
    video_note = 6
    photo = 7
    media_group = 8
    animation = 9


class TourSection(Base):
    __tablename__ = "tour_section"
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    tour_translation_id = Column(
        Integer, ForeignKey("tour_translation.id"), nullable=False
    )
    tour_translation = relationship("TourTranslation", back_populates="section")
    title = Column(String, nullable=False)
    position = Column(SmallInteger, nullable=False)
    content = relationship(
        "TourSectionContent",
        cascade="all, delete-orphan",
        order_by="TourSectionContent.position",
    )
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_tour_section_translation_id_position",
            "tour_translation_id",
            "position",
            unique=True,
        ),
    )


class TourSectionContent(Base):
    __tablename__ = "tour_section_content"
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    tour_section_id = Column(Integer, ForeignKey("tour_section.id"), nullable=False)
    tour_section = relationship("TourSection", back_populates="content")
    position = Column(SmallInteger, nullable=False)
    message_type = Column(Enum(MessageType), nullable=False)
    media_group_id = Column(String)
    content = Column(MutableDict.as_mutable(JSON), nullable=False)
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_tour_section_id_position", "tour_section_id", "position", unique=True
        ),
        Index(
            "ix_tour_section_content_secion_id_media_group",
            "tour_section_id",
            "message_type",
            "media_group_id",
            unique=True,
        ),
    )


class Subscription(Base):
    __tablename__ = "subscription"
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    guest_id = Column(Integer, ForeignKey("guest.id"), nullable=False, index=True)
    guest = relationship("Guest")
    tour_id = Column(Integer, ForeignKey("tour.id"), nullable=False)
    tour = relationship("Tour")
    is_user_notified = Column(Boolean, nullable=False, default=False, index=True)
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    expire_ts = Column(DateTime, nullable=False)


class Guest(Base):
    __tablename__ = "guest"
    __mapper_args__ = {"eager_defaults": True}

    id = Column(Integer, primary_key=True)
    phone = Column(String, index=True, unique=True, nullable=False)
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
