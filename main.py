import os
import tempfile
import logging
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from pydantic import BaseModel, HttpUrl
import uuid

# ---- logging, app, vs (mevcut kodun başı) ----

YTDLP_COOKIES = os.environ.get("YTDLP_COOKIES")  # Render env var

def create_cookie_file_from_env() -> str | None:
    """
    YTDLP_COOKIES env var doluysa geçici bir cookies.txt oluşturup yolunu döndürür.
    Boşsa None döner.
    """
    if not YTDLP_COOKIES:
        return None

    try:
        # NamedTemporaryFile ile oluştur, delete=False çünkü yt-dlp okurken dosya var olmalı
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", suffix=".txt") as f:
            f.write(YTDLP_COOKIES)
            logger.info(f"Geçici cookie dosyası yaratıldı: {f.name}")
            return f.name
    except Exception as e:
        logger.error(f"Cookie dosyası oluşturulamadı: {e}")
        return None

def cleanup_file(path: str | None):
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.info(f"Geçici dosya silindi: {path}")
        except Exception as e:
            logger.warning(f"Geçici dosya silinemedi: {e}")

def get_audio_url_from_youtube(video_url: str) -> dict:
    """
    yt-dlp ile video info alır. Eğer env ile cookie sağlanmışsa cookiefile parametresi ekler.
    """
    cookie_path = create_cookie_file_from_env()
    # Temel seçenekler
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
    }

    # cookie varsa ekle (yalnızca var ise)
    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info:
                raise DownloadError("Video bilgileri alınamadı (boş yanıt).")

            # audio url bul
            audio_url = None
            formats = info.get("formats") or []
            audio_formats = [
                f for f in formats
                if f.get("acodec") != "none" and (f.get("vcodec") == "none" or not f.get("vcodec"))
                and f.get("url")
            ]
            if audio_formats:
                audio_url = audio_formats[-1].get("url")

            if not audio_url:
                audio_url = info.get("url")

            if not audio_url:
                raise DownloadError("Uygun ses akış URL'si bulunamadı.")

            return {
                "title": info.get("title", "Baslik Yok"),
                "thumbnail": info.get("thumbnail", ""),
                "duration": info.get("duration", 0),
                "audio_url": audio_url,
            }

    except DownloadError as e:
        logger.error(f"yt-dlp hatası: {e}")
        # Eğer cookie ile çözülecek bir hata ise kullanıcıya yönlendirici mesaj ver
        if "Sign in to confirm" in str(e) or "cookies" in str(e).lower():
            raise HTTPException(status_code=400, detail=f"Video erişimi için çerez gerekli olabilir. Sunucuya YTDLP_COOKIES ortam değişkenini ekleyin. Hata: {e}")
        raise HTTPException(status_code=404, detail=f"Video bilgileri çekilemedi. Hata: {e}")
    except Exception as e:
        logger.exception("Beklenmedik hata")
        raise HTTPException(status_code=500, detail=f"Sunucuda hata: {e}")
    finally:
        cleanup_file(cookie_path)
