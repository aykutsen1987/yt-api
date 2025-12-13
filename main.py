import os
import uuid
import shutil
import yt_dlp
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="YT to MP3 API", version="2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class YouTubeRequest(BaseModel):
    url: HttpUrl

OUTPUT_DIR = "/tmp/mp3"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def convert_to_mp3(url: str):
    temp_dir = tempfile.mkdtemp()
    outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "outtmpl": outtmpl,
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128"
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    mp3_file = None
    for f in os.listdir(temp_dir):
        if f.endswith(".mp3"):
            mp3_file = os.path.join(temp_dir, f)

    if not mp3_file:
        raise Exception("MP3 üretilemedi")

    final_name = f"{uuid.uuid4()}.mp3"
    final_path = os.path.join(OUTPUT_DIR, final_name)
    shutil.move(mp3_file, final_path)
    shutil.rmtree(temp_dir)

    return {
        "title": info.get("title", "Unknown"),
        "duration": info.get("duration", 0),
        "file": final_name
    }

@app.post("/api/mp3")
async def create_mp3(req: YouTubeRequest):
    try:
       
        data = convert_to_mp3(str(req.url))
        base = os.getenv("RENDER_EXTERNAL_URL", "")
        return {
            "status": "success",
            "mp3Url": f"{base}/files/{data['file']}",
            "title": data["title"],
            "duration": data["duration"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/{filename}")
async def serve_file(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Dosya yok")
    return FileResponse(path, media_type="audio/mpeg")

@app.get("/health")
def health():
    return {"status": "ok"}
