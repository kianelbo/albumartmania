#!/usr/bin/env python3
"""Process an MP3, optionally reversing, muffling, and/or slowing it.

Requires FFmpeg to be installed and available on PATH.

Example:
    python audio.py song.mp3
    python audio.py song.mp3 --reverse --muffle --half-speed
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

OUTPUT_PATH = Path("muffled.mp3")


def _measure_duration(audio_data: bytes) -> float:
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            "pipe:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "8000",
            "-f",
            "s16le",
            "pipe:1",
        ],
        input=audio_data,
        stdout=subprocess.PIPE,
        check=True,
    )
    duration = len(result.stdout) / (8000 * 2)
    if duration <= 0:
        raise ValueError("Audio duration must be positive")
    return duration


def _muffle_filter_graph(
    processing_filters: list[str],
    ramp_duration: float,
    output_duration: float | None,
) -> str:
    if ramp_duration <= 1:
        wet_volume, dry_volume = "0", "1"
    else:
        progress = f"min(max(t/{ramp_duration - 1:.9f},0),1)"
        dry_volume = f"pow({progress},2)"
        wet_volume = f"1-{dry_volume}"

    graph = []
    prefix = ",".join(processing_filters)
    if prefix:
        graph.append(f"[0:a]{prefix}[source]")
        source = "[source]"
    else:
        source = "[0:a]"
    graph.extend(
        [
            f"{source}asplit=2[wet_source][dry_source]",
            "[wet_source]highpass=f=80,lowpass=f=350,"
            f"volume='{wet_volume}':eval=frame[wet]",
            f"[dry_source]volume='{dry_volume}':eval=frame[dry]",
            "[wet][dry]amix=inputs=2:duration=longest:dropout_transition=0:"
            "normalize=0[mixed]",
        ]
    )
    if output_duration is not None:
        graph.append(
            f"[mixed]apad=whole_dur={output_duration},"
            f"atrim=duration={output_duration}[output]"
        )
    else:
        graph.append("[mixed]anull[output]")
    return ";".join(graph)


def process_audio(
    audio_data: bytes,
    *,
    muffle: bool = False,
    half_speed: bool = False,
    reverse: bool = False,
    duration: float | None = None,
) -> bytes:
    if shutil.which("ffmpeg") is None:
        raise FileNotFoundError("FFmpeg is required; install it and make sure it is on PATH")
    if duration is not None and duration <= 0:
        raise ValueError("Audio duration must be positive")

    filters = []
    if half_speed:
        filters.append("atempo=0.5")
    if reverse:
        filters.append("areverse")

    use_filter_graph = muffle
    if muffle:
        processed_duration = _measure_duration(audio_data) * (
            2 if half_speed else 1
        )
        if duration is not None:
            processed_duration = min(processed_duration, duration)
    if duration is not None:
        if not use_filter_graph:
            filters.extend(
                [f"apad=whole_dur={duration}", f"atrim=duration={duration}"]
            )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-vn",
    ]
    if use_filter_graph:
        command.extend(
            [
                "-filter_complex",
                _muffle_filter_graph(filters, processed_duration, duration),
                "-map",
                "[output]",
            ]
        )
    elif filters:
        command.extend(["-af", ",".join(filters)])
    command.extend(
        [
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "4",
            "-f",
            "mp3",
            "pipe:1",
        ]
    )
    result = subprocess.run(
        command,
        input=audio_data,
        stdout=subprocess.PIPE,
        check=True,
    )
    return result.stdout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="MP3 file to process")
    parser.add_argument(
        "--muffle",
        action="store_true",
        help="start heavily muffled and fade to normal over the track",
    )
    parser.add_argument(
        "--half-speed",
        action="store_true",
        help="slow playback to 0.5x while preserving pitch",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="reverse playback",
    )
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
    output = process_audio(
        args.input.read_bytes(),
        muffle=args.muffle,
        half_speed=args.half_speed,
        reverse=args.reverse,
    )
    OUTPUT_PATH.write_bytes(output)
    print(f"Created {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
