from fastapi import FastAPI, HTTPException
from search import search_music
from stream import get_stream_url
from download import get_download_url

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Mp3DMeta backend running"}

@app.get("/search")
async def search(q: str):
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
