from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import httpx
import uuid
import asyncio
import subprocess
from dotenv import load_dotenv
import json

# .env dosyasından ortam değişkenlerini yükler (Yerel Geliştirme İçin)
# Render'da bu dosya kullanılmaz, ortam değişkenleri direkt Render'dan gelir.
load_dotenv()

# --- UYGULAMA TANIMI ---
app = FastAPI(
    title="Mp3DMeta Backend API",
    description="Müzik arama ve uzun video dönüşümü servisi.",
    version="1.0.0"
)

# --- ORTAM DEĞİŞKENLERİ ---
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
# Varsayımsal S3 URL'si
AWS_S3_BASE_URL = os.getenv("AWS_S3_BASE_URL", "https://your-s3-storage.com/")

# Global olarak iş durumlarını saklamak için basit bir sözlük (Render kapandığında sıfırlanır. 
# Üretimde Redis/Veritabanı kullanılmalıdır.)
JOB_STATUS: Dict[str, Dict] = {} 

# --- PYDANTIC MODELLERİ ---

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

# ----------------------------------------------------
# KRİTİK FONKSİYON: Arka Plan Dönüşüm Görevi
# ----------------------------------------------------
async def run_conversion_task(video_url: str, job_id: str, title: str):
    """FFmpeg ve yt-dlp kullanarak video'yu MP3'e dönüştürür."""
    
    JOB_STATUS[job_id] = {"status": "PROCESSING", "progress": 0, "title": title}
    output_path_temp = f"/tmp/{job_id}.mp3" # Render'da /tmp dizini yazılabilir.
    
    # yt-dlp komutu: Sesi MP3 olarak çıkar
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
        # Uzun süren I/O işlemini ana event loop'u engellemeden çalıştırmak için thread kullanıyoruz.
        def sync_conversion():
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
        
        # subprocess'i ayrı bir thread'de çalıştırır
        await asyncio.to_thread(sync_conversion)
        
        # Dönüşüm Başarılı
        # *** S3 Yükleme Mantığı buraya gelir ***
        
        # Basitlik için varsayılan indirme URL'sini döndürüyoruz.
        final_download_url = f"{AWS_S3_BASE_URL}{job_id}.mp3" 
        
        JOB_STATUS[job_id] = {
            "status": "COMPLETED", 
            "progress": 100, 
            "downloadUrl": final_download_url
        }
        
    except subprocess.CalledProcessError as e:
        error_message = f"Dönüşüm hatası: {e.stderr}"
        print(f"[{job_id}] FAILED. Error: {error_message}")
        JOB_STATUS[job_id] = {"status": "FAILED", "error": error_message}
    except Exception as e:
        error_message = f"Beklenmedik hata: {str(e)}"
        print(f"[{job_id}] FAILED. Error: {error_message}")
        JOB_STATUS[job_id] = {"status": "FAILED", "error": error_message}
    finally:
        # Geçici dosyayı temizle
        if os.path.exists(output_path_temp):
            os.remove(output_path_temp)
            print(f"[{job_id}] Temporary file deleted.")


# ----------------------------------------------------
# 1. Endpoint: Müzik Arama
# ----------------------------------------------------
@app.get("/api/search", response_model=SearchResponse, tags=["Search"])
async def search_music(q: str = Query(..., min_length=3)):
    """YouTube API kullanarak müzik arar."""
    if not YOUTUBE_API_KEY:
        raise HTTPException(status_code=503, detail="YOUTUBE_API_KEY ortam değişkeni eksik.")

    youtube_url = "https://www.googleapis.com/youtube/v3/search"
    
    params = {
        "part": "snippet",
        "q": q,
        "key": YOUTUBE_API_KEY,
        "type": "video",
        "maxResults": 10
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(youtube_url, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            # YouTube API hatasını yakala ve temiz bir hata döndür.
            raise HTTPException(status_code=500, detail=f"YouTube API hatası: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ağ hatası: {str(e)}")


    results = []
    for item in data.get("items", []):
        video_id = item["id"]["videoId"]
        
        # SÜRE BİLGİSİ: YouTube Search API'den doğrudan gelmez, bu yüzden varsayımsal 
        # olarak 5 dakika (300 saniye) atıyoruz. 
        # Gerçekte, ek bir 'videos' endpoint çağrısı gerekir.
        duration_seconds = 300 

        results.append(Track(
            id=video_id,
            title=item["snippet"]["title"],
            artist=item["snippet"].get("channelTitle", "Bilinmiyor"),
            channel=item["snippet"].get("channelTitle", "Bilinmiyor"),
            thumbnailUrl=item["snippet"]["thumbnails"]["default"]["url"],
            videoUrl=f"https://www.youtube.com/watch?v={video_id}",
            duration=duration_seconds,
            hasCopyright=False
        ))

    return SearchResponse(results=results)

# ----------------------------------------------------
# 2. Endpoint: Uzun Dönüşümü Başlatma
# ----------------------------------------------------
@app.post("/api/convert/start", response_model=ConvertResponse, tags=["Conversion"])
async def start_conversion_endpoint(track: Track):
    """
    Uzun süreli video dönüşümünü arka plan thread'inde başlatır ve hemen yanıt döner.
    """
    # Uygulamanızın 15 dk (900s) üstü kuralını kontrol et.
    if track.duration <= 900:
         raise HTTPException(status_code=400, detail="Bu video cihazda (FFmpegKit) işlenmelidir.")
         
    job_id = str(uuid.uuid4())
    
    # Arka plan işini başlatıyoruz. Bu, HTTP isteğini bloke etmez (non-blocking).
    # Bu, Render'ın timeout (zaman aşımı) sorununu aşmanın yoludur.
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
    """ Telif hakkı kontrolü yapar. Basitlik için her zaman FALSE dönüyoruz. """
    return {"hasCopyright": False}

# ----------------------------------------------------
# Başlangıç Kontrolü
# ----------------------------------------------------
@app.on_event("startup")
async def startup_event():
    if not YOUTUBE_API_KEY:
        print("CRITICAL: YOUTUBE_API_KEY is not set!")
        # Uygulama burada çökerse, Render loglarında bu hatayı görürsünüz.
        # raise ValueError("YOUTUBE_API_KEY must be set in environment variables.")
