import yt_dlp
import tempfile

from api_keys import get_api_key


async def get_stream_url(video_id: str):
    ydl_opts = {
        "format": "bestaudio",
        "quiet": True,
        "nocheckcertificate": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False
            )
            return info["url"]
        except:
            return None
