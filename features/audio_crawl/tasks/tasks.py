from infrastructure.worker.worker import celery_app
from infrastructure.crawler import create_application
import time
import asyncio
@celery_app.task(name="task_crawler")
def task_crawler(keyword, domain, platform, limit):
    time.sleep(1)
    app = create_application()
    if platform=="youtube":
        videoEntries = app.youtube_search(f"{keyword} {domain}", limit)
        uniqueIds = app.filter_duplicate(videoEntries)
        app.download_and_upload_audio(uniqueIds)
    return True 