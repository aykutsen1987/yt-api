from fastapi import FastAPI
from search import search_music
from stream import get_stream_url
from download import download_audio

app = FastAPI(title="Mp3DMeta Backend")

@app.get("/")
def root():
    return {"status": "Mp3DMeta backend running"}

@app.get("/search")
async def search(q: str):
    return await search_music(q)

@app.get("/stream/{video_id}")
async def stream(video_id: str):
    data = await get_stream_url(video_id)
    if not data:
        return {"error": "Stream alınamadı"}
    return data

@app.get("/download/{video_id}")
async def download(video_id: str):
    return await download_audio(video_id)
