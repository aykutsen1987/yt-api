import logging
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from pydantic import BaseModel, HttpUrl
import uuid
import os

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube MP3 API",
    description="YouTube videolarını MP3'e dönüştürme ve ses stream URL'si alma API'si.",
    version="3.0.0",
)

# --- Models ---
class VideoInfo(BaseModel):
    title: str
    thumbnail: str
    duration: int
    stream_url: HttpUrl

# --- Filename sanitize ---
def sanitize_filename(title: str) -> str:
    sanitized = re.sub(r'[\\/*?:"<>|]', "", title)
    return sanitized[:100]

# --- Extract Audio Info ---
def get_audio_info(url: str):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise Exception("YouTube boş yanıt verdi.")

        # Stream URL bul
        audio_formats = [
            f for f in info["formats"]
            if f.get("acodec") != "none" and f.get("vcodec") == "none"
        ]

        if not audio_formats:
            raise Exception("Uygun ses formatı bulunamadı.")

        stream_url = audio_formats[-1]["url"]

        return {
            "title": info.get("title", ""),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration", 0),
            "stream_url": stream_url
        }

    except Exception as e:
        logger.error(f"Hata: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Video bilgileri alınamadı: {e}"
        )


# --- /info endpoint ---
@app.get("/info", response_model=VideoInfo)
def info(url: HttpUrl = Query(...)):
    data = get_audio_info(str(url))
    return VideoInfo(
        title=data["title"],
        thumbnail=data["thumbnail"],
        duration=data["duration"],
        stream_url=data["stream_url"]
    )


# --- /mp3 download endpoint ---
@app.get("/mp3")
def mp3(url: HttpUrl = Query(...)):
    file_id = f"{uuid.uuid4()}.mp3"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": file_id,
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([str(url)])

        return FileResponse(
            file_id,
            media_type="audio/mpeg",
            filename="audio.mp3"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"MP3 oluşturulamadı: {e}"
        )


@app.get("/")
def root():
    return {"status": "OK", "message": "YouTube MP3 API çalışıyor."}
