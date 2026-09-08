# Learning JSON contract

The export is generated from persisted video and segment records:

```json
{
  "id": "video-id",
  "youtubeId": "VIDEO_ID",
  "title": "Original video title",
  "titleHanzi": "日常习惯",
  "level": 2,
  "topic": "Podcast",
  "channel": "Chinese Podcast Station",
  "durationSec": 595,
  "thumbnailUrl": "https://i.ytimg.com/vi/VIDEO_ID/hqdefault.jpg",
  "totalSentences": 1,
  "segments": [
    {
      "id": 1,
      "start": 0.55,
      "end": 3.61,
      "hanzi": "大家好，欢迎你来到今天的节目。",
      "pinyin": "dà jiā hǎo，huān yíng nǐ lái dào jīn tiān de jié mù。",
      "vi": "Chào mọi người, chào mừng bạn đến với chương trình hôm nay."
    }
  ]
}
```

## Invariants

- `start` and `end` are decimal seconds, never `HH:MM:SS` strings.
- `0 <= start < end <= durationSec`.
- Segments are sorted by `start`; IDs are sequential starting at `1`.
- `hanzi`, `pinyin`, and `vi` are non-empty strings.
- `totalSentences` equals `segments.length`.
- No duplicate segment is emitted.
- Pinyin is generated from the final Hanzi text and must be regenerated when Hanzi
  changes unless the user explicitly edits and saves Pinyin.
- Export is refused when validation has errors.
