import json
import os
import re
from urllib import error, request


class TranslationProviderError(RuntimeError):
    pass


def _parse_json_content(content: str) -> list[dict]:
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    raw = fenced.group(1) if fenced else content
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise TranslationProviderError("Translation response must be a JSON array")
    return parsed


def translate_segments(segments: list[dict]) -> list[dict]:
    if not segments:
        return []
    batch_size = max(1, int(os.getenv("TRANSLATION_BATCH_SIZE", "8")))
    translated: list[dict] = []
    for start in range(0, len(segments), batch_size):
        translated.extend(_translate_batch(segments[start : start + batch_size]))
    return translated


def _translate_batch(segments: list[dict]) -> list[dict]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise TranslationProviderError("OPENAI_API_KEY is not configured")
    model = os.getenv("TRANSLATION_MODEL", "").strip()
    if not model:
        raise TranslationProviderError("TRANSLATION_MODEL is not configured")
    payload_segments = [
        {"id": segment.get("id"), "hanzi": str(segment.get("hanzi", ""))}
        for segment in segments
    ]
    prompt = (
        "Translate each Chinese learning segment into natural Vietnamese. "
        "Return only a JSON array with objects {\"id\": number, \"vi\": string}. "
        "Keep exactly one result for every input id, do not add information, and "
        "do not alter the ids.\n\n"
        f"Input segments:\n{json.dumps(payload_segments, ensure_ascii=False)}"
    )
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = json.dumps(
        {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise Chinese-to-Vietnamese translator.",
                },
                {"role": "user", "content": prompt},
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    client_request = request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(client_request, timeout=120) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        provider_body = exc.read().decode("utf-8", errors="replace").strip()
        if len(provider_body) > 500:
            provider_body = provider_body[:500] + "..."
        detail = provider_body or str(exc.reason)
        raise TranslationProviderError(
            f"Translation provider returned HTTP {exc.code}: {detail}"
        ) from exc
    except (error.URLError, TimeoutError) as exc:
        raise TranslationProviderError(f"Translation provider request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TranslationProviderError("Translation provider returned invalid JSON") from exc

    try:
        content = response_body["choices"][0]["message"]["content"]
        translations = _parse_json_content(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise TranslationProviderError("Translation provider returned invalid JSON content") from exc

    by_id: dict[int, str] = {}
    for item in translations:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            raise TranslationProviderError("Translation result has an invalid id")
        vi = str(item.get("vi", "")).strip()
        if not vi:
            raise TranslationProviderError(f"Translation is empty for segment {item['id']}")
        by_id[item["id"]] = vi

    result: list[dict] = []
    for segment in segments:
        segment_id = segment.get("id")
        if not isinstance(segment_id, int) or segment_id not in by_id:
            raise TranslationProviderError(f"Missing translation for segment {segment_id}")
        enriched = dict(segment)
        enriched["vi"] = by_id[segment_id]
        result.append(enriched)
    return result
