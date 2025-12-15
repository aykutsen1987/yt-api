import itertools
import os

YOUTUBE_API_KEYS = [
    os.getenv("YT_KEY_1"),
    os.getenv("YT_KEY_2"),
    os.getenv("YT_KEY_3")
]

YOUTUBE_API_KEYS = [k for k in YOUTUBE_API_KEYS if k]
_key_cycle = itertools.cycle(YOUTUBE_API_KEYS)

def get_api_key():
    return next(_key_cycle)
