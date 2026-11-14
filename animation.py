#!/usr/bin/env python3
"""Reveal an image by randomly refining largest-first mean-color regions.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageOps

OUTPUT_SIZE = 1024
logger = logging.getLogger(__name__)


def _mean_color(integral: np.ndarray, region: tuple[int, int, int, int]) -> np.ndarray:
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


def _load_image(image_data: bytes, size: int = OUTPUT_SIZE) -> np.ndarray:
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


def _allocate_snapshots(region_counts: list[int], budget: int) -> list[int]:
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


def _allocate_snapshot_holds(snapshot_count: int, extra_frames: int) -> list[int]:
    """Hold early snapshots longer, placing all extra time before the midpoint."""
    first_half = snapshot_count // 2
    weights = np.arange(first_half, 0, -1, dtype=np.float64)
    shares = extra_frames * weights / weights.sum()
    extra_holds = np.floor(shares).astype(np.int64)
    if remainder := extra_frames - int(extra_holds.sum()):
        order = np.argsort(-(shares - extra_holds), kind="stable")
        extra_holds[order[:remainder]] += 1

    holds = np.ones(snapshot_count, dtype=np.int64)
    holds[:first_half] += extra_holds
    return holds.tolist()


def render_animation(
    src_image: Path | str | bytes,
    output_path: Path | str,
    fps: int = 30,
    max_frames: int = 300,
    start_hold: float = 1.0,
    end_hold: float = 1.0,
    seed: int | None = None,
    crf: int = 18,
    preset: str = "medium",
    size: int = OUTPUT_SIZE,
    frame_transform: Callable[[np.ndarray], np.ndarray] | None = None,
    frame_time_transform: Callable[[np.ndarray, float], np.ndarray] | None = None,
    final_frame_transform: Callable[[np.ndarray], np.ndarray] | None = None,
    show_progress: bool = False,
) -> Path:
    if isinstance(src_image, str):
        src_image = Path(src_image)
    output_path = Path(output_path)

    if isinstance(src_image, Path) and output_path.resolve() == src_image.resolve():
        raise ValueError("Output and input paths must differ")
    if fps < 1:
        raise ValueError("--fps must be a positive integer")
    if size < 1:
        raise ValueError("--size must be a positive integer")
    if max_frames < 1:
        raise ValueError("--max-frames must be a positive integer")
    if start_hold < 0 or end_hold < 0:
        raise ValueError("Hold durations cannot be negative")

    image_data = src_image.read_bytes() if isinstance(src_image, Path) else src_image
    image = _load_image(image_data, size)
    height, width = image.shape[:2]
    max_depth = max((height - 1).bit_length(), (width - 1).bit_length())
    if max_depth < 1:
        raise ValueError("Image size must be at least 2x2")

    start_hold_frames = round(start_hold * fps)
    end_hold_frames = round(end_hold * fps)
    level_region_counts = [
        min(2**depth, height) * min(2**depth, width)
        for depth in range(1, max_depth + 1)
    ]
    snapshot_budget = max_frames - start_hold_frames - end_hold_frames
    if snapshot_budget < len(level_region_counts):
        raise ValueError(
            "--max-frames must leave room for at least one refinement frame per level "
            "after start/end holds"
        )
    midpoint_frame = (3 * max_frames + 3) // 4
    midpoint_after_start = midpoint_frame - start_hold_frames
    snapshot_count = 2 * (snapshot_budget - midpoint_after_start)
    snapshot_count = min(snapshot_count, snapshot_budget, sum(level_region_counts))
    snapshot_count = max(10, snapshot_count - snapshot_count % 2)
    snapshots_per_level = _allocate_snapshots(level_region_counts, snapshot_count)
    snapshot_holds = _allocate_snapshot_holds(
        snapshot_count,
        snapshot_budget - snapshot_count,
    )

    integral = np.pad(
        image.astype(np.uint64),
        ((1, 0), (1, 0), (0, 0)),
    ).cumsum(axis=0).cumsum(axis=1)

    canvas = np.empty_like(image)
    canvas[:] = _mean_color(integral, (0, 0, height, width))
    rng = np.random.default_rng(seed)
    total_operations = 1 + sum(level_region_counts)
    completed_operations = 1
    last_progress = -1
    frames_written = 0
    snapshots_written = 0

    def append(
        frame: np.ndarray,
        count: int = 1,
        *,
        frames_written: int,
        is_final_frame: bool = False,
    ) -> int:
        if frame_transform is not None:
            frame = frame_transform(frame)
        if is_final_frame and final_frame_transform is not None:
            frame = final_frame_transform(frame)

        # the timer
        remaining = count
        while remaining:
            if frame_time_transform is None:
                segment_count = remaining
                output_frame = frame
            else:
                frames_to_second_boundary = fps - frames_written % fps
                segment_count = min(remaining, frames_to_second_boundary)
                output_frame = frame_time_transform(frame, frames_written / fps)
            for _ in range(segment_count):
                writer.append_data(output_frame)
            frames_written += segment_count
            remaining -= segment_count
        return frames_written

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_params = [
        "-crf",
        str(crf),
        "-preset",
        preset,
        "-movflags",
        "+faststart",
    ]
    with imageio.get_writer(
        str(output_path),
        format="FFMPEG",
        mode="I",
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
        macro_block_size=1,
        ffmpeg_params=ffmpeg_params,
    ) as writer:
        frames_written = append(
            canvas,
            start_hold_frames,
            frames_written=frames_written,
        )

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
                canvas[y0:y1, x0:x1] = _mean_color(integral, (y0, x0, y1, x1))

                if index in snapshot_targets:
                    frames_written = append(
                        canvas,
                        snapshot_holds[snapshots_written],
                        frames_written=frames_written,
                    )
                    snapshots_written += 1

                completed_operations += 1
                progress = completed_operations * 100 // total_operations
                if show_progress and progress > last_progress and progress < 100:
                    print(
                        f"\rProgress: {progress:3d}%",
                        end="",
                        file=sys.stderr,
                        flush=True,
                    )
                    last_progress = progress

        if not np.array_equal(canvas, image):
            raise RuntimeError("Quadtree refinement did not reproduce the resized image")
        frames_written = append(
            image,
            end_hold_frames,
            frames_written=frames_written,
            is_final_frame=True,
        )

    print("\rProgress: 100%", file=sys.stderr)
    duration = frames_written / fps
    input_label = "<in-memory image>" if isinstance(src_image, bytes) else src_image
    logger.info("Input:       %s", input_label)
    logger.info("Image size:  %dx%d", width, height)
    logger.info(
        "Snapshots:   %d (halfway at about 75%% of clip duration)",
        snapshots_written,
    )
    logger.info("Frames:      %d (%.2fs at %d FPS)", frames_written, duration, fps)
    logger.info("Output:      %s", output_path)
    return output_path
