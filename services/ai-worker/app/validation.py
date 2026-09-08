import re
from typing import Any


def validate_learning_json(video: dict[str, Any], segments: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    duration = video.get("durationSec")
    if not isinstance(duration, (int, float)) or duration <= 0:
        errors.append("durationSec must be a positive number")

    seen: set[tuple[Any, Any, Any]] = set()
    previous_start = -1.0
    previous_end = -1.0
    for index, segment in enumerate(segments, start=1):
        prefix = f"segments[{index - 1}]"
        if segment.get("id") != index:
            errors.append(f"{prefix}.id must be {index}")
        start = segment.get("start")
        end = segment.get("end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            errors.append(f"{prefix}.start and end must be numbers")
            continue
        if start >= end:
            errors.append(f"{prefix}.start must be less than end")
        if start < 0 or (isinstance(duration, (int, float)) and end > duration):
            errors.append(f"{prefix} timestamp must be inside video duration")
        if start < previous_start:
            errors.append(f"{prefix} is not sorted by start")
        if start < previous_end - 0.25:
            errors.append(f"{prefix} overlaps the previous segment excessively")
        previous_start = start
        previous_end = max(previous_end, end)

        hanzi = str(segment.get("hanzi", "")).strip()
        pinyin = str(segment.get("pinyin", "")).strip()
        vi = str(segment.get("vi", "")).strip()
        if not hanzi:
            errors.append(f"{prefix}.hanzi cannot be empty")
        if not pinyin:
            errors.append(f"{prefix}.pinyin cannot be empty")
        if not vi:
            errors.append(f"{prefix}.vi cannot be empty")
        duplicate_key = (start, end, hanzi)
        if duplicate_key in seen:
            errors.append(f"{prefix} duplicates an earlier segment")
        seen.add(duplicate_key)

        if not re.search(r"[a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]", pinyin):
            errors.append(f"{prefix}.pinyin must contain Latin letters or tone marks")

    if video.get("totalSentences") != len(segments):
        errors.append("totalSentences must equal segments.length")
    return errors


def build_learning_json(video: dict[str, Any], segments: list[dict[str, Any]]) -> dict[str, Any]:
    errors = validate_learning_json(video, segments)
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "id": video.get("id"),
        "youtubeId": video.get("youtubeId"),
        "title": video.get("title"),
        "titleHanzi": video.get("titleHanzi"),
        "level": video.get("level"),
        "topic": video.get("topic"),
        "channel": video.get("channel"),
        "durationSec": video.get("durationSec"),
        "thumbnailUrl": video.get("thumbnailUrl"),
        "totalSentences": len(segments),
        "segments": segments,
    }
