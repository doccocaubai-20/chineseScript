# Whisper trên Google Colab (thủ công)

Luồng:

```text
Local tạo WAV -> upload WAV vào Colab -> Colab tạo transcript.json
-> tải transcript.json về máy -> Import transcript.json trong web app
```

## Chạy trên Colab

Chọn `Runtime -> Change runtime type -> T4 GPU`, rồi chạy:

```python
!pip install -q faster-whisper
```

Upload WAV:

```python
from google.colab import files

uploaded = files.upload()
audio_path = next(iter(uploaded))
```

Chạy Whisper và tạo JSON:

```python
from faster_whisper import WhisperModel
import json

model = WhisperModel("small", device="cuda", compute_type="float16")
segments, info = model.transcribe(
    audio_path,
    language="zh",
    word_timestamps=True,
    vad_filter=True,
)

chunks = []
for segment in segments:
    chunks.append({
        "text": segment.text.strip(),
        "start": float(segment.start),
        "end": float(segment.end),
        "words": [
            {
                "text": word.word,
                "start": float(word.start),
                "end": float(word.end),
            }
            for word in (segment.words or [])
        ],
    })

with open("transcript.json", "w", encoding="utf-8") as output:
    json.dump({
        "language": info.language,
        "duration": info.duration,
        "chunks": chunks,
    }, output, ensure_ascii=False, indent=2)
```

Tải file về:

```python
files.download("transcript.json")
```

Trong app local, chọn video rồi bấm **Import transcript.json**. App sẽ tiếp tục
align, tạo Pinyin, dịch tiếng Việt và lưu database.
