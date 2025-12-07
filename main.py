import os
from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

# ---------------------------------------------------------
#  COOKIES.TXT OLUŞTURMA
# ---------------------------------------------------------
def create_cookie_file():
    # Çevre değişkenlerini oku
    c1 = os.getenv("YTDLP_COOKIES_1", "")
    c2 = os.getenv("YTDLP_COOKIES_2", "")
    c3 = os.getenv("YTDLP_COOKIES_3", "")

    full_cookie = c1 + c2 + c3

    # Boş değilse dosyayı oluştur
    if full_cookie.strip():
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(full_cookie)
        print("cookies.txt oluşturuldu.")
    else:
        print("UYARI: Cookie bulunamadı. Yalnızca çerezsiz indirme yapılır.")


# Uygulama açılırken cookie dosyasını oluştur
create_cookie_file()


# ---------------------------------------------------------
#  YTDLP İNDİRME API
# ---------------------------------------------------------
@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json()

    if not data or "url" not in data:
        return jsonify({"error": "URL gerekli"}), 400

    url = data["url"]

    output_file = "video.mp4"

    command = [
        "yt-dlp",
        "--cookies", "cookies.txt",
        "-o", output_file,
        url
    ]

    try:
        subprocess.run(command, check=True)
        return jsonify({
            "success": True,
            "output_file": output_file
        })
    except subprocess.CalledProcessError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
#  TEST ENDPOINT
# ---------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return "YT-DLP Backend Çalışıyor!", 200


# ---------------------------------------------------------
#  RENDER PORT AYARI
# ---------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
