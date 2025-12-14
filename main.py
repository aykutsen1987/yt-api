from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import os
import uuid
import asyncio
import subprocess
import json

from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------
# APP
# --------------------------------------------------
app = FastAPI(
    title="Mp3DMeta Hybrid Backend API",
    version="1.0.0"
)

JOB_STATUS: Dict[str, Dict] = {}

# --------------------------------------------------
# API KEY POOL
# --------------------------------------------------
def get_api_keys():
    keys = []
    for i in range(1, 11):
        key = os.getenv(f"YOUTUBE_API_KEY_{i}")
        if key:
            keys.append(key)

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
def parse_duration(seconds) -> int:
    try:
        return int(seconds)
    except Exception:
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

        JOB_STATUS[job_id] = {
            "status": "COMPLETED",
            "progress": 100,
            "downloadUrl": f"{AWS_S3_BASE_URL}{job_id}.mp3"
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

    results = []

    for item in response.get("items", []):
        vid = item["id"]["videoId"]

        results.append(Track(
            id=vid,
            title=item["snippet"]["title"],
            artist=item["snippet"]["channelTitle"],
            channel=item["snippet"]["channelTitle"],
            thumbnailUrl=item["snippet"]["thumbnails"]["default"]["url"],
            videoUrl=f"https://www.youtube.com/watch?v={vid}",
            duration=300,
            hasCopyright=False
        ))

    return results

async def search_with_yt_dlp(query: str) -> List[Track]:
    command = [
        "yt-dlp",
        f"ytsearch10:{query}",
        "--dump-json",
        "--skip-download"
    ]

    result = await asyncio.to_thread(
        subprocess.run,
        command,
        capture_output=True,
        text=True
    )

    results = []

    for line in result.stdout.splitlines():
        try:
            data = json.loads(line)
            results.append(Track(
                id=data["id"],
                title=data["title"],
                artist=data.get("uploader", "Unknown"),
                channel=data.get("uploader", "Unknown"),
                thumbnailUrl=data.get("thumbnail", ""),
                videoUrl=data.get("webpage_url", ""),
                duration=parse_duration(data.get("duration", 0)),
                hasCopyright=False
            ))
        except Exception:
            continue

    return results

# --------------------------------------------------
# ENDPOINTS
# --------------------------------------------------
@app.get("/api/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=3)):
    # 1️⃣ API
    for key in API_KEYS:
        try:
            return SearchResponse(
                results=await search_with_api(q, key)
            )
        except Exception:
            continue

    # 2️⃣ yt-dlp fallback
    results = await search_with_yt_dlp(q)
    if not results:
        raise HTTPException(503, "Search service unavailable")

    return SearchResponse(results=results)

@app.post("/api/convert/start", response_model=ConvertResponse)
async def start_convert(track: Track):
    if track.duration < 900:
        raise HTTPException(
            status_code=400,
            detail="Bu video mobil cihazda işlenmelidir."
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
