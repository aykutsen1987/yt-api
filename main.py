from fastapi import FastAPI
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

class YtRequest(BaseModel):
    url: str

@app.post("/api/yt")
def get_audio(req: YtRequest):

    ydl_opts = {
        "format": "ba[ext=m4a]/bestaudio/best",
        "quiet": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(req.url, download=False)

    return {
        "status": "ok",
        "title": info.get("title"),
        "audio_url": info["url"]
    }
