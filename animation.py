#!/usr/bin/env python3
"""Reveal an image by randomly refining largest-first mean-color regions.

Dependencies:
    pip install numpy Pillow imageio imageio-ffmpeg

Example:
    python mean_quadtree_reveal.py photo.jpg
    python mean_quadtree_reveal.py photo.jpg -o reveal.mp4 --seed 42
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageOps

OUTPUT_SIZE = 1024


def mean_color(integral: np.ndarray, region: tuple[int, int, int, int]) -> np.ndarray:
    """Return a rounded RGB mean for the half-open region (y0, x0, y1, x1)."""
    y0, x0, y1, x1 = region
    total = (
        integral[y1, x1]
        - integral[y0, x1]
        - integral[y1, x0]
        + integral[y0, x0]
    )
    area = (y1 - y0) * (x1 - x0)
    return np.rint(total / area).clip(0, 255).astype(np.uint8)


def load_image(image_data: bytes, size: int = OUTPUT_SIZE) -> np.ndarray:
    """Load, orient, composite transparency onto white, and resize to a square."""
    with Image.open(BytesIO(image_data)) as source:
        rgba = ImageOps.exif_transpose(source).convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        rgb = Image.alpha_composite(background, rgba).convert("RGB")
        resized = rgb.resize(
            (size, size),
            resample=Image.Resampling.LANCZOS,
        )
        return np.asarray(resized, dtype=np.uint8)


def allocate_snapshots(region_counts: list[int], budget: int) -> list[int]:
    """Distribute a total snapshot budget fairly without skipping levels."""
    allocations = [0] * len(region_counts)
    remaining = min(budget, sum(region_counts))

    while remaining:
        active = [
            index
            for index, count in enumerate(region_counts)
            if allocations[index] < count
        ]
        if not active:
            break
        base, extra = divmod(remaining, len(active))
        if base == 0:
            for index in active[:extra]:
                allocations[index] += 1
            break

        assigned = 0
        for rank, index in enumerate(active):
            requested = base + (rank < extra)
            added = min(requested, region_counts[index] - allocations[index])
            allocations[index] += added
            assigned += added
        remaining -= assigned

    return allocations


def allocate_snapshot_holds(snapshot_count: int, extra_frames: int) -> list[int]:
    """Hold early snapshots longer, placing all extra time before the midpoint."""
    first_half = snapshot_count // 2
    weights = np.arange(first_half, 0, -1, dtype=np.float64)
    shares = extra_frames * weights / weights.sum()
    extra_holds = np.floor(shares).astype(np.int64)
    remainder = extra_frames - int(extra_holds.sum())
    if remainder:
        order = np.argsort(-(shares - extra_holds), kind="stable")
        extra_holds[order[:remainder]] += 1

    holds = np.ones(snapshot_count, dtype=np.int64)
    holds[:first_half] += extra_holds
    return holds.tolist()


def render_animation(
    args: argparse.Namespace,
    *,
    image_data: bytes | None = None,
    frame_transform: Callable[[np.ndarray], np.ndarray] | None = None,
) -> Path:
    input_is_in_memory = image_data is not None
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_name(
        f"{input_path.stem}_quadtree_reveal.mp4"
    )

    if image_data is None and not input_path.is_file():
        raise FileNotFoundError(f"Input image not found: {input_path}")
    if image_data is None and output_path.resolve() == input_path.resolve():
        raise ValueError("Output must differ from input")
    if args.fps < 1:
        raise ValueError("--fps must be a positive integer")
    if args.size < 1:
        raise ValueError("--size must be a positive integer")
    if args.max_frames < 1:
        raise ValueError("--max-frames must be a positive integer")
    if args.start_hold < 0 or args.end_hold < 0:
        raise ValueError("Hold durations cannot be negative")

    if image_data is None:
        image_data = input_path.read_bytes()
    image = load_image(image_data, args.size)
    height, width = image.shape[:2]
    max_depth = max((height - 1).bit_length(), (width - 1).bit_length())
    if max_depth < 1:
        raise ValueError("Image size must be at least 2x2")

    start_hold_frames = round(args.start_hold * args.fps)
    end_hold_frames = round(args.end_hold * args.fps)
    level_region_counts = [
        min(2**depth, height) * min(2**depth, width)
        for depth in range(1, max_depth + 1)
    ]
    snapshot_budget = args.max_frames - start_hold_frames - end_hold_frames
    if snapshot_budget < len(level_region_counts):
        raise ValueError(
            "--max-frames must leave room for at least one refinement frame per level "
            "after start/end holds"
        )
    midpoint_frame = (3 * args.max_frames + 3) // 4
    midpoint_after_start = midpoint_frame - start_hold_frames
    snapshot_count = 2 * (snapshot_budget - midpoint_after_start)
    snapshot_count = min(snapshot_count, snapshot_budget, sum(level_region_counts))
    snapshot_count = max(10, snapshot_count - snapshot_count % 2)
    snapshots_per_level = allocate_snapshots(level_region_counts, snapshot_count)
    snapshot_holds = allocate_snapshot_holds(
        snapshot_count,
        snapshot_budget - snapshot_count,
    )

    integral = np.pad(
        image.astype(np.uint64),
        ((1, 0), (1, 0), (0, 0)),
    ).cumsum(axis=0).cumsum(axis=1)

    canvas = np.empty_like(image)
    canvas[:] = mean_color(integral, (0, 0, height, width))
    rng = np.random.default_rng(args.seed)
    total_operations = 1 + sum(level_region_counts)
    completed_operations = 1
    last_progress = -1
    frames_written = 0
    snapshots_written = 0

    def append(frame: np.ndarray, count: int = 1) -> None:
        nonlocal frames_written
        if frame_transform is not None:
            frame = frame_transform(frame)
        for _ in range(count):
            writer.append_data(frame)
            frames_written += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_params = [
        "-crf",
        str(args.crf),
        "-preset",
        args.preset,
        "-movflags",
        "+faststart",
    ]
    with imageio.get_writer(
        str(output_path),
        format="FFMPEG",
        mode="I",
        fps=args.fps,
        codec="libx264",
        pixelformat="yuv420p",
        macro_block_size=1,
        ffmpeg_params=ffmpeg_params,
    ) as writer:
        append(canvas, start_hold_frames)

        # Process each region serially, with randomized tie-breaking within a level.
        for depth, (region_count, snapshot_count) in enumerate(
            zip(level_region_counts, snapshots_per_level),
            start=1,
        ):
            grid_size = 2**depth
            grid_rows = min(grid_size, height)
            grid_columns = min(grid_size, width)
            order = rng.permutation(region_count)
            snapshot_targets = {
                (index * region_count + snapshot_count - 1) // snapshot_count
                for index in range(1, snapshot_count + 1)
            }

            for index, region_id in enumerate(order, start=1):
                row, column = divmod(int(region_id), grid_columns)
                y0 = row * height // grid_rows
                x0 = column * width // grid_columns
                y1 = (row + 1) * height // grid_rows
                x1 = (column + 1) * width // grid_columns
                canvas[y0:y1, x0:x1] = mean_color(integral, (y0, x0, y1, x1))

                if index in snapshot_targets:
                    append(canvas, snapshot_holds[snapshots_written])
                    snapshots_written += 1

                completed_operations += 1
                progress = completed_operations * 100 // total_operations
                if progress > last_progress and progress < 100:
                    print(
                        f"\rProgress: {progress:3d}%",
                        end="",
                        file=sys.stderr,
                        flush=True,
                    )
                    last_progress = progress

        if not np.array_equal(canvas, image):
            raise RuntimeError("Quadtree refinement did not reproduce the resized image")
        append(image, end_hold_frames)

    print("\rProgress: 100%", file=sys.stderr)
    duration = frames_written / args.fps
    input_label = "<in-memory image>" if input_is_in_memory else input_path
    print(f"Input:       {input_label}")
    print(f"Image size:  {width}x{height}")
    print(f"Snapshots:   {snapshots_written} (halfway at about 75% of clip duration)")
    print(f"Frames:      {frames_written} ({duration:.2f}s at {args.fps} FPS)")
    print(f"Output:      {output_path}")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reveal an image by randomly refining largest-first mean-color regions."
    )
    parser.add_argument("input", help="Input image (any format supported by Pillow)")
    parser.add_argument(
        "-o",
        "--output",
        help="Output MP4 path (default: <input>_quadtree_reveal.mp4)",
    )
    parser.add_argument("--fps", type=int, default=30, help="Output frame rate (default: 30)")
    parser.add_argument(
        "--size",
        type=int,
        default=OUTPUT_SIZE,
        help=f"Square output size in pixels (default: {OUTPUT_SIZE})",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=1800,
        help=(
            "Maximum total output frames, including start/end holds (default: 1800); "
            "snapshots are distributed across refinement levels"
        ),
    )
    parser.add_argument(
        "--start-hold",
        type=float,
        default=1.0,
        help="Seconds to hold the single-color start frame (default: 1)",
    )
    parser.add_argument(
        "--end-hold",
        type=float,
        default=1.0,
        help="Seconds to hold the completed image (default: 1)",
    )
    parser.add_argument("--seed", type=int, help="Random seed for repeatable tie-breaking")
    parser.add_argument("--crf", type=int, default=18, help="H.264 quality (default: 18)")
    parser.add_argument(
        "--preset",
        default="faster",
        choices=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ],
        help="H.264 encoding speed/size trade-off (default: faster)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        render_animation(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
