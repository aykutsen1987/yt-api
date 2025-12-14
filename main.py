from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import os
import uuid
import asyncio
import subprocess

from googleapiclient.discovery import build
from youtubesearchpython import VideosSearch
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------
# APP
# --------------------------------------------------
app = FastAPI(
    title="Mp3DMeta Hybrid Backend API",
    version="1.0.0"
)

# In-memory job tracking (prod'da Redis önerilir)
JOB_STATUS: Dict[str, Dict] = {}

# --------------------------------------------------
# API KEY POOL
# --------------------------------------------------
def get_api_keys():
    keys = []
    for i in range(1, 11):
        k = os.getenv(f"YOUTUBE_API_KEY_{i}")
        if k:
            keys.append(k)

    if not keys:
        single = os.getenv("YOUTUBE_API_KEY")
        if single:
            keys.append(single)

    return keys

API_KEYS = get_api_keys()
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

AWS_S3_BASE_URL = os.getenv(
    "AWS_S3_BASE_URL",
    "https://your-s3-bucket.example/"
)

# --------------------------------------------------
# MODELS
# --------------------------------------------------
class Track(BaseModel):
    id: str
    title: str
    artist: str
    channel: str
    thumbnailUrl: str
    videoUrl: str
    duration: int
    hasCopyright: bool = False

class SearchResponse(BaseModel):
    results: List[Track]

class ConvertResponse(BaseModel):
    jobId: str
    message: str

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def parse_duration(duration: str) -> int:
    """
    '1:02:30' -> seconds
    """
    parts = duration.split(":")
    try:
        parts = list(map(int, parts))
    except ValueError:
        return 0

    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 1:
        return parts[0]
    return 0

# --------------------------------------------------
# CONVERSION TASK
# --------------------------------------------------
async def run_conversion(video_url: str, job_id: str, title: str):
    JOB_STATUS[job_id] = {
        "status": "PROCESSING",
        "progress": 0,
        "title": title
    }

    output_template = f"/tmp/{job_id}.%(ext)s"

    command = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--no-progress",
        "-o", output_template,
        video_url
    ]

    try:
        await asyncio.to_thread(
            subprocess.run,
            command,
            check=True,
            capture_output=True,
            text=True
        )

        # Burada S3 upload yapılabilir (boto3)
        download_url = f"{AWS_S3_BASE_URL}{job_id}.mp3"

        JOB_STATUS[job_id] = {
            "status": "COMPLETED",
            "progress": 100,
            "downloadUrl": download_url
        }

    except subprocess.CalledProcessError as e:
        JOB_STATUS[job_id] = {
            "status": "FAILED",
            "error": e.stderr
        }

# --------------------------------------------------
# SEARCH METHODS
# --------------------------------------------------
async def search_with_api(query: str, api_key: str) -> List[Track]:
    youtube = build(
        API_SERVICE_NAME,
        API_VERSION,
        developerKey=api_key
    )

    request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=10
    )

    response = await asyncio.to_thread(request.execute)

    results: List[Track] = []

    for item in response.get("items", []):
        video_id = item["id"]["videoId"]

        results.append(Track(
            id=video_id,
            title=item["snippet"]["title"],
            artist=item["snippet"]["channelTitle"],
            channel=item["snippet"]["channelTitle"],
            thumbnailUrl=item["snippet"]["thumbnails"]["default"]["url"],
            videoUrl=f"https://www.youtube.com/watch?v={video_id}",
            duration=300,  # Basitlik için sabit
            hasCopyright=False
        ))

    return results

async def search_with_scraper(query: str) -> List[Track]:
    def _search():
        return VideosSearch(query, limit=10).result()

    data = await asyncio.to_thread(_search)
    videos = data.get("result", [])

    results: List[Track] = []

    for v in videos:
        duration_str = v.get("duration", "0:00")

        results.append(Track(
            id=v["id"],
            title=v["title"],
            artist=v.get("channel", {}).get("name", "Unknown"),
            channel=v.get("channel", {}).get("name", "Unknown"),
            thumbnailUrl=v["thumbnails"][0]["url"],
            videoUrl=v["link"],
            duration=parse_duration(duration_str),
            hasCopyright=False
        ))

    return results

# --------------------------------------------------
# ENDPOINTS
# --------------------------------------------------
@app.get("/api/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=3)):
    # 1) API KEY POOL
    for key in API_KEYS:
        try:
            return SearchResponse(
                results=await search_with_api(q, key)
            )
        except Exception:
            continue

    # 2) SCRAPER FALLBACK
    try:
        return SearchResponse(
            results=await search_with_scraper(q)
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Search service unavailable"
        )

@app.post("/api/convert/start", response_model=ConvertResponse)
async def start_convert(track: Track):
    # 15 dk altı -> mobil
    if track.duration < 900:
        raise HTTPException(
            status_code=400,
            detail="Bu video mobil cihazda (FFmpegKit) işlenmelidir."
        )

    job_id = str(uuid.uuid4())
    asyncio.create_task(
        run_conversion(track.videoUrl, job_id, track.title)
    )

    return ConvertResponse(
        jobId=job_id,
        message="Conversion started"
    )

@app.get("/api/convert/status")
def convert_status(jobId: str):
    if jobId not in JOB_STATUS:
        raise HTTPException(404, "Job not found")
    return JOB_STATUS[jobId]

@app.get("/api/copyright-check")
def copyright_check(videoId: str):
    return {"hasCopyright": False}
