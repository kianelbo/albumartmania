from crawler import get_random_album_cover
from image import crop_image


if __name__ == "__main__":
    result = get_random_album_cover()

    print(f"{result['year']} — {result['artist']} — {result['album']}")
    print(f"Cover: {result['cover_url']}")

    crop_image(result["downloaded_path"])
