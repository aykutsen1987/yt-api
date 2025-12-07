from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import os

app = FastAPI()

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 🔥 10 parçayı birleştirip cookies.txt dosyasını oluşturan fonksiyon
def create_cookie_file():
    cookie_file = "cookies.txt"
    parts = []

    for i in range(1, 11):  # 1'den 10'a kadar
        key = f"YTDLP_COOKIES_{i}"
        part = os.getenv(key)

        if part is None:
            print(f"[UYARI] {key} bulunamadı, boş kabul edildi.")
            part = ""

        parts.append(part)

    # Birleştir ve cookies.txt oluştur
    with open(cookie_file, "w", encoding="utf-8") as f:
        f.write("".join(parts))

    print("✔ cookies.txt oluşturuldu.")


# 🔥 FastAPI başlarken cookie dosyasını oluştur
create_cookie_file()


# =============== YOUTUBE INFO ENDPOINT ================
@app.get("/info")
def get_video_info(url: str):
    try:
        print(f"İstek alındı: {url}")

        # yt-dlp komutu (cookies.txt kullanıyor)
        result = subprocess.check_output([
            "yt-dlp",
            "--cookies", "cookies.txt",
            "-j",   # JSON output
            url
        ])

        return {"status": "ok", "data": result.decode("utf-8")}

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Video bilgileri alınamadı: {e.output.decode('utf-8')}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def home():
    return {"message": "YT API çalışıyor!"}
