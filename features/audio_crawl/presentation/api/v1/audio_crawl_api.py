from typing import List, Optional, Annotated, Any, Sequence
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, status, Query, HTTPException, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from features.audio_crawl.domain.entities.audio_crawl import AudioCrawl as AudioCrawlEntity
from features.audio_crawl.app.use_cases.create_audio_crawl import CreateAudioCrawlUseCase
from features.audio_crawl.app.use_cases.get_audio_crawl import GetAudioCrawlUseCase
from features.audio_crawl.app.use_cases.list_audio_crawl import ListAudioCrawlUseCase
from features.audio_crawl.app.use_cases.update_audio_crawl import UpdateAudioCrawlUseCase
from features.audio_crawl.app.use_cases.delete_audio_crawl import DeleteAudioCrawlUseCase
from app.dependencies import UoW, PasswordHasherDep, get_repo
from app.exceptions import NotFoundError, ConflictError, UnprocessableEntityError, BadRequestError
from infrastructure.repositories.audio_crawl_repository import AudioCrawlRepository
from infrastructure.repositories.base_repository import BaseRepositoryInterface
from celery.result import AsyncResult
from features.audio_crawl.tasks.tasks import task_crawler
# --- API Schemas ---
class AudioCrawlBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    audio_id: str
    video_platform: str
    platform_url: str
    audio_url: str
    duration: int
    lang: str
    title: str = None
    description: str
    tags: str = None    
    subtitle: str
    domain: str
    caption_downloaded: bool
    caption_url: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime
    is_deleted: bool
    created_at: datetime
    updated_at: Optional[datetime]

class AudioCrawlCreateRequestSchema(BaseModel):
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    is_deleted: Optional[bool] = None

class AudioCrawlUpdateRequestSchema(BaseModel):
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    is_deleted: Optional[bool] = None

# --- Repository Dependencies ---
AudioCrawlConcreteRepo = Annotated[AudioCrawlRepository, Depends(get_repo(AudioCrawlEntity))]
AudioCrawlInterfaceRepo = Annotated[BaseRepositoryInterface, Depends(get_repo(AudioCrawlEntity))]

# --- API Router ---
router = APIRouter(prefix="/audio_crawls", tags=["AudioCrawl"])

# --- Endpoints ---
@router.post("/", response_model=AudioCrawlBaseSchema, status_code=status.HTTP_201_CREATED)
async def create_audio_crawl(
    data: AudioCrawlCreateRequestSchema,
    repo: AudioCrawlConcreteRepo,
    uow: UoW,
    hasher: PasswordHasherDep
):
    try:
        use_case = CreateAudioCrawlUseCase(repo, uow, hasher) if False else CreateAudioCrawlUseCase(repo, uow)
        return await use_case.execute(data.model_dump())
    except (ConflictError, UnprocessableEntityError, BadRequestError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get("/{obj_id}", response_model=AudioCrawlBaseSchema)
async def get_audio_crawl(
    obj_id: UUID,
    repo: AudioCrawlInterfaceRepo,
):
    try:
        return await GetAudioCrawlUseCase(repo).execute(obj_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)

@router.get("/", response_model=Sequence[AudioCrawlBaseSchema])
async def list_audio_crawls(
    repo: AudioCrawlInterfaceRepo,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return await ListAudioCrawlUseCase(repo).execute(skip=skip, limit=limit)

@router.put("/{obj_id}", response_model=AudioCrawlBaseSchema)
async def update_audio_crawl(
    obj_id: UUID,
    data: AudioCrawlUpdateRequestSchema,
    repo: AudioCrawlConcreteRepo,
    uow: UoW,
):
    try:
        return await UpdateAudioCrawlUseCase(repo, uow).execute(obj_id, data.model_dump(exclude_unset=True))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)
    except (ConflictError, UnprocessableEntityError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.delete("/{obj_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audio_crawl(
    obj_id: UUID,
    repo: AudioCrawlInterfaceRepo,
    uow: UoW,
):
    try:
        await DeleteAudioCrawlUseCase(repo, uow).execute(obj_id)
        return None
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.detail)

@router.post("/tasks", status_code=201)
def run_task(payload = Body(...)):
    keyword = payload["keyword"]
    domain = payload["domain"]
    platform = payload["platform"]
    limit = payload["limit"]
    task = task_crawler.delay(keyword, domain, platform, limit)
    return JSONResponse({"task_id": task.id})


@router.get("/tasks/{task_id}")
def get_status(task_id):
    task_result = AsyncResult(task_id)
    result = {
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result
    }
    return JSONResponse(result)

@router.get("/celery/health")
def celery_health():
    insp = celery_app.control.inspect()

    stats = insp.stats()
    active = insp.active()
    registered = insp.registered()

    return {
        "stats": stats,
        "active": active,
        "registered_tasks": registered,
    }