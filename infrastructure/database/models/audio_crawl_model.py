# infrastructure/database/models/audio_crawl_model.py
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, Integer, Float, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID as PythonUUID
from infrastructure.database.base_model import Base, UUIDType

class AudioCrawlModel(Base):
    __tablename__ = 'audio_crawls'
    id: Mapped[PythonUUID] = mapped_column(primary_key=True, default=PythonUUID, index=True)
    audio_id: Mapped[Optional[str]] = mapped_column(String, nullable=False)
    video_platform: Mapped[Optional[str]] = mapped_column(String, nullable=False)
    platform_url: Mapped[Optional[str]] = mapped_column(String, nullable=False)
    audio_url: Mapped[Optional[str]] = mapped_column(String, nullable=False)
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lang: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    caption_downloaded: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    caption_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_deleted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
