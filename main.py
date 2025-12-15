from fastapi import FastAPI
from search import search_music


app = FastAPI()

@app.get("/")
def root():
    return {"status": "Mp3DMeta backend running"}

@app.get("/search")
def search(q: str):
    return search_music(q)

@app.get("/stream/{video_id}")
def stream(video_id: str):
    return stream_audio(video_id)

@app.get("/download/{video_id}")
def download(video_id: str):
    return download_audio(video_id)
