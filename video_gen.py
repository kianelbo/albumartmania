#!/usr/bin/env python3
"""Create a 60-second vertical album-reveal video with reversed audio."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from animation import render_animation
from audio import process_audio

FPS = 30
DURATION = 60
SIZE = 1080
VIDEO_HEIGHT = 1920
CAPTION = "How soon can you guess the album?"


def create_caption_frame_transform() -> Callable[[np.ndarray], np.ndarray]:
    top = np.zeros((420, SIZE, 3), dtype=np.uint8)
    banner = Image.fromarray(top)
    draw = ImageDraw.Draw(banner)
    draw.text(
        (SIZE // 2, 210),
        CAPTION,
        fill="white",
        font=ImageFont.load_default(size=48),
        anchor="mm",
    )
    header = np.asarray(banner)

    def compose(frame: np.ndarray) -> np.ndarray:
        composed = np.zeros((VIDEO_HEIGHT, SIZE, 3), dtype=np.uint8)
        composed[:420] = header
        composed[420:1500] = frame
        return composed

    return compose


def create_album_video(
    image_data: bytes,
    audio_data: bytes,
    output_path: Path,
    *,
    seed: int | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    processed_audio = process_audio(
        audio_data,
        muffle=False,
        half_speed=True,
        reverse=True,
        duration=DURATION,
    )

    with tempfile.TemporaryDirectory() as temporary_directory:
        square_video = Path(temporary_directory) / "reveal.mp4"
        render_animation(
            argparse.Namespace(
                input="<in-memory image>",
                output=str(square_video),
                fps=FPS,
                max_frames=FPS * DURATION,
                start_hold=1.0,
                end_hold=1.0,
                seed=seed,
                crf=18,
                preset="faster",
                size=SIZE,
            ),
            image_data=image_data,
            frame_transform=create_caption_frame_transform(),
        )

        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(square_video),
                "-f",
                "mp3",
                "-i",
                "pipe:0",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-t",
                str(DURATION),
                "-movflags",
                "+faststart",
                str(output_path),
            ],
            input=processed_audio,
            check=True,
        )

    print(f"Created {output_path}")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Album-cover image")
    parser.add_argument("audio", type=Path, help="Song MP3")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("album_reveal.mp4"),
        help="Output MP4 path (default: album_reveal.mp4)",
    )
    parser.add_argument("--seed", type=int, help="Random seed for repeatable reveals")
    args = parser.parse_args()

    for input_path in (args.image, args.audio):
        if not input_path.is_file():
            parser.error(f"input file does not exist: {input_path}")
        if input_path.resolve() == args.output.resolve():
            parser.error(f"output must differ from input: {input_path}")
    return args


def main() -> int:
    args = parse_args()
    try:
        create_album_video(
            args.image.read_bytes(),
            args.audio.read_bytes(),
            args.output,
            seed=args.seed,
        )
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
