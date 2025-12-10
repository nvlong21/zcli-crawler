from typing import Any
from uuid import UUID
from features.audio_crawl.domain.entities.audio_crawl import AudioCrawl
from infrastructure.repositories.base_repository import BaseRepositoryInterface
from app.exceptions import NotFoundError

class GetAudioCrawlUseCase:
    def __init__(self, repository: BaseRepositoryInterface[Any, AudioCrawl]):
        self._repository = repository

    async def execute(self, obj_id: UUID) -> AudioCrawl:
        result = await self._repository.get_by_audio_id(obj_id)
        if not result:
            raise NotFoundError("AudioCrawl not found.")
        return result
    
