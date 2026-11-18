import logging
from pathlib import Path
from time import sleep

from crawler import get_random_album
from video_gen import create_short_video, save_random_thumbnail
from youtube import YouTubeClient

logger = logging.getLogger(__name__)


def _get_caption(listeners_count):
    if listeners_count > 2_000_000:
        return "Can you recognize\nthis iconic album?"
    elif listeners_count < 1_000_000:
        return "Only real music nerds\nknow this album"
    return "How soon can you\nguess the album?"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    logger.info("Fetching a random album...")
    album = get_random_album()
    logger.info("Album fetched!")

    output_path = Path("reveal.mp4")
    output_path = create_short_video(
        Path(album["cover_path"]).read_bytes(),
        Path(album["preview_track_path"]).read_bytes(),
        output_path,
        caption=_get_caption(album["listeners_count"]),
        credit=f"{album['artist']}, {album['year']}\n{album['title']}",
    )
    logger.info("Created %s", output_path)

    client = YouTubeClient()
    tags = ["album art", "ambient", "music"]
    tags.append(album["artist"])
    tags.append(album["title"])

    logger.info("Uploading %s...", output_path.name)
    video_id = client.upload_short(
        output_path,
        "Guess the album! #music #albumart",
        "Test your music knowledge by guessing the album and the song! Subscribe for more daily challenges.",
        tags,
    )
    logger.info("Uploaded successfully: https://www.youtube.com/watch?v=%s", video_id)

    sleep(5 * 60)  # Wait before setting the thumbnail
    thumbnail_path, thumbnail_time = save_random_thumbnail(output_path)
    logger.info("Created thumbnail %s from %.2fs", thumbnail_path, thumbnail_time)
    client.set_thumbnail(video_id, thumbnail_path)
    logger.info("Custom thumbnail uploaded successfully!")
