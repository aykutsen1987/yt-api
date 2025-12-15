# stream.py
import yt_dlp

def get_stream_url(video_id: str):
    ydl_opts = {
        "format": "bestaudio",
        "quiet": True,
        "nocheckcertificate": True,
        "skip_download": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False
            )

            if "url" not in info:
                return None

            return info["url"]

    except Exception as e:
        print(f"[STREAM ERROR] {video_id} -> {e}")
        return None
