from fastapi import FastAPI, HTTPException, Query
from youtube.search import search_music
from youtube.stream import get_stream_url
from youtube.download import get_download_url

app = FastAPI(
    title="Mp3DMeta Backend",
    version="1.0.0"
)

@app.get("/search")
async def search(q: str = Query(..., min_length=2)):
    return await search_music(q)

@app.get("/stream/{video_id}")
async def stream(video_id: str):
    url = await get_stream_url(video_id)
    if not url:
        raise HTTPException(status_code=404, detail="Stream not available")
    return {"streamUrl": url}

@app.get("/download/{video_id}")
async def download(video_id: str):
    data = await get_download_url(video_id)
    if not data:
        raise HTTPException(status_code=403, detail="Download not allowed")
    return data
