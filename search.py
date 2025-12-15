import httpx
from api_keys import get_api_key
from copyright import is_copyright_free


async def search_music(query: str):
    api_key = get_api_key()
    url = "https://www.googleapis.com/youtube/v3/search"

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoCategoryId": "10",
        "maxResults": 15,
        "key": api_key
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        items = r.json()["items"]

    results = []

    for item in items:
        snippet = item["snippet"]
        can_download = is_download_allowed(
            snippet["title"],
            snippet.get("description", ""),
            snippet["channelTitle"]
        )

        results.append({
            "id": item["id"]["videoId"],
            "title": snippet["title"],
            "artist": snippet["channelTitle"],
            "duration": 0,
            "thumbnail": snippet["thumbnails"]["medium"]["url"],
            "canStream": True,
            "canDownload": can_download,
            "reason": "royalty_free" if can_download else "copyright"
        })

    return results
