import re
import os
from dataclasses import asdict, dataclass
from typing import Any


SENTENCE_ENDINGS = set("。！？!?")
PUNCTUATION_REPLACEMENTS = str.maketrans({",": "，", "?": "？", "!": "！"})


@dataclass(frozen=True)
class AlignedSegment:
    start: float
    end: float
    hanzi: str


def _clean_hanzi(text: str) -> str:
    cleaned = re.sub(r"\s+", "", text).translate(PUNCTUATION_REPLACEMENTS)
    if cleaned and cleaned[-1] not in SENTENCE_ENDINGS:
        cleaned += "。"
    return cleaned


def align_sentences(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aligned: list[AlignedSegment] = []
    current_words: list[dict[str, Any]] = []
    max_duration = max(5.0, float(os.getenv("MAX_SEGMENT_DURATION_SEC", "20")))
    max_characters = max(10, int(os.getenv("MAX_SEGMENT_CHARACTERS", "45")))

    def flush() -> None:
        if not current_words:
            return
        text = _clean_hanzi("".join(str(word.get("text", "")) for word in current_words))
        if text:
            aligned.append(
                AlignedSegment(
                    start=float(current_words[0]["start"]),
                    end=float(current_words[-1]["end"]),
                    hanzi=text,
                )
            )
        current_words.clear()

    for chunk in chunks:
        words = chunk.get("words") or []
        if not words:
            flush()
            text = _clean_hanzi(str(chunk.get("text", "")))
            if text and float(chunk["start"]) < float(chunk["end"]):
                aligned.append(
                    AlignedSegment(
                        start=float(chunk["start"]),
                        end=float(chunk["end"]),
                        hanzi=text,
                    )
                )
            continue

        for word in words:
            if current_words:
                previous_end = float(current_words[-1].get("end", 0))
                current_start = float(current_words[0].get("start", 0))
                current_text = "".join(str(item.get("text", "")) for item in current_words)
                if (
                    float(word.get("start", previous_end)) - previous_end >= 0.8
                    or float(word.get("end", current_start)) - current_start >= max_duration
                    or len(current_text) >= max_characters
                ):
                    flush()
            current_words.append(word)
            if any(mark in str(word.get("text", "")) for mark in SENTENCE_ENDINGS):
                flush()
    flush()

    result: list[dict[str, Any]] = []
    previous_end = -1.0
    for segment in aligned:
        start = max(0.0, segment.start)
        end = max(start, segment.end)
        if end <= start or start < previous_end - 0.25:
            continue
        result.append(
            {
                "id": len(result) + 1,
                "start": round(start, 3),
                "end": round(end, 3),
                "hanzi": segment.hanzi,
            }
        )
        previous_end = end
    return result
