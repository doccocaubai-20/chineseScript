from pathlib import Path
import os

from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from yt_dlp import YoutubeDL

from .media import extract_audio
from .models import (
    AlignmentRequest,
    AlignmentResponse,
    AudioExtractionRequest,
    TranscriptionRequest,
    TranscriptionResponse,
    YouTubeMetadata,
    YouTubeDownloadRequest,
    YouTubeMetadataRequest,
    WorkerJobRequest,
    PinyinRequest,
    PinyinResponse,
    TranslationRequest,
    TranslationResponse,
    ExportRequest,
    ValidationResponse,
)
from .pinyin import add_pinyin
from .segmentation import align_sentences
from .translation import TranslationProviderError, translate_segments
from .transcription import FasterWhisperProvider
from .validation import build_learning_json, validate_learning_json

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

app = FastAPI(title="Chinese Video AI Worker", version="0.1.0")
transcription_provider = FasterWhisperProvider()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs")
def accept_job(request: WorkerJobRequest) -> dict[str, str]:
    # Processing is intentionally not implemented until the provider contracts are wired.
    return {"job_id": request.job_id, "status": "accepted"}


@app.post("/youtube/metadata", response_model=YouTubeMetadata)
def youtube_metadata(request: YouTubeMetadataRequest) -> YouTubeMetadata:
    source_url = str(request.source_url)
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(source_url, download=False)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Unable to read YouTube metadata: {error}") from error

    youtube_id = info.get("id")
    title = info.get("title")
    if not youtube_id or not title:
        raise HTTPException(status_code=422, detail="YouTube metadata did not include an id and title")

    return YouTubeMetadata(
        youtube_id=youtube_id,
        title=title,
        channel=info.get("channel") or info.get("uploader"),
        duration_sec=info.get("duration"),
        thumbnail_url=info.get("thumbnail"),
        source_url=source_url,
    )


@app.post("/youtube/download")
def youtube_download(request: YouTubeDownloadRequest) -> dict[str, str]:
    output_directory = Path(request.output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    try:
        with YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "socket_timeout": 60,
                "retries": 5,
                "fragment_retries": 5,
                "file_access_retries": 3,
                "concurrent_fragment_downloads": 1,
                "format": (
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"
                    if request.source_type == "TIKTOK"
                    else "bestaudio[ext=m4a]/bestaudio/best"
                ),
                "merge_output_format": "mp4",
                "outtmpl": str(
                    output_directory
                    / (
                        "%(id)s.video.%(ext)s"
                        if request.source_type == "TIKTOK"
                        else "%(id)s.audio.%(ext)s"
                    )
                ),
            }
        ) as ydl:
            info = ydl.extract_info(str(request.source_url), download=True)
            prepared_path = Path(ydl.prepare_filename(info)).resolve()
            if request.source_type == "TIKTOK":
                candidates = sorted(output_directory.glob(f"{info['id']}.video.*"))
                downloaded_path = (candidates[-1] if candidates else prepared_path).resolve()
            else:
                downloaded_path = prepared_path
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Unable to download media: {error}") from error

    if not downloaded_path.is_file():
        raise HTTPException(status_code=500, detail="yt-dlp completed without creating a media file")

    max_size_mb = float(os.getenv("MAX_VIDEO_SIZE_MB", "256"))
    if downloaded_path.stat().st_size > max_size_mb * 1024 * 1024:
        downloaded_path.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail=f"Downloaded media exceeds {max_size_mb:g} MB")

    return {"youtube_id": str(info["id"]), "media_path": str(downloaded_path)}


@app.post("/media/extract-audio")
def extract_audio_endpoint(request: AudioExtractionRequest) -> dict[str, str]:
    try:
        audio_path = extract_audio(request.media_path, request.output_directory)
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"audio_path": audio_path}


@app.post("/transcribe", response_model=TranscriptionResponse)
def transcribe(request: TranscriptionRequest) -> TranscriptionResponse:
    audio_path = Path(request.audio_path).resolve()
    if not audio_path.is_file():
        raise HTTPException(
            status_code=422,
            detail=f"Audio file does not exist: {audio_path}",
        )
    try:
        chunks = transcription_provider.transcribe(str(audio_path))
    except (FileNotFoundError, RuntimeError, OSError, ValueError) as error:
        raise HTTPException(
            status_code=422,
            detail=f"Transcription failed for {audio_path}: {error}",
        ) from error
    return TranscriptionResponse(
        audio_path=request.audio_path,
        language="zh",
        chunks=chunks,
    )


@app.post("/align", response_model=AlignmentResponse)
def align(request: AlignmentRequest) -> AlignmentResponse:
    return AlignmentResponse(segments=align_sentences(request.chunks))


@app.post("/pinyin", response_model=PinyinResponse)
def pinyin(request: PinyinRequest) -> PinyinResponse:
    try:
        return PinyinResponse(segments=add_pinyin(request.segments))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/translate", response_model=TranslationResponse)
def translate(request: TranslationRequest) -> TranslationResponse:
    try:
        return TranslationResponse(segments=translate_segments(request.segments))
    except TranslationProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/validate", response_model=ValidationResponse)
def validate(request: ExportRequest) -> ValidationResponse:
    errors = validate_learning_json(request.video, request.segments)
    return ValidationResponse(valid=not errors, errors=errors)


@app.post("/export/json")
def export_json(request: ExportRequest) -> dict:
    try:
        return build_learning_json(request.video, request.segments)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
