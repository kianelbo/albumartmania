import os
import math
import random
import re
import requests
from datetime import datetime

LAST_FM_API_KEY = os.getenv("LAST_FM_API_KEY")


def _get_random_page_index(total_pages, lam=0.3):
    # Lower pages are more likely: p(page) ∝ e^{-λ*(page-1)}, λ controls bias
    probs = [math.exp(-lam * (p - 1)) for p in range(1, total_pages + 1)]
    total = sum(probs)
    probs = [p / total for p in probs]
    return random.choices(range(1, total_pages + 1), weights=probs, k=1)[0]


def _fix_lastfm_image_url(url: str):
    # Remove size segment from Last.fm image URLs, e.g.:
    # https://.../i/u/174s/xxxxx.png    -> https://.../i/u/xxxxx.png
    # https://.../i/u/300x300/xxxxx.png -> https://.../i/u/xxxxx.png
    return re.sub(r'/(\d+s?|\d+x\d+)/', '/', url)


def _is_popular_enough(album: dict, min_listeners=10000):
    # TODO
    return True


def download_file(url, out_path="./"):
    resp = requests.get(url)
    resp.raise_for_status()
    ext = resp.headers.get("Content-Type", "").lower().split("/")[-1]
    fname = f"{out_path}.{ext}"

    with open(fname, "wb") as f:
        f.write(resp.content)

    return fname

def get_random_album(year=None):
    if year is None:
        cur_year = datetime.now().year
        year = random.randint(1955, cur_year)

    lastfm_base_url = "http://ws.audioscrobbler.com/2.0/"
    deezer_base_url = "https://api.deezer.com/search"
    params = {
        "method": "tag.gettopalbums",
        "tag": str(year),
        "api_key": LAST_FM_API_KEY,
        "format": "json",
        "page": 1
    }

    response = requests.get(lastfm_base_url, params=params)
    response.raise_for_status()
    data = response.json().get("albums")
    total_pages = int(data["@attr"].get("totalPages", 1))

    cover_url = None
    while cover_url is None:
        chosen_page = _get_random_page_index(total_pages)

        params["page"] = chosen_page
        response = requests.get(lastfm_base_url, params=params)
        response.raise_for_status()
        albums_list = response.json().get("albums").get("album", [])

        album = random.choice(albums_list)
        if not _is_popular_enough(album):
            continue

        artist = album["artist"]["name"]
        title = album["name"]
        image_list = album.get("image", [])
        cover_url = None
        for img in reversed(image_list):
            if url := img.get("#text", None):
                cover_url = _fix_lastfm_image_url(url)
                break

        if cover_url:
            cover_path = download_file(cover_url)

            # Get a preview track from Deezer
            response = requests.get(deezer_base_url, params={"q": f"{artist} {title}"})
            response.raise_for_status()
            deezer_data = response.json()["data"]
            preview_track = deezer_data[0]["preview"]
            preview_track_path = download_file(preview_track)
            break

    return {
        "year": year,
        "artist": artist,
        "album": title,
        "cover_path": cover_path,
        "preview_track_path": preview_track_path,
    }
