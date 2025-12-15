KEYWORDS = [
    "no copyright",
    "royalty free",
    "copyright free",
    "free to use",
    "public domain"
]

def is_download_allowed(title: str, description: str, channel: str):
    text = f"{title} {description} {channel}".lower()
    for k in KEYWORDS:
        if k in text:
            return True
    return False
