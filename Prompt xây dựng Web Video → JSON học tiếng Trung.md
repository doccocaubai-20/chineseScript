Bạn là một Senior Full-Stack Engineer + AI Engineer. Hãy xây dựng cho tôi một web application có chức năng chính:

**VIDEO → TRANSCRIPT → SEGMENTS → PINYIN → TIẾNG VIỆT → JSON**

Mục tiêu của hệ thống là biến một video tiếng Trung thành dữ liệu bài học tiếng Trung có cấu trúc JSON.

## 1. INPUT

Web phải hỗ trợ 2 loại input:

### A. Upload video MP4
Người dùng có thể upload file `.mp4`.

### B. YouTube URL
Người dùng nhập URL YouTube, ví dụ:

https://www.youtube.com/watch?v=aw_zlJW-m7M

Hệ thống phải lấy được:
- YouTube ID
- title
- thumbnail
- duration
- metadata cơ bản

Không được yêu cầu người dùng tự nhập lại những thông tin có thể lấy tự động.

---

# 2. OUTPUT JSON

Output cuối cùng phải có cấu trúc:

{
  "id": "aw_zlJW-m7M",
  "youtubeId": "aw_zlJW-m7M",
  "title": "Nói về thói quen hằng ngày",
  "titleHanzi": "日常习惯",
  "level": 2,
  "topic": "Podcast",
  "channel": "Chinese Podcast Station",
  "durationSec": 595,
  "thumbnailUrl": "https://i.ytimg.com/vi/aw_zlJW-m7M/hqdefault.jpg",
  "totalSentences": 182,
  "segments": [
    {
      "id": 1,
      "start": 0.55,
      "end": 3.61,
      "hanzi": "大家好，欢迎你来到今天的节目。",
      "pinyin": "dà jiā hǎo ， huān yíng nǐ lái dào jīn tiān de jié mù 。",
      "vi": "Chào mọi người, chào mừng đến với chương trình hôm nay."
    }
  ]
}

Trong đó `segments` là thành phần QUAN TRỌNG NHẤT của hệ thống.

---

# 3. YÊU CẦU QUAN TRỌNG NHẤT: SEGMENTS

Mỗi segment tương ứng với một câu hoặc một đơn vị lời thoại tương đối hoàn chỉnh.

Mỗi segment bắt buộc có:

- `id`
- `start`
- `end`
- `hanzi`
- `pinyin`
- `vi`

Ví dụ:

{
  "id": 15,
  "start": 42.31,
  "end": 45.72,
  "hanzi": "我每天早上七点起床。",
  "pinyin": "wǒ měi tiān zǎo shang qī diǎn qǐ chuáng。",
  "vi": "Mỗi sáng tôi thức dậy lúc bảy giờ."
}

## Timestamp

`start` và `end` phải là số giây dạng decimal.

Ví dụ:

0.55
3.61
12.42
15.87

Không sử dụng timestamp dạng:

"00:01:23"

trong JSON cuối cùng.

Timestamp phải cố gắng khớp chính xác với lời nói trong video.

---

# 4. PIPELINE XỬ LÝ VIDEO

Thiết kế hệ thống theo pipeline:

INPUT VIDEO
↓
VIDEO METADATA
↓
AUDIO EXTRACTION
↓
SPEECH-TO-TEXT
↓
WORD/SENTENCE TIMESTAMP ALIGNMENT
↓
CHINESE SENTENCE SEGMENTATION
↓
HANZI CLEANING
↓
PINYIN GENERATION
↓
VIETNAMESE TRANSLATION
↓
QUALITY VALIDATION
↓
JSON

Không được bỏ qua bước timestamp alignment.

## Speech-to-text

Ưu tiên sử dụng Whisper hoặc một giải pháp speech-to-text có khả năng nhận dạng tiếng Trung tốt.

Cần lấy timestamp ở mức phù hợp để có thể tạo ra:

start → end → câu tiếng Trung

Không chỉ lấy transcript dạng text thuần.

Nếu Whisper trả về word-level timestamps thì tận dụng chúng để cải thiện việc chia câu.

---

# 5. CHIA CÂU

Không được phụ thuộc hoàn toàn vào timestamp của Whisper segment.

Ví dụ Whisper có thể trả:

"大家好欢迎你来到今天的节目我们今天要聊的是日常习惯"

Hệ thống phải xử lý thành:

Segment 1:
大家好，欢迎你来到今天的节目。

Segment 2:
我们今天要聊的是日常习惯。

Timestamp của từng câu phải được tính lại dựa trên timestamp của words/chunks tương ứng.

Mục tiêu là:

Mỗi segment = một câu tương đối hoàn chỉnh + timestamp tương ứng.

Không chia câu giữa một cụm từ làm mất nghĩa.

---

# 6. HANZI

Hanzi phải giữ nguyên nội dung tiếng Trung được nói trong video.

Không tự ý viết lại câu theo cách khác.

Không tự ý thêm nội dung.

Nếu speech-to-text nhận dạng sai rõ ràng thì có thể sử dụng bước AI correction để sửa lỗi ASR, nhưng phải ưu tiên nội dung thực tế được nói trong video.

Ví dụ:

ASR:
我每天早上七点起床然后去上班

Có thể chuẩn hóa thành:

我每天早上七点起床，然后去上班。

Nhưng KHÔNG được biến thành một câu khác:

我每天早上七点起床，然后坐公交车去公司上班。

nếu video không nói điều đó.

---

# 7. PINYIN

Tự động tạo Pinyin từ Hanzi.

Ví dụ:

Hanzi:
大家好，欢迎你来到今天的节目。

Pinyin:
dà jiā hǎo ， huān yíng nǐ lái dào jīn tiān de jié mù 。

Yêu cầu:

- Pinyin có dấu thanh.
- Giữ mapping chính xác giữa Hanzi và Pinyin.
- Không sử dụng Pinyin không dấu nếu không cần thiết.
- Xử lý đúng các từ đa âm / ngữ cảnh khi có thể.
- Không dịch Hanzi sang Pinyin bằng LLM một cách tùy tiện nếu có thư viện chuyên dụng phù hợp.

Hãy ưu tiên thư viện Pinyin chuyên dụng và chỉ dùng LLM để xử lý các trường hợp khó.

---

# 8. TIẾNG VIỆT

Tự động dịch từng segment sang tiếng Việt.

Ví dụ:

Hanzi:
我每天早上七点起床。

Vi:
Mỗi sáng tôi thức dậy lúc bảy giờ.

Yêu cầu:

- Dịch đúng nghĩa.
- Câu tiếng Việt tự nhiên.
- Không dịch máy một cách quá literal nếu làm mất nghĩa.
- Không thêm thông tin không tồn tại trong câu tiếng Trung.
- Giữ context giữa các segment khi cần thiết.

---

# 9. TITLE HANZI

Ngoài title gốc của video, tạo:

"titleHanzi"

Đây là tiêu đề tiếng Trung phù hợp với nội dung video.

Ví dụ:

title:
Nói về thói quen hằng ngày

titleHanzi:
日常习惯

Nếu title video đã là tiếng Trung thì có thể sử dụng title phù hợp làm `titleHanzi`.

---

# 10. LEVEL

Có trường:

"level": 2

Đây là trình độ tiếng Trung.

Thiết kế hệ thống sao cho level có thể được xác định bằng một trong hai cách:

1. Người dùng chọn level.
2. AI tự động ước lượng level dựa trên vocabulary + grammar.

Ưu tiên cho phép người dùng override kết quả AI.

Ví dụ:

level:
1 → HSK 1
2 → HSK 2
...
9 → HSK 9

Không được để hệ thống phụ thuộc cứng vào một level duy nhất.

---

# 11. TOPIC

Tự động phân loại chủ đề video.

Ví dụ:

"Podcast"
"Daily Life"
"Travel"
"Food"
"Education"
"Business"
"Culture"
"News"
"Conversation"

Cho phép mở rộng danh sách topic.

---

# 12. QUALITY CONTROL

Đây là phần rất quan trọng.

Sau khi tạo segments, hệ thống phải kiểm tra:

### Check 1
start < end

### Check 2
segment sau không được overlap bất hợp lý với segment trước.

### Check 3
Hanzi không được rỗng.

### Check 4
Pinyin không được rỗng.

### Check 5
Vietnamese không được rỗng.

### Check 6
Timestamp nằm trong duration video.

### Check 7
segment phải được sắp xếp theo start time.

### Check 8
id phải tăng tuần tự.

### Check 9
Không được có duplicate segment.

### Check 10
Hanzi và Pinyin phải tương ứng với nhau.

### Check 11
Không tạo segment có timestamp quá dài nếu bên trong có nhiều câu độc lập.

---

# 13. WEB UI

Tạo giao diện web đơn giản nhưng dễ sử dụng.

Trang chính gồm:

## Input

[ Upload MP4 ]

hoặc

[ YouTube URL ]

[ Process ]

Sau khi xử lý:

## Video Preview

Hiển thị video.

## Transcript Editor

Hiển thị:

| # | Time | Hanzi | Pinyin | Vietnamese |
|---|------|-------|--------|------------|

Ví dụ:

1 | 00:00.55 - 00:03.61 | 大家好，欢迎你来到今天的节目。 | dà jiā hǎo... | Chào mọi người...

Người dùng có thể:

- sửa Hanzi
- sửa Pinyin
- sửa tiếng Việt
- sửa start
- sửa end
- xóa segment
- thêm segment
- split segment
- merge segment

Đây là yêu cầu bắt buộc vì ASR/AI không thể chính xác 100%.

---

# 14. AUDIO / VIDEO SYNCHRONIZATION

Khi click vào một segment:

Video phải seek tới:

segment.start

Ví dụ:

click segment 25

→ video.currentTime = segment[24].start

Ngoài ra nên có chức năng:

Play segment

để người dùng nghe chính xác câu đó.

Có thể thêm:

- Play
- Pause
- Replay sentence
- Previous sentence
- Next sentence

---

# 15. EXPORT

Cho phép:

Download JSON

Ví dụ:

[ Download JSON ]

File phải chứa đúng schema:

{
  ...
  "segments": [...]
}

Ngoài ra có thể có:

[ Copy JSON ]

---

# 16. BACKEND ARCHITECTURE

Không xử lý toàn bộ video trực tiếp trong frontend.

Thiết kế:

Frontend
↓
Backend API
↓
Job Queue / Processing
↓
FFmpeg
↓
Whisper / ASR
↓
Sentence Alignment
↓
Pinyin
↓
Translation
↓
Validation
↓
JSON

Nếu video dài, processing phải chạy dạng background job.

Frontend cần hiển thị:

Uploading...
Extracting audio...
Transcribing...
Aligning timestamps...
Generating Pinyin...
Translating...
Validating...
Completed.

---

# 17. API DESIGN

Thiết kế API rõ ràng.

Ví dụ:

POST /api/videos/upload

POST /api/videos/youtube

POST /api/jobs

GET /api/jobs/:id

GET /api/videos/:id

GET /api/videos/:id/segments

PUT /api/videos/:id/segments/:segmentId

DELETE /api/videos/:id/segments/:segmentId

POST /api/videos/:id/segments/split

POST /api/videos/:id/segments/merge

GET /api/videos/:id/export/json

Có thể điều chỉnh API nếu kiến trúc tốt hơn.

---

# 18. DATABASE

Thiết kế database để lưu:

Video

- id
- youtubeId
- title
- titleHanzi
- level
- topic
- channel
- durationSec
- thumbnailUrl
- status
- createdAt
- updatedAt

Segment

- id
- videoId
- start
- end
- hanzi
- pinyin
- vi
- order

Không lưu toàn bộ JSON như một blob duy nhất nếu điều đó làm khó việc chỉnh sửa từng segment.

JSON nên được generate khi export.

---

# 19. ERROR HANDLING

Phải xử lý:

- YouTube URL không hợp lệ.
- Video không tồn tại.
- Không lấy được video.
- Video không có audio.
- Audio không nhận dạng được.
- ASR thất bại.
- Translation thất bại.
- Video quá dài.
- File quá lớn.
- Timeout.
- API key không hợp lệ.
- Processing job thất bại.

Không để backend crash khi một bước AI thất bại.

---

# 20. CẤU HÌNH AI

Không hard-code API key.

Sử dụng `.env`.

Ví dụ:

OPENAI_API_KEY=
WHISPER_MODEL=
TRANSLATION_MODEL=

Nếu có thể, thiết kế abstraction layer:

SpeechToTextProvider
TranslationProvider
PinyinProvider

để sau này có thể thay đổi provider mà không phải viết lại toàn bộ hệ thống.

---

# 21. ƯU TIÊN CHẤT LƯỢNG SEGMENT

Điểm quan trọng nhất của project không phải UI mà là:

**Timestamp + Hanzi + Pinyin + Vietnamese phải khớp với nhau.**

Ví dụ:

Video:

大家好，欢迎你来到今天的节目。

Timestamp:

0.55 → 3.61

Output:

{
  "id": 1,
  "start": 0.55,
  "end": 3.61,
  "hanzi": "大家好，欢迎你来到今天的节目。",
  "pinyin": "dà jiā hǎo ， huān yíng nǐ lái dào jīn tiān de jié mù 。",
  "vi": "Chào mọi người, chào mừng bạn đến với chương trình hôm nay."
}

Khi người dùng click segment này:

→ video phải nhảy đến 0.55s

→ phát đúng câu

Đây là behavior cốt lõi của ứng dụng.

---

# 22. YÊU CẦU CODE

Trước khi viết code:

1. Phân tích yêu cầu.
2. Đề xuất architecture.
3. Đề xuất tech stack.
4. Giải thích pipeline xử lý video.
5. Thiết kế database schema.
6. Thiết kế API.
7. Thiết kế folder structure.
8. Chỉ ra các dependency cần cài.
9. Giải thích cách xử lý timestamp.
10. Giải thích cách đảm bảo segment alignment.

Sau đó mới bắt đầu implement.

Không viết toàn bộ project trong một file.

Code phải:

- modular
- typed nếu dùng TypeScript
- dễ maintain
- có error handling
- có logging
- có `.env.example`
- có README
- có setup instructions

---

# 23. QUAN TRỌNG: KHÔNG ĐƯỢC GIẢ LẬP

Không được:

- fake transcript
- hard-code JSON
- hard-code timestamps
- tạo dữ liệu mẫu rồi giả vờ là kết quả AI
- giả lập API response

Phải xây dựng pipeline thực sự có thể:

MP4 / YouTube
→ audio
→ ASR
→ timestamp
→ sentence segmentation
→ Pinyin
→ Vietnamese
→ JSON.

Nếu một dependency/API có giới hạn hoặc không khả thi, phải nói rõ và đề xuất giải pháp thay thế thay vì giả lập.

---

# 24. MVP

Trước tiên hãy xây MVP với flow:

YouTube URL
→ download/extract audio
→ Whisper transcription
→ sentence segmentation
→ timestamp
→ Pinyin
→ Vietnamese
→ JSON
→ hiển thị transcript trên web.

Sau khi MVP hoạt động ổn định mới thêm:

- MP4 upload
- editor
- split/merge
- video synchronization
- database
- job queue
- advanced validation
- export.

---

# 25. OUTPUT MONG MUỐN TỪ BẠN

Hãy làm việc theo từng phase.

Phase 1:
Architecture + technology selection.

Phase 2:
Project initialization.

Phase 3:
Video/YouTube ingestion.

Phase 4:
ASR + timestamp extraction.

Phase 5:
Sentence segmentation + alignment.

Phase 6:
Pinyin generation.

Phase 7:
Vietnamese translation.

Phase 8:
JSON generation + validation.

Phase 9:
Frontend transcript editor.

Phase 10:
Video synchronization.

Phase 11:
Database + persistence.

Phase 12:
Testing + optimization.

Ở mỗi phase:

- giải thích mục tiêu
- tạo code cần thiết
- chỉ rõ file nào cần tạo/sửa
- cung cấp code hoàn chỉnh cho file đó
- hướng dẫn chạy
- kiểm tra lỗi có thể xảy ra

Không nhảy sang phase tiếp theo nếu phase hiện tại chưa có cách test rõ ràng.

**Bắt đầu bằng Phase 1.**