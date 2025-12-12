import os
import uuid
import shutil
import psutil
import yt_dlp
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from datetime import datetime

app = FastAPI(title="YT-to-MP3 API", version="1.0")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Model ----------
class YouTubeRequest(BaseModel):
    url: HttpUrl

# ---------- MP3 Output Directory ----------
OUTPUT_DIR = "/tmp/mp3_files"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------- MP3 DÖNÜŞTÜRME ----------
def convert_to_mp3(url: str):
    """
    YouTube videosunu indirir → MP3'e dönüştürür → dosya yolunu döndürür.
    """

    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, "%(title)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        "nocheckcertificate": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    title = info.get("title", f"yt-{uuid.uuid4()}")
    mp3_file = None

    # Temp klasördeki MP3 dosyasını bul
    for f in os.listdir(temp_dir):
        if f.endswith(".mp3"):
            mp3_file = os.path.join(temp_dir, f)

    if not mp3_file:
        raise HTTPException(status_code=500, detail="MP3 dosyası üretilemedi.")

    # Kalıcı klasöre taşı
    final_name = f"{uuid.uuid4()}.mp3"
    final_path = os.path.join(OUTPUT_DIR, final_name)
    shutil.move(mp3_file, final_path)

    shutil.rmtree(temp_dir)

    return title, final_name, final_path, info.get("duration", 0)


# ---------- ENDPOINT ----------
@app.post("/api/mp3")
async def create_mp3(req: YouTubeRequest):
    title, filename, filepath, duration = convert_to_mp3(req.url)

    base_url = os.getenv("RENDER_EXTERNAL_URL", "")
    file_url = f"{base_url}/files/{filename}"

    return {
        "status": "success",
        "title": title,
        "duration": duration,
        "mp3_url": file_url
    }


# ---------- DOSYA SERVİSİ ----------
@app.get("/files/{filename}")
async def serve_mp3(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")

    return FileResponse(file_path, media_type="audio/mpeg")


# ---------- HEALTH ----------
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "cpu": psutil.cpu_percent(interval=0.5),
        "memory": psutil.virtual_memory().percent,
        "timestamp": datetime.utcnow().isoformat()
    }
