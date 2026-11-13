#!/usr/bin/env python3
"""Create a 60-second reverse-to-forward guitar-fuzz and tremolo effect."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

OUTPUT_PATH = Path("processed.mp3")
DEFAULT_DURATION = 60.0


def _effect_filter_graph(duration: float) -> str:
    segment_duration = duration / 2
    effect_fade_duration = duration / 3
    fuzz = (
        "volume=12,asoftclip=type=hard:threshold=0.2:oversample=8,"
        "highpass=f=100,lowpass=f=5000"
    )
    effect_progress = (
        f"min(max(t/{effect_fade_duration:.9f},0),1)"
    )
    wet_volume = f"1-pow({effect_progress},2)"
    dry_volume = f"pow({effect_progress},2)"
    overall_progress = f"min(max(t/{duration:.9f},0),1)"
    overall_volume = f"0.01+0.99*pow({overall_progress},2)"
    segment = f"{segment_duration:.9f}"

    return ";".join(
        [
            "[0:a]asplit=2[reverse_input][forward_input]",
            f"[reverse_input]atrim=duration={segment},asetpts=PTS-STARTPTS,"
            "areverse,apad=whole_dur="
            f"{segment},atrim=duration={segment},{fuzz}[reverse_effect]",
            f"[forward_input]atrim=duration={segment},asetpts=PTS-STARTPTS,"
            f"apad=whole_dur={segment},atrim=duration={segment},"
            "asplit=2[wet_input][dry_input]",
            f"[wet_input]{fuzz},tremolo=f=8:d=0.98,"
            f"volume='{wet_volume}':eval=frame[wet]",
            f"[dry_input]volume='{dry_volume}':eval=frame[dry]",
            "[wet][dry]amix=inputs=2:duration=first:dropout_transition=0:"
            "normalize=0[forward_effect]",
            "[reverse_effect][forward_effect]concat=n=2:v=0:a=1[segments]",
            f"[segments]volume='{overall_volume}':eval=frame,"
            f"apad=whole_dur={duration},atrim=duration={duration}[output]",
        ]
    )


def process_audio(audio_data: bytes, *, duration: float = DEFAULT_DURATION) -> bytes:
    if shutil.which("ffmpeg") is None:
        raise FileNotFoundError("FFmpeg is required; install it and make sure it is on PATH")
    if duration <= 0:
        raise ValueError("Audio duration must be positive")

    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-filter_complex",
            _effect_filter_graph(duration),
            "-map",
            "[output]",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "4",
            "-f",
            "mp3",
            "pipe:1",
        ],
        input=audio_data,
        stdout=subprocess.PIPE,
        check=True,
    )
    return result.stdout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Song MP3")
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")
    if args.input.resolve() == OUTPUT_PATH.resolve():
        parser.error(f"input cannot be overwritten: {OUTPUT_PATH}")
    if shutil.which("ffmpeg") is None:
        parser.error("FFmpeg is required; install it and make sure it is on PATH")

    return args


def main() -> None:
    args = parse_args()
    output = process_audio(args.input.read_bytes())
    OUTPUT_PATH.write_bytes(output)
    print(f"Created {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
