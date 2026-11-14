
import os
import mimetypes
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"
CATEGORY = "10" # Music


class YouTubeClient:
    def __init__(self):
        self._client = self._get_youtube_service()

    def _get_youtube_service(self):
        """Create an authenticated YouTube API client."""

        required_vars = [
            "YOUTUBE_CLIENT_ID",
            "YOUTUBE_CLIENT_SECRET",
            "YOUTUBE_REFRESH_TOKEN",
        ]
        missing = [name for name in required_vars if not os.getenv(name)]
        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

        credentials = Credentials(
            token=None,
            refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
            token_uri=TOKEN_URI,
            client_id=os.environ["YOUTUBE_CLIENT_ID"],
            client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
            scopes=SCOPES,
        )
        # Exchange the refresh token for a fresh access token.
        credentials.refresh(Request())

        return build(
            "youtube",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )


    def upload_short(self,
        file_path: str | Path,
        title: str | None = None,
        description: str = "",
        tags: list[str] | None = None,
        privacy_status: str = "public",
    ) -> str:
        """Upload a video and return its YouTube video ID."""

        path = Path(file_path)

        if not path.is_file():
            raise FileNotFoundError(f"Video not found: {path}")

        if privacy_status not in ("private", "public", "unlisted"):
            raise ValueError("Invalid privacy status")

        body = {
            "snippet": {
                "title": title or path.stem,
                "description": description,
                "categoryId": CATEGORY,
            },
            "status": {
                "privacyStatus": privacy_status,
            },
        }
        if tags:
            body["snippet"]["tags"] = tags

        mime_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
        media = MediaFileUpload(
            str(path),
            mimetype=mime_type,
            chunksize=8 * 1024 * 1024,
            resumable=True,
        )

        request = self._client.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Progress: {int(status.progress() * 100)}%")

        video_id = response["id"]

        return video_id


    def set_thumbnail(self, video_id: str, thumbnail_path: str | Path) -> None:
        """Set a custom thumbnail for a YouTube video."""
        thumbnail = Path(thumbnail_path)

        if not thumbnail.is_file():
            raise FileNotFoundError(f"Thumbnail not found: {thumbnail}")

        thumbnail_mime = mimetypes.guess_type(thumbnail.name)[0]
        if thumbnail_mime not in ("image/jpeg", "image/png"):
            raise ValueError("Thumbnail must be JPEG or PNG")

        self._client.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(
                str(thumbnail),
                mimetype=thumbnail_mime,
            ),
        ).execute()
