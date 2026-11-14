#!/usr/bin/env python3
"""Create a 60-second vertical album-reveal video with PaulStretch audio.

Example:
    python video_gen.py cover.jpg song.mp3 --credit "Artist, year" "Title

A random frame from 17-31 seconds is saved beside the video as *_thumbnail.jpg.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Callable
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from animation import render_animation
from paul import paulstretch_mp3

FPS = 30
DURATION = 60
REVERSE_DURATION = 2
FORWARD_DURATION = DURATION - REVERSE_DURATION
CREDIT_START = FORWARD_DURATION - REVERSE_DURATION
REVERSE_FRAME_COUNT = FPS * REVERSE_DURATION
THUMBNAIL_START_SECOND = 17
THUMBNAIL_END_SECOND = 31
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


def create_bottom_panel_frame_transform(
    credit: str,
) -> Callable[[np.ndarray, float], np.ndarray]:
    if len(credit.splitlines()) != 2:
        raise ValueError("Credit must contain exactly two lines")
    font = ImageFont.truetype(str(font_path), size=84)
    credit_panel = render_text_panel(credit)

    def compose(frame: np.ndarray, elapsed_seconds: float) -> np.ndarray:
        composed = frame.copy()
        if elapsed_seconds >= CREDIT_START:
            composed[1500:] = credit_panel
        else:
            panel = Image.new("RGB", (SIZE, 420), "black")
            ImageDraw.Draw(panel).text(
                (SIZE // 2, 210),
                str(int(elapsed_seconds) + 1),
                font=font,
                fill=(72, 72, 72),
                anchor="mm",
            )
            composed[1500:] = np.asarray(panel)
        return composed

    return compose


def create_reverse_tail_video(
    forward_video_path: Path,
    output_path: Path,
    credit: str,
) -> Path:
    reverse_middle_path = output_path.with_name("reverse_middle.mp4")
    forward_frame_count = FPS * FORWARD_DURATION
    selected_frames = [
        round(index * (forward_frame_count - 1) / (REVERSE_FRAME_COUNT - 1))
        for index in range(REVERSE_FRAME_COUNT)
    ]
    select_expression = "+".join(f"eq(n,{index})" for index in selected_frames)
    filter_graph = (
        f"crop={SIZE}:{SIZE}:0:420,"
        f"select='{select_expression}',reverse,setpts=N/({FPS}*TB)"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(forward_video_path),
            "-vf",
            filter_graph,
            "-an",
            "-frames:v",
            str(REVERSE_FRAME_COUNT),
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "faster",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            str(reverse_middle_path),
        ],
        check=True,
    )

    caption_panel = render_text_panel(CAPTION, wrap_width=18)
    credit_panel = render_text_panel(credit).astype(np.float32)
    frames_written = 0
    writer_args = {
        "format": "FFMPEG",
        "mode": "I",
        "fps": FPS,
        "codec": "libx264",
        "pixelformat": "yuv420p",
        "macro_block_size": 1,
        "ffmpeg_params": ["-crf", "18", "-preset", "faster", "-movflags", "+faststart"],
    }
    with (
        imageio.get_reader(str(reverse_middle_path)) as reader,
        imageio.get_writer(str(output_path), **writer_args) as writer,
    ):
        for index, middle_frame in enumerate(reader):
            if index >= REVERSE_FRAME_COUNT:
                raise RuntimeError("Reverse tail contains too many frames")
            fade = 1 - index / (REVERSE_FRAME_COUNT - 1)
            composed = np.zeros((VIDEO_HEIGHT, SIZE, 3), dtype=np.uint8)
            composed[:420] = caption_panel
            composed[420:1500] = middle_frame
            composed[1500:] = (credit_panel * fade).astype(np.uint8)
            writer.append_data(composed)
            frames_written += 1

    if frames_written != REVERSE_FRAME_COUNT:
        raise RuntimeError(
            f"Reverse tail has {frames_written} frames; expected {REVERSE_FRAME_COUNT}"
        )
    return output_path


def create_loop_filter_complex() -> str:
    reverse_speed = FORWARD_DURATION / REVERSE_DURATION
    tempo_filters = []
    while reverse_speed > 2:
        tempo_filters.append("atempo=2")
        reverse_speed /= 2
    tempo_filters.append(f"atempo={reverse_speed:.9g}")
    tempo_chain = ",".join(tempo_filters)

    return (
        "[0:v]setpts=PTS-STARTPTS[forward_video];"
        "[1:v]setpts=PTS-STARTPTS[reverse_video];"
        "[forward_video][reverse_video]concat=n=2:v=1:a=0[video];"
        f"[2:a]atrim=duration={FORWARD_DURATION},asetpts=PTS-STARTPTS,"
        "asplit=2[forward_audio][reverse_source];"
        f"[reverse_source]areverse,{tempo_chain},"
        f"apad=whole_dur={REVERSE_DURATION},"
        f"atrim=duration={REVERSE_DURATION},asetpts=PTS-STARTPTS[reverse_audio];"
        "[forward_audio][reverse_audio]concat=n=2:v=0:a=1[audio]"
    )


def save_random_thumbnail(
    video_path: Path,
    *,
    seed: int | None = None,
) -> tuple[Path, float]:
    frame_index = int(
        np.random.default_rng(seed).integers(
            THUMBNAIL_START_SECOND * FPS,
            THUMBNAIL_END_SECOND * FPS + 1,
        )
    )
    timestamp = frame_index / FPS
    thumbnail_path = video_path.with_name(f"{video_path.stem}_thumbnail.jpg")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-ss",
            f"{timestamp:.6f}",
            "-map",
            "0:v:0",
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(thumbnail_path),
        ],
        check=True,
    )
    return thumbnail_path, timestamp


def create_short_video(
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
        reverse_video_path = Path(temporary_directory) / "reverse_tail.mp4"
        audio_input_path.write_bytes(audio_data)
        paulstretch_mp3(audio_input_path, processed_audio_path, factor=2.0)

        square_video = Path(temporary_directory) / "reveal.mp4"
        render_animation(
            argparse.Namespace(
                input="<in-memory image>",
                output=str(square_video),
                fps=FPS,
                max_frames=FPS * FORWARD_DURATION,
                start_hold=1.0,
                end_hold=1 / FPS,
                seed=seed,
                crf=18,
                preset="faster",
                size=SIZE,
            ),
            image_data=image_data,
            frame_transform=create_caption_frame_transform(),
            frame_time_transform=create_bottom_panel_frame_transform(credit),
        )
        create_reverse_tail_video(square_video, reverse_video_path, credit)

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
                str(reverse_video_path),
                "-i",
                str(processed_audio_path),
                "-filter_complex",
                create_loop_filter_complex(),
                "-map",
                "[video]",
                "-map",
                "[audio]",
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-preset",
                "faster",
                "-pix_fmt",
                "yuv420p",
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
        help="two credit lines shown from second 56 and faded out at the end",
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

    thumbnail_path = args.output.with_name(f"{args.output.stem}_thumbnail.jpg")
    for input_path in (args.image, args.audio):
        if not input_path.is_file():
            parser.error(f"input file does not exist: {input_path}")
        if input_path.resolve() == args.output.resolve():
            parser.error(f"output must differ from input: {input_path}")
        if input_path.resolve() == thumbnail_path.resolve():
            parser.error(f"thumbnail output must differ from input: {input_path}")
    return args


def main() -> int:
    args = parse_args()
    try:
        create_short_video(
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
