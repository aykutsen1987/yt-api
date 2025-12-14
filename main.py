from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import yt_dlp
import asyncio

app = FastAPI()

# CORS ayarı (Android + Web için)
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
    artist: Optional[str] = ""
    channel: str
    thumbnail: str
    url: str
    durationSeconds: int
    hasCopyright: bool = False

class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    query: str

class ConversionResponse(BaseModel):
    success: bool
    mp3Url: Optional[str] = None
    message: Optional[str] = None

# -------------------------------
# YT-DLP AYARLARI
# -------------------------------
YDL_OPTS_INFO = {
    "quiet": True,
    "skip_download": True,
    "format": "bestaudio/best",
}

YDL_OPTS_MP3 = {
    "format": "bestaudio/best",
    "outtmpl": "/tmp/%(id)s.%(ext)s",
    "quiet": True,
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
}

# -------------------------------
# HELPERS
# -------------------------------
def get_video_info(url: str):
    with yt_dlp.YoutubeDL(YDL_OPTS_INFO) as ydl:
        info = ydl.extract_info(url, download=False)
    return info

# -------------------------------
# ENDPOINTLER
# -------------------------------

@app.get("/search", response_model=SearchResponse)
async def search(query: str = Query(..., min_length=1)):
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS_INFO) as ydl:
            search_url = f"ytsearch10:{query}"
            info = ydl.extract_info(search_url, download=False)
            results = []
            for entry in info['entries']:
                results.append(
                    SearchResultItem(
                        id=entry.get('id'),
                        title=entry.get('title'),
                        artist=entry.get('uploader'),
                        channel=entry.get('uploader'),
                        thumbnail=entry.get('thumbnail'),
                        url=f"https://www.youtube.com/watch?v={entry.get('id')}",
                        durationSeconds=entry.get('duration') or 0,
                        hasCopyright=False  # opsiyonel, telif kontrol eklenebilir
                    )
                )
        return SearchResponse(results=results, query=query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream")
async def get_stream_url(videoUrl: str):
    """
    15dk altı → direkt audio stream URL
    15dk üstü → async dönüş linki
    """
    info = get_video_info(videoUrl)
    duration = info.get('duration', 0)
    if duration > 15*60:
        return {"mp3Url": f"/convert?videoUrl={videoUrl}", "message": "Video uzun, dönüşüm async"}
    
    formats = info.get('formats', [])
    audio_url = None
    for f in formats:
        if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
            audio_url = f.get('url')
            break
    if not audio_url:
        raise HTTPException(status_code=404, detail="Audio stream not found")
    return {"mp3Url": audio_url, "duration": duration}

@app.get("/convert", response_model=ConversionResponse)
async def convert_to_mp3(videoUrl: str):
    """
    15dk üstü videolar için mp3 dönüşümü
    """
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(YDL_OPTS_MP3).download([videoUrl]))
        video_id = videoUrl.split("v=")[-1]
        mp3_file = f"/tmp/{video_id}.mp3"
        return ConversionResponse(success=True, mp3Url=mp3_file)
    except Exception as e:
        return ConversionResponse(success=False, message=str(e))

@app.get("/duration")
async def get_duration(videoUrl: str):
    info = get_video_info(videoUrl)
    return {"duration": info.get('duration', 0)}

@app.get("/copyright")
async def check_copyright(videoId: str):
    # Opsiyonel telif kontrolü
    return {"hasCopyright": False}
