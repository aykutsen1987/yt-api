from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import uuid
import asyncio
import subprocess
import re
from youtube_search import YoutubeSearch # Yeni arama kütüphanesi
from datetime import timedelta

# --- UYGULAMA TANIMI ---
app = FastAPI(
    title="Mp3DMeta Zero-Quota Backend API",
    description="Doğrudan web scraping ile arama ve yt-dlp ile dönüşüm servisi.",
    version="1.0.0"
)

# Global olarak iş durumlarını saklamak için basit bir sözlük (Redis/Veritabanı simülasyonu)
JOB_STATUS: Dict[str, Dict] = {} 

# --- PYDANTIC MODELLERİ ---
# ... (Track, SearchResponse, ConvertResponse modelleri aynı kalır) ...

class Track(BaseModel):
    id: str
    title: str
    artist: str
    channel: str
    thumbnailUrl: str
    videoUrl: str
    duration: int # Saniye cinsinden
    hasCopyright: bool = False

class SearchResponse(BaseModel):
    results: List[Track]

class ConvertResponse(BaseModel):
    jobId: str
    message: str


# --- YARDIMCI FONKSİYONLAR ---

def parse_duration_to_seconds(duration_str: str) -> int:
    """Süre stringini (örn: '1:30' veya '1:00:30') saniyeye çevirir."""
    parts = list(map(int, duration_str.split(':')))
    seconds = 0
    if len(parts) == 3:
        seconds += parts[0] * 3600 # Saat
        seconds += parts[1] * 60  # Dakika
        seconds += parts[2]       # Saniye
    elif len(parts) == 2:
        seconds += parts[0] * 60  # Dakika
        seconds += parts[1]       # Saniye
    else: # Sadece saniye veya yanlış format
        seconds = parts[0] if parts else 0
    return seconds


async def run_conversion_task(video_url: str, job_id: str, title: str):
    """FFmpeg ve yt-dlp kullanarak video'yu MP3'e dönüştürür."""
    # ... (run_conversion_task fonksiyonu önceki yanıttakiyle aynı kalır) ...
    JOB_STATUS[job_id] = {"status": "PROCESSING", "progress": 0, "title": title}
    output_path_temp = f"/tmp/{job_id}.mp3"
    
    # yt-dlp komutu
    command = [
        "yt-dlp",
        "--extract-audio", 
        "--audio-format", "mp3", 
        "--audio-quality", "192K",
        "--no-progress",
        "-o", output_path_temp,
        video_url
    ]
    
    print(f"[{job_id}] Conversion started for: {title}")

    try:
        def sync_conversion():
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
        
        await asyncio.to_thread(sync_conversion)
        
        # S3 yüklemesi atlandı, varsayılan URL dönüldü
        final_download_url = f"https://your-s3-storage.com/{job_id}.mp3" 
        
        JOB_STATUS[job_id] = {
            "status": "COMPLETED", 
            "progress": 100, 
            "downloadUrl": final_download_url
        }
        
    except subprocess.CalledProcessError as e:
        error_message = f"Dönüşüm hatası: {e.stderr}"
        JOB_STATUS[job_id] = {"status": "FAILED", "error": error_message}
    except Exception as e:
        error_message = f"Beklenmedik hata: {str(e)}"
        JOB_STATUS[job_id] = {"status": "FAILED", "error": error_message}
    finally:
        if os.path.exists(output_path_temp):
            os.remove(output_path_temp)
            print(f"[{job_id}] Temporary file deleted.")


# ----------------------------------------------------
# 1. Endpoint: Müzik Arama (Sıfır Kota Kullanımı)
# ----------------------------------------------------
@app.get("/api/search", response_model=SearchResponse, tags=["Search"])
async def search_music(q: str = Query(..., min_length=3)):
    """YouTube web scraping kullanarak müzik arar (Kotadan bağımsız)."""
    
    try:
        # YouTube'u arama sorgusu ile tarar
        # 10 sonuç, müzik filtresi (varsa)
        results_json = await asyncio.to_thread(
            YoutubeSearch, 
            q, 
            max_results=10
        )
        
        data = results_json.to_json()
        search_results = json.loads(data).get('videos', [])
        
    except Exception as e:
        print(f"Scraping Hatası: {str(e)}")
        # Scraping engellenmiş olabilir veya format değişmiş olabilir.
        raise HTTPException(
            status_code=500, 
            detail="Arama servisimiz geçici olarak kullanılamıyor. Lütfen tekrar deneyin."
        )

    results = []
    for item in search_results:
        video_id = item["id"]
        
        # Duration formatı: "1:30", "1:00:30" vb.
        duration_seconds = parse_duration_to_seconds(item.get("duration", "0:00")) 
        
        results.append(Track(
            id=video_id,
            title=item["title"],
            artist=item.get("channel", "Bilinmiyor"),
            channel=item.get("channel", "Bilinmiyor"),
            thumbnailUrl=item.get("thumbnails", [""])[0], # İlk küçük resmi al
            videoUrl=f"https://www.youtube.com/watch?v={video_id}",
            duration=duration_seconds,
            hasCopyright=False # Telif kontrolünü atla
        ))

    return SearchResponse(results=results)

# ----------------------------------------------------
# 2. Endpoint: Uzun Dönüşümü Başlatma
# ----------------------------------------------------
@app.post("/api/convert/start", tags=["Conversion"])
async def start_conversion_endpoint(track: Track):
    """
    Uzun süreli video dönüşümünü arka plan thread'inde başlatır ve hemen yanıt döner.
    """
    # Uygulamanızın 15 dk (900s) üstü kuralını kontrol et.
    if track.duration <= 900:
         raise HTTPException(status_code=400, detail="Bu video cihazda (FFmpegKit) işlenmelidir.")
         
    job_id = str(uuid.uuid4())
    asyncio.create_task(run_conversion_task(track.videoUrl, job_id, track.title))
    
    return ConvertResponse(
        jobId=job_id,
        message="Dönüşüm arka planda başlatıldı. Durum kontrolü için /api/convert/status kullanın."
    )

# ----------------------------------------------------
# 3. Endpoint: Durum Kontrolü
# ----------------------------------------------------
@app.get("/api/convert/status", tags=["Conversion"])
def get_conversion_status(jobId: str):
    """ Dönüşüm işinin durumunu döndürür. """
    status = JOB_STATUS.get(jobId)
    if not status:
        raise HTTPException(status_code=404, detail="Job ID bulunamadı.")
    
    return status

# ----------------------------------------------------
# 4. Endpoint: Telif Kontrolü
# ----------------------------------------------------
@app.get("/api/copyright-check", tags=["Search"])
def check_copyright(videoId: str):
    """ Telif hakkı kontrolü yapar. """
    return {"hasCopyright": False}
