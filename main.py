from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import uuid
import asyncio
import subprocess
import json
import re
from youtube_search import YoutubeSearch # Zero-Quota Yedek
from googleapiclient.discovery import build # Resmi YouTube API

# --- UYGULAMA TANIMI ---
app = FastAPI(
    title="Mp3DMeta Hybrid Backend API",
    description="Kota yedekli arama ve yt-dlp ile dönüşüm servisi.",
    version="1.0.0"
)

# Global Durum
JOB_STATUS: Dict[str, Dict] = {} 

# --- GÜNCELLENMİŞ KRİTİK FONKSİYON ---
def get_api_keys():
    """Ortam değişkenlerinden 10 adede kadar API anahtarı okur."""
    keys = []
    # 1'den 10'a kadar anahtarları kontrol et
    for i in range(1, 11): # <-- DÖNGÜ SINIRI 10'a ÇIKARILDI
        key = os.getenv(f"YOUTUBE_API_KEY_{i}")
        if key:
            keys.append(key)
            
    # Eğer hiç numaralı anahtar tanımlı değilse, YOUTUBE_API_KEY adlı tekil anahtarı dene
    if not keys:
        single_key = os.getenv("YOUTUBE_API_KEY")
        if single_key:
            keys.append(single_key)
            
    return keys

API_KEY_POOL = get_api_keys()
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

# --- PYDANTIC MODELLERİ VE YARDIMCI FONKSİYONLAR (AYNI KALIR) ---
# ...
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

def parse_duration_to_seconds(duration_str: str) -> int:
    parts = list(map(int, duration_str.split(':')))
    seconds = 0
    if len(parts) == 3:
        seconds += parts[0] * 3600
        seconds += parts[1] * 60
        seconds += parts[2]
    elif len(parts) == 2:
        seconds += parts[0] * 60
        seconds += parts[1]
    else:
        seconds = parts[0] if parts else 0
    return seconds
    
async def run_conversion_task(video_url: str, job_id: str, title: str):
    JOB_STATUS[job_id] = {"status": "PROCESSING", "progress": 0, "title": title}
    output_path_temp = f"/tmp/{job_id}.mp3"
    
    command = [
        "yt-dlp", "--extract-audio", "--audio-format", "mp3", 
        "--audio-quality", "192K", "--no-progress", "-o", output_path_temp, video_url
    ]
    
    print(f"[{job_id}] Conversion started for: {title}")

    try:
        def sync_conversion():
            return subprocess.run(command, capture_output=True, text=True, check=True)
        
        await asyncio.to_thread(sync_conversion)
        
        final_download_url = f"https://your-s3-storage.com/{job_id}.mp3" 
        
        JOB_STATUS[job_id] = {
            "status": "COMPLETED", "progress": 100, "downloadUrl": final_download_url
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

async def search_with_api(query: str, api_key: str) -> List[Track]:
    """Resmi YouTube API ile arama yapar."""
    youtube = await asyncio.to_thread(
        build, API_SERVICE_NAME, API_VERSION, developerKey=api_key
    )

    request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=10
    )
    
    response = await asyncio.to_thread(request.execute)

    results = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
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
    return results

async def search_with_scraper(query: str) -> List[Track]:
    """Zero-Quota Scraping ile arama yapar."""
    results_json = await asyncio.to_thread(YoutubeSearch, query, max_results=10)
    data = results_json.to_json()
    search_results = json.loads(data).get('videos', [])
    
    results = []
    for item in search_results:
        video_id = item["id"]
        duration_seconds = parse_duration_to_seconds(item.get("duration", "0:00")) 
        
        results.append(Track(
            id=video_id,
            title=item["title"],
            artist=item.get("channel", "Bilinmiyor"),
            channel=item.get("channel", "Bilinmiyor"),
            thumbnailUrl=item.get("thumbnails", [""])[0],
            videoUrl=f"https://www.youtube.com/watch?v={video_id}",
            duration=duration_seconds,
            hasCopyright=False
        ))
    return results


# ----------------------------------------------------
# 1. Endpoint: HİBRİT Müzik Arama
# ----------------------------------------------------
@app.get("/api/search", response_model=SearchResponse, tags=["Search"])
async def search_music_hybrid(q: str = Query(..., min_length=3)):
    if API_KEY_POOL:
        for i, key in enumerate(API_KEY_POOL):
            try:
                print(f"INFO: Trying API Key #{i+1}...")
                results = await search_with_api(q, key)
                print(f"INFO: API Key #{i+1} Succeeded.")
                return SearchResponse(results=results)
                
            except Exception as e:
                # 403 Forbidden veya Kota hatası durumunda bir sonraki anahtarı dene
                print(f"WARNING: API Key #{i+1} Failed. Trying next or falling back. Error: {e}")
                continue
                
    
    # --- 2. Zero-Quota Scraping'e Geç (Fallback) ---
    print("WARNING: API Key pool exhausted or empty. Falling back to Zero-Quota Scraper.")
    try:
        results = await search_with_scraper(q)
        print("INFO: Scraper Succeeded.")
        return SearchResponse(results=results)
    except Exception as e:
        print(f"CRITICAL: Scraper failed. Error: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Tüm arama servislerimiz geçici olarak kullanılamıyor."
        )


# ----------------------------------------------------
# Diğer Endpointler (AYNI KALIR)
# ----------------------------------------------------

@app.post("/api/convert/start", response_model=ConvertResponse, tags=["Conversion"])
async def start_conversion_endpoint(track: Track):
    if track.duration <= 900:
         raise HTTPException(status_code=400, detail="Bu video cihazda (FFmpegKit) işlenmelidir.")
         
    job_id = str(uuid.uuid4())
    asyncio.create_task(run_conversion_task(track.videoUrl, job_id, track.title))
    
    return ConvertResponse(
        jobId=job_id,
        message="Dönüşüm arka planda başlatıldı. Durum kontrolü için /api/convert/status kullanın."
    )

@app.get("/api/convert/status", tags=["Conversion"])
def get_conversion_status(jobId: str):
    status = JOB_STATUS.get(jobId)
    if not status:
        raise HTTPException(status_code=404, detail="Job ID bulunamadı.")
    return status

@app.get("/api/copyright-check", tags=["Search"])
def check_copyright(videoId: str):
    return {"hasCopyright": False}
