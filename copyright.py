KEYWORDS = [
    "no copyright",
    "royalty free",
    "copyright free",
    "free to use",
    "public domain"
]

def is_copyright_free(title: str, description: str, channel: str) -> bool:
    text = f"{title} {description} {channel}".lower()
    return any(k in text for k in KEYWORDS)
