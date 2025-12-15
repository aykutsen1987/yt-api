from fastapi import FastAPI, HTTPException
from stream import get_stream_url

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Mp3DMeta backend running"}

@app.get("/stream/{video_id}")
def stream(video_id: str):
    url = get_stream_url(video_id)

    if not url:
        raise HTTPException(
            status_code=403,
            detail="Stream not available for this content"
        )

    return {
        "streamUrl": url
    }
