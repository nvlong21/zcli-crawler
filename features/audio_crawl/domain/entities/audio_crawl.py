# features/audio_crawl/domain/entities/audio_crawl.py
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict

class AudioCrawl(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    audio_id: Optional[str] = None
    video_platform: Optional[str] = None
    platform_url: Optional[str] = None
    audio_url: Optional[str] = None
    duration: Optional[int] = None
    lang: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str]    
    tags: Optional[str] = None
    subtitle: Optional[str] = None
    domain: Optional[str] = None
    caption_downloaded: Optional[bool] = None
    caption_url: Optional[str] = None
    deleted_at: Optional[datetime] = None
    is_deleted: Optional[bool] = None
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")