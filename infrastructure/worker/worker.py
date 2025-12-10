from celery import Celery
from app.config import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.task_default_queue = settings.CELERY_TASK_DEFAULT_QUEUE
# celery_app.conf.task_queues = settings.CELERY_TASK_QUEUES
# celery_app.autodiscover_tasks(["tasks"])
# celery_app.conf.update(CELERY_CONFIG)
