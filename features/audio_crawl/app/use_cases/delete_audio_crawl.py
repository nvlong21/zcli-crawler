from typing import Any
from uuid import UUID
from infrastructure.repositories.base_repository import BaseRepositoryInterface
from infrastructure.uow import AbstractUnitOfWork
from app.exceptions import NotFoundError

class DeleteAudioCrawlUseCase:
    def __init__(self, repository: BaseRepositoryInterface[Any, Any], uow: AbstractUnitOfWork):
        self._repository = repository; self._uow = uow

    async def execute(self, obj_id: UUID) -> bool:
        async with self._uow:
            deleted = await self._repository.delete(obj_id)
            if not deleted:
                raise NotFoundError("AudioCrawl not found.")
            await self._uow.commit()
            return True
