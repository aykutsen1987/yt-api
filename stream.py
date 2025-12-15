import yt_dlp

async def get_stream_url(video_id: str):
    ydl_opts = {
        "format": "bestaudio",
        "quiet": True,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False,
            )
            return {
                "streamUrl": info["url"],
                "expiresIn": 600,
            }
    except Exception:
        return None
