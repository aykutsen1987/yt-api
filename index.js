import express from "express";
import { exec } from "child_process";
import cors from "cors";

const app = express();
app.use(cors());
app.use(express.json());

app.post("/api/yt", (req, res) => {
    const url = req.body.url;

    if (!url) return res.json({ error: "URL boş!" });

    const command = `yt-dlp -f bestaudio --dump-json "${url}"`;

    exec(command, { maxBuffer: 1024 * 5000 }, (error, stdout, stderr) => {
        if (error) {
            return res.json({ error: stderr.toString() });
        }

        try {
            const json = JSON.parse(stdout);
            const audioUrl = json.url;

            res.json({
                title: json.title,
                thumbnail: json.thumbnail,
                downloadUrl: audioUrl
            });

        } catch (e) {
            res.json({ error: "Çözüm yapılamadı (JSON)." });
        }
    });
});

app.listen(10000, () => {
    console.log("YT API çalışıyor 10000 portunda");
});
