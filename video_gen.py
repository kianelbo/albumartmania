#!/usr/bin/env python3
"""Create a 60-second vertical album-reveal video with PaulStretch audio.

Example:
    python video_gen.py cover.jpg song.mp3 --credit "Artist, year" "Title
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from animation import render_animation
from paul import paulstretch_mp3

FPS = 30
DURATION = 60
SIZE = 1080
VIDEO_HEIGHT = 1920
CAPTION = "How soon can you guess the album?"
font_path = Path(__file__).resolve().parent / "assets" / "OLDSH___.ttf"


def render_text_panel(text: str, *, wrap_width: int | None = None) -> np.ndarray:
    if wrap_width is not None:
        text = textwrap.fill(text, width=wrap_width)
    lines = text.splitlines()
    stroke_width = 2
    font = None
    for size in range(90, 8, -2):
        candidate = ImageFont.truetype(str(font_path), size=size)
        line_widths = [
            candidate.getlength(line) + 2 * stroke_width
            for line in lines
        ]
        if max(line_widths) <= SIZE - 100:
            font = candidate
            break
    if font is None:
        raise ValueError("Text is too long to fit in the banner")

    overlay = Image.new("RGBA", (SIZE, 420), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).multiline_text(
        (SIZE // 2, 210),
        text,
        font=font,
        fill="white",
        anchor="mm",
        align="center",
        spacing=8,
        stroke_width=stroke_width,
        stroke_fill="white",
    )
    italic = overlay.transform(
        overlay.size,
        Image.Transform.AFFINE,
        (1, 0.12, -50, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )
    banner = Image.alpha_composite(Image.new("RGBA", overlay.size, "black"), italic)
    return np.asarray(banner.convert("RGB"))


def create_caption_frame_transform() -> Callable[[np.ndarray], np.ndarray]:
    header = render_text_panel(CAPTION, wrap_width=18)

    def compose(frame: np.ndarray) -> np.ndarray:
        composed = np.zeros((VIDEO_HEIGHT, SIZE, 3), dtype=np.uint8)
        composed[:420] = header
        composed[420:1500] = frame
        return composed

    return compose


def create_credit_frame_transform(credit: str) -> Callable[[np.ndarray], np.ndarray]:
    if len(credit.splitlines()) != 2:
        raise ValueError("Credit must contain exactly two lines")
    credit_panel = render_text_panel(credit)

    def compose(frame: np.ndarray) -> np.ndarray:
        composed = frame.copy()
        composed[1500:] = credit_panel
        return composed

    return compose


def create_timer_frame_transform() -> Callable[[np.ndarray, float], np.ndarray]:
    font = ImageFont.truetype(str(font_path), size=84)

    def compose(frame: np.ndarray, elapsed_seconds: float) -> np.ndarray:
        if elapsed_seconds >= DURATION - 2:
            return frame

        panel = Image.new("RGB", (SIZE, 420), "black")
        ImageDraw.Draw(panel).text(
            (SIZE // 2, 210),
            str(int(elapsed_seconds) + 1),
            font=font,
            fill=(72, 72, 72),
            anchor="mm",
        )
        composed = frame.copy()
        composed[1500:] = np.asarray(panel)
        return composed

    return compose


def create_album_video(
    image_data: bytes,
    audio_data: bytes,
    output_path: Path,
    *,
    credit: str,
    seed: int | None = None,
) -> Path:
    if len(credit.splitlines()) != 2:
        raise ValueError("Credit must contain exactly two lines")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temporary_directory:
        audio_input_path = Path(temporary_directory) / "input.mp3"
        processed_audio_path = Path(temporary_directory) / "stretched.mp3"
        audio_input_path.write_bytes(audio_data)
        paulstretch_mp3(audio_input_path, processed_audio_path, factor=2.0)

        square_video = Path(temporary_directory) / "reveal.mp4"
        render_animation(
            argparse.Namespace(
                input="<in-memory image>",
                output=str(square_video),
                fps=FPS,
                max_frames=FPS * DURATION,
                start_hold=1.0,
                end_hold=2.0,
                seed=seed,
                crf=18,
                preset="faster",
                size=SIZE,
            ),
            image_data=image_data,
            frame_transform=create_caption_frame_transform(),
            frame_time_transform=create_timer_frame_transform(),
            final_frame_transform=create_credit_frame_transform(credit),
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
                "-i",
                str(processed_audio_path),
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
            check=True,
        )

    print(f"Created {output_path}")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Album-cover image")
    parser.add_argument("audio", type=Path, help="Song MP3")
    parser.add_argument(
        "--credit",
        nargs=2,
        required=True,
        metavar=("ARTIST_YEAR", "TITLE"),
        help="two credit lines shown during the final two seconds",
    )
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
            credit="\n".join(args.credit),
            seed=args.seed,
        )
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
