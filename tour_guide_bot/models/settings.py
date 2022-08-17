import enum

from sqlalchemy import Column, DateTime, Enum, Index, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import Base


class SettingsKey(enum.Enum):
    guide_welcome_message = 1
    audio_to_voice = 2


class Settings(Base):
    __tablename__ = "settings"
    __mapper_args__ = {"eager_defaults": True}

    __bool_settings = [SettingsKey.audio_to_voice]

    # Global default is "empty means true"
    __bool_settings_defaults = {}

    id = Column(Integer, primary_key=True)
    key = Column(Enum(SettingsKey), nullable=False)
    language = Column(String)
    value = Column(String, nullable=False)
    created_ts = Column(DateTime, nullable=False, server_default=func.now())
    updated_ts = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_settings_key_language", "key", "language", unique=True),
    )

    @property
    def is_enabled(self) -> bool:
        if self.key not in self.__bool_settings:
            raise RuntimeError("This setting is not boolean")

        return self.value == "yes" or (
            self.value is None
            and self.__bool_settings_defaults.get(self.key, "yes") == "yes"
        )

    def enable(self) -> "Settings":
        if self.key not in self.__bool_settings:
            raise RuntimeError("This setting is not boolean")

        self.value = "yes"

        return self

    def disable(self) -> "Settings":
        if self.key not in self.__bool_settings:
            raise RuntimeError("This setting is not boolean")

        self.value = "no"

        return self

    @staticmethod
    async def load(
        db_session: AsyncSession, key: SettingsKey, language: str | None = None
    ) -> "Settings":
        stmt = select(Settings).where(
            (Settings.key == key) & (Settings.language == language)
        )
        setting = await db_session.scalar(stmt)
        if not setting:
            setting = Settings(key=key, language=language)

        return setting
