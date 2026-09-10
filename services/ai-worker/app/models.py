from enum import Enum

from pydantic import BaseModel, HttpUrl


class ProcessingStep(str, Enum):
    INGESTING = "INGESTING"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    TRANSCRIBING = "TRANSCRIBING"
    ALIGNING = "ALIGNING"
    GENERATING_PINYIN = "GENERATING_PINYIN"
    TRANSLATING = "TRANSLATING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"


class WorkerJobRequest(BaseModel):
    job_id: str
    video_id: str
    source_url: HttpUrl
    callback_url: HttpUrl


class YouTubeMetadata(BaseModel):
    youtube_id: str
    title: str
    channel: str | None = None
    duration_sec: float | None = None
    thumbnail_url: HttpUrl | None = None
    source_url: HttpUrl


class YouTubeMetadataRequest(BaseModel):
    source_url: HttpUrl


class YouTubeDownloadRequest(BaseModel):
    source_url: HttpUrl
    output_directory: str
    source_type: str = "YOUTUBE"


class AudioExtractionRequest(BaseModel):
    media_path: str
    output_directory: str


class TranscriptionRequest(BaseModel):
    audio_path: str


class TranscriptionResponse(BaseModel):
    audio_path: str
    language: str
    chunks: list[dict]


class AlignmentRequest(BaseModel):
    chunks: list[dict]


class AlignmentResponse(BaseModel):
    segments: list[dict]


class PinyinRequest(BaseModel):
    segments: list[dict]


class PinyinResponse(BaseModel):
    segments: list[dict]


class TranslationRequest(BaseModel):
    segments: list[dict]


class TranslationResponse(BaseModel):
    segments: list[dict]


class ExportRequest(BaseModel):
    video: dict
    segments: list[dict]


class ValidationResponse(BaseModel):
    valid: bool
    errors: list[str]
