from fastapi import FastAPI
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

class VideoRequest(BaseModel):
    url: str

@app.post("/api/yt")
async def get_video_info(data: VideoRequest):
    try:
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=False)
            return {"title": info.get("title"), "formats": info.get("formats")}
    except Exception as e:
        return {"error": str(e)}
