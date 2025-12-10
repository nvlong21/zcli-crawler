# infrastructure/repositories/audio_crawl_repository.py
from typing import Type, Optional
from features.audio_crawl.domain.entities.audio_crawl import AudioCrawl as AudioCrawlEntity
from infrastructure.database.models.audio_crawl_model import AudioCrawlModel
from infrastructure.repositories.base_repository import BaseRepository
from sqlalchemy import select

class AudioCrawlRepository(BaseRepository[AudioCrawlModel, AudioCrawlEntity]):
    @property
    def model_class(self) -> Type[AudioCrawlModel]:
        return AudioCrawlModel

    @property
    def entity_class(self) -> Type[AudioCrawlEntity]:
        return AudioCrawlEntity
    async def get_by_audio_id(self, audio_id: str) -> Optional[AudioCrawlEntity]:
        stmt = select(self.model_class).where(self.model_class.audio_id == audio_id)
        if self._is_async:
            result = await self._db.execute(stmt) # type: ignore
            model = result.scalars().first()
        else:
             model = self._db.scalars(stmt).first() # type: ignore
        
        if model:
            return AudioCrawlEntity.from_orm(model)
        return None
    
    # TODO: Thêm các phương thức truy vấn tùy chỉnh ở đây nếu cần. Ví dụ:
    # async def find_by_name(self, name: str) -> Optional[AudioCrawlEntity]:
    #     ...
