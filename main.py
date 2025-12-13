import os
import uuid
import shutil
import tempfile
import yt_dlp

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="YouTube to MP3 API", version="2.2")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class YouTubeRequest(BaseModel):
    url: str

OUTPUT_DIR = "/tmp/mp3"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def convert_to_mp3(youtube_url: str):
    temp_dir = tempfile.mkdtemp()
    try:
        # Cookies yaz
        cookies_env = os.getenv("YT_COOKIES")
        cookies_path = os.path.join(temp_dir, "cookies.txt") if cookies_env else None
        if cookies_env:
            with open(cookies_path, "w", encoding="utf-8") as f:
                f.write(cookies_env)

        outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best/best",
            "noplaylist": True,
            "outtmpl": outtmpl,
            "quiet": True,
            "nocheckcertificate": True,
            "user_agent": "Mozilla/5.0",
            "cookies": cookies_path,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
            "js_runtimes": ["node"],  # JS solver Node.js ile
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)

        mp3_file = next((os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith(".mp3")), None)
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

@app.get("/files/{filename}")
async def serve_file(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    return FileResponse(path, media_type="audio/mpeg")

@app.get("/health")
def health():
    return {"status": "ok"}
