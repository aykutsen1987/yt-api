# main.py dosyasında...
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List
import os
import httpx
import uuid
import asyncio
import subprocess # Komut satırı araçlarını (yt-dlp/ffmpeg) çalıştırmak için kritik!

# ... (Track ve SearchResponse Modelleri burada kalır) ...

# ... (Ortam Değişkenleri burada kalır) ...

app = FastAPI(...)

# Global olarak iş durumlarını saklamak için basit bir sözlük (Veritabanı/Redis simülasyonu)
JOB_STATUS = {} 

# ----------------------------------------------------
# Uzun Süreli İşlem: Video Dönüşümünü Gerçekleştiren Fonksiyon
# Render Worker'ı olsaydı bu fonksiyon Worker'da çalışırdı.
# Web Service üzerinde kullanmak için asenkron yapıyı kullanıyoruz.
# ----------------------------------------------------
async def run_conversion_task(video_url: str, job_id: str, title: str):
    JOB_STATUS[job_id] = {"status": "PROCESSING", "progress": 0, "title": title}
    output_path = f"/tmp/{job_id}.mp3" # Render'da /tmp dizini yazılabilir.

    # --extract-audio: Yalnızca ses akışını çıkar.
    # --audio-format mp3: Çıktı formatını mp3 olarak ayarla.
    # -o: Çıktı dosya yolu.
    command = [
        "yt-dlp",
        "--extract-audio", 
        "--audio-format", "mp3", 
        "--no-progress", # Konsol çıktısını sadeleştirir
        "-o", output_path,
        video_url
    ]
    
    try:
        # subprocess.run yerine, FastAPI'nin event döngüsünü engellememek için
        # asyncio.to_thread veya loop.run_in_executor kullanmak en iyisidir.
        # Bu, Render'ın timeout riskini azaltır ancak tamamen ortadan kaldırmaz.
        # BASİT ÇÖZÜM: subprocess.run (Hala riskli, ama en az çabayla yt-dlp kullanma yolu)
        
        # subprocess.run senkron bir fonksiyondur, bu yüzden thread'de çalıştırmalıyız.
        # (Bu, tek bir Render Web Service'de uzun süreli dönüşümün en iyi yolu değildir, 
        # ancak Celery/Redis entegrasyonundan kaçınmanın en basitidir.)
        def sync_conversion():
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True # Hata varsa istisna fırlatır
            )
            return process
        
        await asyncio.to_thread(sync_conversion)
        
        # Başarılı (Başarıdan sonra S3'e yükleme kodu buraya gelir)
        # S3 yüklemesi için 'boto3' kütüphanesi ve 'AWS_ACCESS_KEY' değişkenleri gerekir.
        
        # Şimdilik başarılı varsayıyoruz.
        download_url = f"https://YOUR_S3_BUCKET_URL/{job_id}.mp3" 
        JOB_STATUS[job_id] = {"status": "COMPLETED", "progress": 100, "downloadUrl": download_url}
        
    except subprocess.CalledProcessError as e:
        JOB_STATUS[job_id] = {"status": "FAILED", "error": f"Dönüşüm hatası: {e.stderr}"}
    except Exception as e:
        JOB_STATUS[job_id] = {"status": "FAILED", "error": f"Beklenmedik hata: {str(e)}"}
    finally:
        # Dönüşüm bitince geçici dosyayı temizle (Render'ın geçici diski dolar)
        if os.path.exists(output_path):
            os.remove(output_path)


# ----------------------------------------------------
# Endpoint: Uzun Dönüşümü Başlatma
# ----------------------------------------------------
@app.post("/api/convert/start", tags=["Conversion"])
async def start_conversion(track: Track):
    """
    Uzun süreli video dönüşümünü bir arka plan thread'inde başlatır ve hemen yanıt döner.
    """
    # 15 dakikanın altındaki videolar (900 saniye) uygulamanın kendisi tarafından işlenmelidir.
    if track.duration <= 900:
         raise HTTPException(status_code=400, detail="Bu video cihazda (FFmpegKit) işlenecek kadar kısadır.")
         
    job_id = str(uuid.uuid4())
    
    # Arka plan işini başlatıyoruz. HTTP isteğini engellemez.
    # Bu, Render Web Service'inize 300 saniye timeout kısıtlamasına rağmen 
    # uzun süreli işleri başlatma yeteneği verir.
    asyncio.create_task(run_conversion_task(track.videoUrl, job_id, track.title))
    
    return {
        "jobId": job_id,
        "status": "PROCESSING_STARTED",
        "message": "Dönüşüm arka planda başladı. Lütfen durumu kontrol edin."
    }

# ----------------------------------------------------
# Endpoint: Durum Kontrolü
# ----------------------------------------------------
@app.get("/api/convert/status", tags=["Conversion"])
def get_conversion_status(jobId: str):
    """ Dönüşüm işinin durumunu (Bekliyor, İşleniyor, Tamamlandı, Hata) döndürür. """
    status = JOB_STATUS.get(jobId)
    if not status:
        raise HTTPException(status_code=404, detail="Job ID bulunamadı.")
    
    return status

# ... (Diğer endpointler: /api/search, /api/copyright-check) ...
