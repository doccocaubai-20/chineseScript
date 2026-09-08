import subprocess
from pathlib import Path


def extract_audio(input_path: str, output_directory: str) -> str:
    source = Path(input_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Media file does not exist: {source}")

    destination_directory = Path(output_directory).resolve()
    destination_directory.mkdir(parents=True, exist_ok=True)
    destination = destination_directory / f"{source.stem}.wav"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError("FFmpeg is not installed or is not available on PATH") from error

    if completed.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {completed.stderr[-1000:]}")
    return str(destination)
