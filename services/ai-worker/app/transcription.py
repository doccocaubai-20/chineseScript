from dataclasses import asdict, dataclass
import os
from pathlib import Path
import tempfile
import wave
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
        result: list[dict[str, Any]] = []
        chunk_duration = max(0, int(os.getenv("AUDIO_CHUNK_DURATION_SEC", "600")))
        if chunk_duration == 0:
            return self._transcribe_file(audio_path, 0.0)

        try:
            source = wave.open(audio_path, "rb")
        except (wave.Error, FileNotFoundError):
            return self._transcribe_file(audio_path, 0.0)

        with source:
            frame_rate = source.getframerate()
            frames_per_chunk = frame_rate * chunk_duration
            total_frames = source.getnframes()
            with tempfile.TemporaryDirectory(prefix="whisper-chunks-") as temporary_directory:
                chunk_index = 0
                while chunk_index * frames_per_chunk < total_frames:
                    start_frame = chunk_index * frames_per_chunk
                    source.setpos(start_frame)
                    frames = source.readframes(min(frames_per_chunk, total_frames - start_frame))
                    chunk_path = Path(temporary_directory) / f"chunk-{chunk_index:04d}.wav"
                    with wave.open(str(chunk_path), "wb") as chunk:
                        chunk.setnchannels(source.getnchannels())
                        chunk.setsampwidth(source.getsampwidth())
                        chunk.setframerate(frame_rate)
                        chunk.writeframes(frames)
                    result.extend(self._transcribe_file(str(chunk_path), start_frame / frame_rate))
                    chunk_index += 1
        return result

    def _transcribe_file(self, audio_path: str, offset: float) -> list[dict[str, Any]]:
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
                        start=float(word.start) + offset,
                        end=float(word.end) + offset,
                    )
                )
                for word in (segment.words or [])
            ]
            result.append(
                asdict(
                    TranscriptChunk(
                        text=segment.text.strip(),
                        start=float(segment.start) + offset,
                        end=float(segment.end) + offset,
                        words=words,
                    )
                )
            )
        return result
