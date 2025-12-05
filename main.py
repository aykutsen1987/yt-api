from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)

@app.route("/api/yt", methods=["GET"])
def yt():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "url parameter missing"}), 400

    try:
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify(info)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return "YT API is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
