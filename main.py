from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import yt_dlp
import os

app = FastAPI(title="Mp3DMeta API", version="2.0.0")

# -------------------------------
# CORS
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# MODELLER
# -------------------------------
class SearchResultItem(BaseModel):
    id: str
    title: str
    channel: str
    thumbnail: str
    url: str
    durationSeconds: int
    source: str = "youtube"   # youtube | server | cc
    downloadable: bool = False

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]

# -------------------------------
# YT-DLP (SADECE BİLGİ + STREAM)
# -------------------------------
YDL_OPTS_INFO = {
    "quiet": True,
    "skip_download": True,
    "format": "bestaudio/best",
}

def get_video_info(url: str):
    with yt_dlp.YoutubeDL(YDL_OPTS_INFO) as ydl:
        return ydl.extract_info(url, download=False)

# -------------------------------
# ENDPOINTS
# -------------------------------

@app.get("/search", response_model=SearchResponse)
async def search(query: str = Query(..., min_length=1)):
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS_INFO) as ydl:
            info = ydl.extract_info(f"ytsearch10:{query}", download=False)

        results = []
        for entry in info.get("entries", []):
            results.append(
                SearchResultItem(
                    id=entry["id"],
                    title=entry["title"],
                    channel=entry.get("uploader", ""),
                    thumbnail=entry.get("thumbnail", ""),
                    url=f"https://www.youtube.com/watch?v={entry['id']}",
                    durationSeconds=entry.get("duration", 0),
                    source="youtube",
                    downloadable=False  # 🔴 YouTube için DAİMA false
                )
            )

        return SearchResponse(query=query, results=results)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stream")
async def stream(videoUrl: str):
    """
    YouTube → SADECE stream URL döner
    """
    info = get_video_info(videoUrl)

    formats = info.get("formats", [])
    for f in formats:
        if f.get("vcodec") == "none" and f.get("acodec") != "none":
            return {
                "streamUrl": f["url"],
                "duration": info.get("duration", 0),
                "source": "youtube",
                "downloadable": False
            }

    raise HTTPException(status_code=404, detail="Audio stream not found")


@app.get("/duration")
async def duration(videoUrl: str):
    info = get_video_info(videoUrl)
    return {"duration": info.get("duration", 0)}
