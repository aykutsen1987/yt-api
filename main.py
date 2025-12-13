import os
import uuid
import shutil
import tempfile
import yt_dlp

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# =========================
# FASTAPI APP
# =========================
app = FastAPI(
    title="YouTube to MP3 API",
    version="2.2"
)

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# REQUEST MODEL
# =========================
class YouTubeRequest(BaseModel):
    url: str

# =========================
# OUTPUT DIRECTORY
# =========================
OUTPUT_DIR = "/tmp/mp3"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =========================
# CORE FUNCTION
# =========================
def convert_to_mp3(youtube_url: str):
    temp_dir = tempfile.mkdtemp()

    try:
        # --- cookies.txt oluştur ---
        cookies_env = os.getenv("YT_COOKIES")
        cookies_path = None

        if cookies_env:
            cookies_path = os.path.join(temp_dir, "cookies.txt")
            with open(cookies_path, "w", encoding="utf-8") as f:
                f.write(cookies_env)

        output_template = os.path.join(temp_dir, "%(id)s.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "outtmpl": output_template,

            # 🔥 EN KRİTİK SATIR
            "cookiefile": cookies_path,

            # Bot algısını düşürür
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                )
            },

            # YouTube extractor fix
            "extractor_args": {
                "youtube": {
                    "player_client": ["web"]
                }
            },

            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],

            "quiet": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)

        mp3_file = None
        for f in os.listdir(temp_dir):
            if f.endswith(".mp3"):
                mp3_file = os.path.join(temp_dir, f)
                break

        if not mp3_file:
            raise Exception("MP3 dosyası üretilemedi")

        final_name = f"{uuid.uuid4()}.mp3"
        final_path = os.path.join(OUTPUT_DIR, final_name)
        shutil.move(mp3_file, final_path)

        return {
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "filename": final_name,
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# =========================
# API ENDPOINT
# =========================
@app.post("/api/mp3")
async def create_mp3(req: YouTubeRequest):
    try:
        data = convert_to_mp3(req.url)
        base_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

        return {
            "status": "success",
            "mp3Url": f"{base_url}/files/{data['filename']}",
            "title": data["title"],
            "duration": data["duration"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# FILE SERVE
# =========================
@app.get("/files/{filename}")
async def serve_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")

    return FileResponse(file_path, media_type="audio/mpeg")

# =========================
# HEALTH CHECK
# =========================
@app.get("/health")
def health():
    return {"status": "ok"}
