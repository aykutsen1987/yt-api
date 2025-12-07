import os
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS ayarı
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------
# COOKIES.TXT OLUŞTURMA FONKSİYONU
# -------------------------------------------------------
def create_cookie_file():
    cookie_file = "cookies.txt"
    all_parts = ""
    total_chars = 0

    print("=== COOKIE PARÇALARI OKUNUYOR ===")

    for i in range(1, 11):
        key = f"YTDLP_COOKIES_{i}"
        part = os.getenv(key)

        if part is None:
            print(f"[HATA] {key} hiç yok! (Render Environment Variable eksik)")
            part = ""
        else:
            print(f"{key} uzunluk: {len(part)}")

        total_chars += len(part)
        all_parts += part

    with open(cookie_file, "w", encoding="utf-8") as f:
        f.write(all_parts)

    print(f"✔ cookies.txt oluşturuldu. Toplam karakter: {total_chars}")
    print("=====================================\n")


# -------------------------------------------------------
# UYGULAMA BAŞLARKEN COOKIES.TXT OLUŞTUR
# -------------------------------------------------------
@app.on_event("startup")
def startup_event():
    create_cookie_file()


# -------------------------------------------------------
# /info → YouTube video bilgisi
# -------------------------------------------------------
@app.get("/info")
def get_info(url: str):
    try:
        print(f"İstek alındı: {url}")

        # yt-dlp komutu (cookies ile)
        result = subprocess.check_output([
            "yt-dlp",
            "--cookies", "cookies.txt",
            "-j",
            url
        ], stderr=subprocess.STDOUT)

        json_data = result.decode("utf-8")
        return {"status": "ok", "data": json_data}

    except subprocess.CalledProcessError as e:
        error_message = e.output.decode("utf-8")

        raise HTTPException(
            status_code=400,
            detail=f"Video bilgileri alınamadı: {error_message}"
        )


# -------------------------------------------------------
# Debug endpoint (cookie boyutunu görmek için)
# -------------------------------------------------------
@app.get("/debug-cookies")
def debug_cookies():
    if not os.path.exists("cookies.txt"):
        return {"exists": False, "msg": "cookies.txt bulunamadı"}

    size = os.path.getsize("cookies.txt")
    return {"exists": True, "size_bytes": size}
