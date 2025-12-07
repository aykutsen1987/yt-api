import os
import tempfile
import logging
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from pydantic import BaseModel, HttpUrl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Ses API",
    description="YouTube videolarını dinlemek veya indirmek için API.",
    version="2.0.0",
)

# -------------------------------------------------------
# COOKIES — 10 parçayı birleştir
# -------------------------------------------------------
def load_cookie_from_parts():
    parts = []
    for i in range(1, 11):
        part = os.getenv(f"YTDLP_COOKIES_{i}", "")
        if part:
            parts.append(part)

    cookies_joined = "".join(parts)

    if not cookies_joined.strip():
        return None

    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', suffix='.txt') as f:
            f.write(cookies_joined)
            return f.name
    except Exception as e:
        logger.error(f"Cookie dosyası oluşturulamadı: {e}")
        return None


# -------------------------------------------------------
# Pydantic Model
# -------------------------------------------------------
class VideoInfo(BaseModel):
    title: str
    thumbnail: str
    duration: int
    stream_url: HttpUrl


# -------------------------------------------------------
# Yardımcı Fonksiyon
# -------------------------------------------------------
def sanitize_filename(title: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", title)[:100]


def get_audio_url(video_url: str):
    cookie_file = load_cookie_from_parts()

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "cookiefile": cookie_file,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

            if not info:
                raise DownloadError("Boş veri alındı.")

            audio_formats = [
                f for f in info.get("formats", [])
                if f.get("acodec") != "none" and f.get("vcodec") == "none"
            ]

            if audio_formats:
                audio_url = audio_formats[-1]["url"]
            else:
                audio_url = info.get("url")

            if not audio_url:
                raise DownloadError("Ses linki bulunamadı.")

            return {
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration", 0),
                "audio_url": audio_url
            }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Video bilgileri alınamadı: {e}")


# -------------------------------------------------------
# ENDPOINTS
# -------------------------------------------------------
@app.get("/info", response_model=VideoInfo)
def info(url: HttpUrl = Query(...)):
    data = get_audio_url(str(url))
    return VideoInfo(
        title=data["title"],
        thumbnail=data["thumbnail"],
        duration=data["duration"],
        stream_url=data["audio_url"]
    )


@app.get("/download", response_class=RedirectResponse)
def download(url: HttpUrl = Query(...)):
    data = get_audio_url(str(url))
    filename = sanitize_filename(data["title"]) + ".mp3"
    return RedirectResponse(data["audio_url"])


@app.get("/")
def root():
    return {"message": "YouTube MP3 API çalışıyor."}
