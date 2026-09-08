import re

from pypinyin import Style, lazy_pinyin


def generate_pinyin(hanzi: str) -> str:
    if not hanzi.strip():
        raise ValueError("Hanzi cannot be empty")

    syllables = lazy_pinyin(
        hanzi,
        style=Style.TONE,
        neutral_tone_with_five=True,
        errors=lambda item: list(item),
    )
    result: list[str] = []
    for syllable in syllables:
        if re.fullmatch(r"[\u4e00-\u9fff]", syllable):
            result.append(syllable)
        elif re.fullmatch(r"[，。！？、；：,.!?;:\s]", syllable):
            result.append(syllable)
        else:
            result.append(syllable)
    return " ".join(result).replace("  ", " ").strip()


def add_pinyin(segments: list[dict]) -> list[dict]:
    result: list[dict] = []
    for segment in segments:
        hanzi = str(segment.get("hanzi", "")).strip()
        if not hanzi:
            raise ValueError(f"Segment {segment.get('id', '?')} has empty Hanzi")
        enriched = dict(segment)
        enriched["pinyin"] = generate_pinyin(hanzi)
        result.append(enriched)
    return result
