from crawler import get_random_album_cover


if __name__ == "__main__":
    result = get_random_album_cover()

    print(f"{result['year']} — {result['artist']} — {result['album']}")
    print(f"Cover: {result['cover_url']}")
