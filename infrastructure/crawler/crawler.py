import os
import json
from pathlib import Path
import tqdm
from datetime import datetime
import time
import shutil
from sqlalchemy import select
from functools import partial
from glob import glob
import yt_dlp as youtube_dl
from pydub import AudioSegment
from youtube_transcript_api import YouTubeTranscriptApi, Transcript
from youtube_transcript_api._errors import NoTranscriptFound
from app.config import settings
from app.dependencies import DefaultSessionDep
from features.audio_crawl.domain.entities.audio_crawl import AudioCrawl
from infrastructure.database.models.audio_crawl_model import AudioCrawlModel
from infrastructure.repositories.audio_crawl_repository import AudioCrawlRepository
from infrastructure.S3.s3 import get_s3_client
import time
import boto3
def split_with_caption(audio_path, skip_idx=0, out_ext="wav") -> list:
    df = pd.read_csv(audio_path.split('wavs')[0] + 'text/subtitle.csv')
    filename = os.path.basename(audio_path).split('.', 1)[0]

    audio = read_audio(audio_path)
    df2 = df[df['id'].apply(str) == filename]
    df2['end'] = round((df2['start'] + df2['duration']) * 1000).astype(int)
    df2['start'] = round(df2['start'] * 1000).astype(int)
    edges = df2[['start', 'end']].values.tolist()

    audio_paths = []
    for idx, (start_idx, end_idx) in enumerate(edges[skip_idx:]):
        start_idx = max(0, start_idx)

        target_audio_path = "{}/{}.{:04d}.{}".format(
            os.path.dirname(audio_path), filename, idx, out_ext)

        segment = audio[start_idx:end_idx]

        segment.export(target_audio_path, "wav")  # for soundsegment

        audio_paths.append(target_audio_path)

    return audio_paths

def read_audio(audio_path):
    return AudioSegment.from_file(audio_path)


import asyncio

class YtDlpProcessor:
    def __init__(self, loop, local_session):
        self.loop = loop          # event loop của app/celery
        self.local_session = local_session          # async repository
        self.s3 = boto3.client(
            "s3",
            # endpoint_url=settings.S3_ENDPOOINT,
            aws_access_key_id=settings.S3_ACCESSKEY,
            aws_secret_access_key=settings.S3_SECRETKEY,
            region_name=settings.S3_REGION
        )    
    async def async_post_hook(self, data):
        print(f"Status: {data["status"]}")
        if data["status"] != "finished":
            print(data["status"])
            return
        time.sleep(3)
        info = data.get("info_dict", {})
        local_path=data["filename"]
        local_path=f"{local_path.split(".")[0]}.{settings.PREFER_RED_CODEC}"
        filename = str(local_path).split("/")[-1]
        s3_prefix = os.path.join("", filename)
        print("uploaded to S3")
        self.s3.upload_file(
            Filename=str(local_path),
            Bucket=settings.S3_BUCKETNAME,
            Key=filename
        )
        print("uploaded to S3 done")
        audio_url = os.path.join(s3_prefix,filename )
        # Tạo session mới cho mỗi callback
        async with self.local_session() as session:
            repo = AudioCrawlRepository(session)
            model = AudioCrawl(
                audio_id=info["id"],
                video_platform=info["extractor"],
                platform_url=info["webpage_url"],
                audio_url=audio_url,
                duration=info["duration"],
                description=info["description"],
                lang=info["language"],
                title=info["title"],
                tags = ",".join(info["tags"]),
                subtitle=info["subtitle"],
                domain=",".join(info["categories"]),
            )            
            await repo.add(model) 

        # session.add(model)

        # await self.session.commit()
        # await self.session.refresh(model)

        # self.session.add(model)
        # await self.session.commit()
        # await self.session.refresh(model)        

        # with open("data.json", "w", encoding="utf-8") as f:
        #     json.dump(d, f, ensure_ascii=False, indent=4)                

    def post_hook(self, data):
        """Hook sync do yt-dlp gọi → chuyển sang async"""
        print(f"Status: {data["status"]}")
        if data["status"] != "finished":
            print(data["status"])
            return
        info = data.get("info_dict", {})
        local_path=info["filepath"]
        local_path=f"{local_path.split(".")[0]}.{settings.PREFER_RED_CODEC}"
        filename = str(local_path).split("/")[-1]
        s3_prefix = os.path.join("", filename)
        print("uploaded to S3")
        self.s3.upload_file(
            Filename=str(local_path),
            Bucket=settings.S3_BUCKETNAME,
            Key=filename
        )
        print("uploaded to S3 done")
        audio_url = os.path.join(s3_prefix,filename)
        session = next(DefaultSessionDep())
        repo = AudioCrawlRepository(session)
        model = AudioCrawl(
            audio_id=info["id"],
            video_platform=info["extractor"],
            platform_url=info["webpage_url"],
            audio_url=audio_url,
            duration=info["duration"],
            description=info["description"],
            lang=info["language"],
            title=info["title"],
            tags = ",".join(info["tags"]),
            subtitle="",
            domain=",".join(info["categories"]),
        )            
        repo.add(model)
        # asyncio.run_coroutine_threadsafe(
        #     self.async_post_hook(data),
        #     self.loop,
        # )
class AudioCrawler:
    def __init__(self):
        # Delete directory if existing
        if os.path.exists(settings.DATA_DIR):
            shutil.rmtree(settings.DATA_DIR, ignore_errors=True)
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        self.lang = "en"

    def youtube_search(self, query: str, max_results: int = 20, upload_after: str = '', upload_before: str = ''):
        ydl_opts = {
            "format": "ba/best",
            'quiet': True,
            'skip_download': True, 
        }
        _upload_after = datetime.strptime("19700101", "%Y%m%d")
        _upload_before = datetime.now()
        query_str = f"ytsearch{max_results}:{query}"
        now = int(time.time())
        _videoEntries = []
        if len(upload_after)==8:
            _upload_after = datetime.strptime(upload_after, "%Y%m%d")
        if len(upload_before)==8:
            _upload_before = datetime.strptime(upload_before, "%Y%m%d")

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(query_str, download=False)
        for v in result.get("entries", []):
            if v.get("live_status") in ("is_live", "is_upcoming"):
                continue     
            upload_date = v.get("upload_date")

            if not upload_date and v.get("timestamp"):
                d = datetime.utcfromtimestamp(v["timestamp"])
            elif upload_date:
                d = datetime.strptime(upload_date, "%Y%m%d")
            else:
                continue
            if d < _upload_after or d > _upload_before:
                continue
            print(f"{d.date()} | {v['title']}")
            v["platform"]= v["extractor"]
            _videoEntries.append(v)
            
        return _videoEntries

    def filter_duplicate(self, _videos: list[dict]):
        db = next(DefaultSessionDep())
        _vidIds = [v['id'] for v in _videos]
        try:
            _existingRows = db.query(AudioCrawlModel.audio_id).filter(AudioCrawlModel.audio_id.in_(_vidIds)).all()
            _existingIds = {row[0] for row in _existingRows}
            _uniqueVideos = [v for v in _videos if v['id'] not in _existingIds]
            return _uniqueVideos
        finally:
            db.close()
    def bilibili_search(keyword, max_results=5, out_dir="audio"):
        ydl_opts = {
            "format": "ba/best",
            "quiet": False,
            # "default_search": "bilisearch",  # yt-dlp builtin search Bilibili
            "skip_download": True, 
            # 'extract_flat': True,  # chỉ lấy metadata, không load streams
        }
        query_str = f"bilisearch1:{keyword}"
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            # yt-dlp sẽ search và download audio
            result = ydl.extract_info(query_str, download=False)
            with open("data.json", "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)                
        # print(result)
    # Example

    def download_and_upload_audio(self, entries) -> None:
        if os.path.exists(os.path.join(settings.DATA_DIR, "wavs/")):
            shutil.rmtree(os.path.join(settings.DATA_DIR, "wavs/"))        
        download_path = os.path.join(settings.DATA_DIR, "wavs/" + '%(id)s.%(ext)s')
        print("tao folder:  ", os.path.join(settings.DATA_DIR, "wavs/"))
        os.makedirs(os.path.join(settings.DATA_DIR, "wavs/"), exist_ok=True) 
        # loop = asyncio.get_running_loop()
        processor = YtDlpProcessor(None, DefaultSessionDep)
        # youtube_dl options
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': settings.PREFER_RED_CODEC,
                'preferredquality': '192'
            }],
            'postprocessors_args': [
                '-ar', '21000'
            ],
            'prefer_ffmpeg': True,
            'keepvideo': False,
            'outtmpl': download_path,  # 다운로드 경로 설정
            'ignoreerrors': True,
            "postprocessor_hooks": [processor.post_hook],
        }

        urls:list[str] = []
        
        for v in entries:
            video_data = {
                "title": v.get("title"),
                "url": v.get("webpage_url"),
                "duration": v.get("duration"),
                "id": v.get("id")
            }
            urls.append(v.get("webpage_url"))
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download(urls)
            # await asyncio.to_thread(
            #     lambda: youtube_dl.YoutubeDL(ydl_opts).download(urls)
            # )    
        except Exception as e:
            print('error', e)
        #         print("Uploaded:", s3_key)
        #         try:
        #             db = next(get_db())
    #                 audio =  AudioCraw(
    # audio_id = _audioID,
    # video_platform: Mapped[str] = mapped_column(String, nullable=True, default=None)
    # platform_url: Mapped[str] = mapped_column(String, nullable=False, default= "")
    # audio_url: Mapped[str] = mapped_column(String, nullable=True, default= "")
    # duration: Mapped[int] = mapped_column(Integer, nullable=True, default= "")
    # lang: Mapped[str] = mapped_column(String, nullable=True, default= "")
    # subtitle: Mapped[str] = mapped_column(String, nullable=True, default= "")
    # domain: Mapped[str] = mapped_column(String, nullable=True, default= "")
    # caption_downloaded: Mapped[bool] = mapped_column(default=False)
    # caption_url: Mapped[str] = mapped_column(String, nullable=True, default= "")    
    # created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default_factory=lambda: datetime.now(UTC))
    # updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)    
    # deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # is_deleted: Mapped[bool] = mapped_column(default=False, index=True) 
                    # db.add(video)
                #     db.commit()
                # finally:
                #     db.close()

    def download_captions(self, priority_manually_created=True) -> None:
        lang = self.lang
        text = []
        wav_dir = os.path.join(settings.DATA_DIR, "wavs")
        file_list = os.listdir(wav_dir)
        file_list_wav = [file for file in file_list if file.endswith(".wav")]
        ytt_api = YouTubeTranscriptApi()
        for f in tqdm.tqdm(file_list_wav):
            transcript = Transcript("",0,
                "",
                None,
                None,
                True,
                [],)
            try:
                video = f.split(".wav")[0]
                transcript_list = ytt_api.list(video)
                if priority_manually_created:                  
                    try:
                        transcript = transcript_list.find_manually_created_transcript([lang])
                    except NoTranscriptFound:
                        msg = "Find generated transcript video {} because it has no manually generated subtitles"
                        print(msg.format(video))
                if transcript.language is None:
                    transcript = transcript_list.find_generated_transcript([lang])
                subtitle = transcript.fetch()
                for snippet in subtitle:
                    print(snippet.text)
                    print(snippet.start)    
                    print(snippet.duration)
            except Exception as e:
                print("error:", e)
            print(text)

        # print(os.path.basename(self.output_dir) + ' channel was finished')
    def audio_split(self, parallel=False) -> None:
        base_dir = self.output_dir + '/wavs/*.wav'
        audio_paths = glob(base_dir)
        audio_paths.sort()
        fn = partial(split_with_caption)
        parallel_run(fn, audio_paths, desc="Split with caption", parallel=parallel)