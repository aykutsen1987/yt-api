import tempfile
import yt_dlp
from search import search_music

async def get_download_url(video_id: str):
    results = await search_music(video_id)

    if not results or not results[0]["canDownload"]:
        return None

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")

    ydl_opts = {
        "format": "bestaudio/mp3",
        "outtmpl": tmp.name,
        "quiet": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    return {
        "downloadUrl": tmp.name,
        "expiresIn": 600
    }
