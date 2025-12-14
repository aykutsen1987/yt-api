from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import os
import uuid
import asyncio
import subprocess
import json

from youtube_search import YoutubeSearch
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
AWS_S3_BASE_URL = os.getenv("AWS_S3_BASE_URL", "https://your-s3.com/")

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
    parts = list(map(int, duration.split(":")))
    if len(parts) == 3:
        return parts[0]*3600 + parts[1]*60 + parts[2]
    if len(parts) == 2:
        return parts[0]*60 + parts[1]
    return parts[0] if parts else 0

# --------------------------------------------------
# CONVERSION TASK
# --------------------------------------------------
async def run_conversion(video_url: str, job_id: str, title: str):
    JOB_STATUS[job_id] = {"status": "PROCESSING", "progress": 0}

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
async def search_with_api(query: str, key: str) -> List[Track]:
    youtube = build(API_SERVICE_NAME, API_VERSION, developerKey=key)

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

async def search_with_scraper(query: str) -> List[Track]:
    def _search():
        return YoutubeSearch(query, max_results=10).to_json()

    raw = await asyncio.to_thread(_search)
    data = json.loads(raw).get("videos", [])

    results = []
    for ite
