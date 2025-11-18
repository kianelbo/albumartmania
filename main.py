import json
import os
import redis

from crawler import download_image, get_random_album_cover
from image import crop_image
from twitter import TwitterClient


REDIS_URL = os.getenv("REDIS_URL")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
redis_key = "last_album"


if __name__ == "__main__":
    r = redis.Redis(
        host=REDIS_URL,
        port=13261,
        decode_responses=True,
        username="default",
        password=REDIS_PASSWORD,
    )

    twitter_client = TwitterClient()

    saved = r.get(redis_key)

    if not saved:
        print("Fetching and posting the teaser...")

        album = get_random_album_cover()

        cropped_image = crop_image(album["downloaded_path"])

        tweet_id = twitter_client.post(cropped_image, "Guess the album 🎵")
        album["tweet_id"] = tweet_id

        r.set(redis_key, json.dumps(album))

    else:
        print("Fetching and posting the full image...")

        album = json.loads(saved)
        tweet_id = album["tweet_id"]

        twitter_client.delete(tweet_id)

        img_path = download_image(album["url"])
        text = f"{album['artist']} — {album['album']} ({album['year']})"
        twitter_client.post(img_path, text)

        r.delete(redis_key)
