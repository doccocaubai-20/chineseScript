from dataclasses import asdict, dataclass
import os
from typing import Any

from faster_whisper import WhisperModel


@dataclass(frozen=True)
class WordTimestamp:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class TranscriptChunk:
    text: str
    start: float
    end: float
    words: list[WordTimestamp]


class FasterWhisperProvider:
    def __init__(self) -> None:
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                os.getenv("WHISPER_MODEL", "small"),
                device=os.getenv("WHISPER_DEVICE", "cpu"),
                compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            )
        return self._model

    def transcribe(self, audio_path: str) -> list[dict[str, Any]]:
        segments, _ = self._get_model().transcribe(
            audio_path,
            language="zh",
            word_timestamps=True,
            vad_filter=True,
        )
        result: list[dict[str, Any]] = []
        for segment in segments:
            words = [
                asdict(
                    WordTimestamp(
                        text=word.word,
                        start=float(word.start),
                        end=float(word.end),
                    )
                )
                for word in (segment.words or [])
            ]
            result.append(
                asdict(
                    TranscriptChunk(
                        text=segment.text.strip(),
                        start=float(segment.start),
                        end=float(segment.end),
                        words=words,
                    )
                )
            )
        return result
