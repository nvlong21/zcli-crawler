from typing import Dict, Any
from uuid import UUID
from features.audio_crawl.domain.entities.audio_crawl import AudioCrawl
from infrastructure.repositories.audio_crawl_repository import AudioCrawlRepository
from infrastructure.uow import AbstractUnitOfWork
from app.exceptions import NotFoundError, ConflictError, UnprocessableEntityError

class UpdateAudioCrawlUseCase:
    def __init__(self, repository: AudioCrawlRepository, uow: AbstractUnitOfWork):
        self._repository = repository; self._uow = uow

    async def execute(self, obj_id: UUID, update_data: Dict[str, Any]) -> AudioCrawl:
        # TODO: Add business logic and uniqueness checks for update data.
        # Example:
        # if 'name' in update_data:
        #     existing = await self._repository.find_by_name(update_data['name'])
        #     if existing and existing.id != obj_id:
        #         raise ConflictError("A audio_crawl with this name already exists.")
        
        obj_to_update = await self._repository.get_by_id(obj_id)
        if not obj_to_update:
            raise NotFoundError("AudioCrawl not found.")

        updated_data_dict = obj_to_update.model_dump()
        updated_data_dict.update(update_data)
        
        try:
            updated_entity = AudioCrawl(**updated_data_dict)
        except Exception as e:
            raise UnprocessableEntityError(f"Invalid update data: {e}")

        async with self._uow:
            result_entity = await self._repository.update(updated_entity)
            if result_entity is None:
                 raise NotFoundError("AudioCrawl not found during update process.")
            await self._uow.commit()
            return result_entity
