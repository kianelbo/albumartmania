from pathlib import Path
from time import sleep

from crawler import get_random_album
from video_gen import create_short_video, save_random_thumbnail
from youtube import YouTubeClient


if __name__ == "__main__":
    print("Fetching a random album...")
    album = get_random_album()
    print("Album fetched!")

    output_path = Path("reveal.mp4")
    output_path =create_short_video(
        Path(album["cover_path"]).read_bytes(),
        Path(album["preview_track_path"]).read_bytes(),
        output_path,
        credit=f"{album['artist']}, {album['year']}\n{album['title']}",
    )
    print(f"Created {output_path}")

    client = YouTubeClient()
    tags = ["album art", "ambient", "music"]
    tags.append(album["artist"])
    tags.append(album["title"])

    print(f"Uploading {output_path.name}...")
    video_id = client.upload_short(output_path, "Guess the album! #music #albumart", tags=tags)
    print(f"Uploaded successfully: https://www.youtube.com/watch?v={video_id}")

    sleep(5 * 60)  # Wait before setting the thumbnail
    thumbnail_path, thumbnail_time = save_random_thumbnail(output_path)
    print(f"Created thumbnail {thumbnail_path} from {thumbnail_time:.2f}s")
    client.set_thumbnail(video_id, thumbnail_path)
    print("Custom thumbnail uploaded successfully!")
