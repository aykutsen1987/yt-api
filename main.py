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
    parts = duration.split(":")
    try:
        parts = list(map(int, parts))
    except ValueError:
        return 0

    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
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

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            check=True
        )

        results: List[Track] = []

        for line in result.stdout.splitlines():
            data = json.loads(line)

            results.append(Track(
                id=data["id"],
                title=data["title"],
                artist=data.get("uploader", "Unknown"),
                channel=data.get("uploader", "Unknown"),
                thumbnailUrl=data["thumbnail"],
                videoUrl=data["webpage_url"],
                duration=int(data.get("duration", 0)),
                hasCopyright=False
            ))

        return results

    except Exception:
        return []

# --------------------------------------------------
# ENDPOINTS
# --------------------------------------------------
@app.get("/api/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=3)):
    # 1) API FIRST
    for key in API_KEYS:
        try:
            return SearchResponse(
                results=await search_with_api(q, key)
            )
        except Exception:
            continue

    # 2) yt-dlp SCRAPER FALLBACK
    results = await search_with_yt_dlp(q)
    if not results:
        raise HTTPException(503, "Search service unavailable")

    return SearchResponse(results=results)

@app.post("/api/convert/start", response_model=ConvertResponse)
async def start_convert(track: Track):
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
