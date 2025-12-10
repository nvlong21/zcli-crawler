from typing import Any, Sequence
from features.audio_crawl.domain.entities.audio_crawl import AudioCrawl
from infrastructure.repositories.base_repository import BaseRepositoryInterface

class ListAudioCrawlUseCase:
    def __init__(self, repository: BaseRepositoryInterface[Any, AudioCrawl]):
        self._repository = repository

    async def execute(self, skip: int = 0, limit: int = 100) -> Sequence[AudioCrawl]:
        return await self._repository.get_all(skip=skip, limit=limit)
