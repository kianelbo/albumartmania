
import argparse
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from paulstretch import stretch


SAMPLE_RATE = 44100
CHANNELS = 2


def decode_mp3(filename):
    """Decode an MP3 into stereo float32 samples using FFmpeg."""
    command = [
        "ffmpeg", "-v", "error",
        "-i", str(filename),
        "-f", "f32le",
        "-acodec", "pcm_f32le",
        "-ar", str(SAMPLE_RATE),
        "-ac", str(CHANNELS),
        "pipe:1"
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True
    )

    audio = np.frombuffer(result.stdout, dtype="<f4")

    if audio.size == 0 or audio.size % CHANNELS:
        raise ValueError("Could not decode valid stereo audio.")

    return audio.reshape(-1, CHANNELS).copy()


def nearest_power_of_two(value):
    return 1 << round(math.log2(value))


def encode_mp3(audio, filename, echo=False):
    """Encode float32 stereo audio into a high-quality MP3."""
    with tempfile.TemporaryDirectory() as temp_dir:
        raw_file = Path(temp_dir) / "audio.raw"

        audio.astype("<f4", copy=False).tofile(raw_file)

        command = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "f32le",
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            "-i", str(raw_file),
        ]

        if echo:
            command += [
                "-af",
                "aecho=0.8:0.16:650|1100|1800:0.10|0.07|0.05"
            ]

        command += [
            "-c:a", "libmp3lame",
            "-q:a", "2",
            str(filename)
        ]

        subprocess.run(command, check=True)


def paulstretch_mp3(
    input_file,
    output_file,
    factor=2.0,
    window_seconds=1.0,
    seed=42,
    echo=False
):
    if factor <= 1:
        raise ValueError("Stretch factor must be greater than 1.")

    print("Decoding input...")
    audio = decode_mp3(input_file)

    original_frames = len(audio)
    expected_frames = round(original_frames * factor)

    print(f"Original duration: {original_frames / SAMPLE_RATE:.1f}s")
    print(f"Stretch factor: {factor}x")
    print(f"Expected duration: {expected_frames / SAMPLE_RATE:.1f}s")

    # Convert window duration to a suitable FFT size.
    window_size = nearest_power_of_two(
        max(2048, round(window_seconds * SAMPLE_RATE))
    )

    print(f"FFT window size: {window_size}")
    print("Applying PaulStretch...")

    # Reproducible random phase generation.
    np.random.seed(seed)

    stretched = stretch(
        audio,
        stretch_factor=factor,
        window_size=window_size
    )

    # Trim to the exact target duration.
    stretched = stretched[:expected_frames]

    # Prevent clipping and normalize output peak.
    peak = 0.0

    for start in range(0, len(stretched), 1_000_000):
        block = stretched[start:start + 1_000_000]
        peak = max(peak, float(np.max(np.abs(block))))

    if peak < 1e-9:
        raise ValueError("Output audio is silent.")

    stretched *= 0.90 / peak

    Path(output_file).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    print("Encoding MP3...")
    encode_mp3(stretched, output_file, echo=echo)

    print(f"Finished: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create ambient music using PaulStretch."
    )

    parser.add_argument("input")
    parser.add_argument("output")

    parser.add_argument(
        "--factor",
        type=float,
        default=8.0,
        help="Stretch factor (default: 8)"
    )

    parser.add_argument(
        "--window",
        type=float,
        default=0.75,
        help="FFT window duration in seconds (default: 0.75)"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42
    )

    parser.add_argument(
        "--echo",
        action="store_true",
        help="Add a subtle multi-tap echo after stretching"
    )

    args = parser.parse_args()

    paulstretch_mp3(
        args.input,
        args.output,
        factor=args.factor,
        window_seconds=args.window,
        seed=args.seed,
        echo=args.echo
    )
