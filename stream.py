# stream.py
import yt_dlp

def get_stream_url(video_id: str) -> str | None:
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "nocheckcertificate": True,
        "skip_download": True,
        "extract_flat": False,
        "forcejson": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False
            )

            if not info:
                return None

            # 🔑 En güvenlisi
            if "url" in info:
                return info["url"]

            # fallback
            formats = info.get("formats", [])
            if formats:
                return formats[-1].get("url")

            return None

    except Exception as e:
        print(f"[STREAM ERROR] {video_id} -> {e}")
        return None
