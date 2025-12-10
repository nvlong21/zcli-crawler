from typing import Any
from infrastructure.crawler.crawler import AudioCrawler 
# -------------- application --------------
def create_application(
    **kwargs: Any,
) -> AudioCrawler:
    application = AudioCrawler(**kwargs)
    return application