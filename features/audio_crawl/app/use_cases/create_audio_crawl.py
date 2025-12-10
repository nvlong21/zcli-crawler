from datetime import datetime
from typing import Dict, Any
from features.audio_crawl.domain.entities.audio_crawl import AudioCrawl
from infrastructure.repositories.audio_crawl_repository import AudioCrawlRepository
from infrastructure.uow import AbstractUnitOfWork
from app.exceptions import ConflictError, BadRequestError, UnprocessableEntityError

try: from infrastructure.utils.logging_config import logger
except ImportError: import logging; logger = logging.getLogger(__name__)

class CreateAudioCrawlUseCase:
    def __init__(self, repository: AudioCrawlRepository, uow: AbstractUnitOfWork):
        self._repository = repository
        self._uow = uow

    async def execute(self, create_data: Dict[str, Any]) -> AudioCrawl:
        logger.info(f"Executing CreateAudioCrawlUseCase")

        log_extra = {"feature": "audio_crawl", "data_keys": list(create_data.keys())}
        logger.info(f"Executing CreateAudioCrawlUseCase", extra=log_extra)

        # Validate Input & Create Domain Entity
        try:
            # Pydantic model handles initial validation.
            # Ensure ID generation strategy aligns (client vs DB). default_factory implies client-side.
            create_data['created_at'] = datetime.now()
            if 'updated_at' not in create_data:
                create_data['updated_at'] = None
            new_entity = AudioCrawl(**create_data)
            logger.debug(f"Domain entity for AudioCrawl created: {new_entity.id}", extra=log_extra)
        except Exception as e: # Catch Pydantic ValidationError, etc.
            logger.warning(f"Invalid data for creating AudioCrawl: {e}", extra=log_extra)
            raise UnprocessableEntityError(detail=f"Invalid data: {e}") from e

        async with self._uow:
            new_obj_entity = await self._repository.add(new_entity)
            await self._uow.commit()
            return new_obj_entity
