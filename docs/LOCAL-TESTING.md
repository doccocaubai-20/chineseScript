# Hướng dẫn test local

Tài liệu này dùng cho MVP local-first hiện tại:

```text
Python AI Worker :8000
NestJS API       :3001
Next.js Web      :3000
Supabase         PostgreSQL
```

## 1. Chuẩn bị

Mở PowerShell tại thư mục project:

```powershell
cd C:\path\to\chinese-video-to-learning-json
```

Kiểm tra các công cụ:

```powershell
node --version
corepack pnpm --version
python --version
ffmpeg -version
```

Nếu `ffmpeg` không nhận diện được, cần cài FFmpeg và mở lại PowerShell.

## 2. Kiểm tra file `.env`

Tạo file:

```text
C:\path\to\chinese-video-to-learning-json\.env
```

Không commit file này và không chia sẻ password Supabase.

Nội dung tối thiểu:

```env
NODE_ENV=development
API_PORT=3001
WEB_PORT=3000
DATABASE_URL=postgresql://USER:PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres?sslmode=require
AI_WORKER_URL=http://localhost:8000
MEDIA_ROOT=.\media
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
OPENAI_API_KEY=
TRANSLATION_MODEL=deepseek-chat
```

Nếu password có ký tự đặc biệt trong URL, hãy URL-encode password trước khi đặt vào
`DATABASE_URL`.

## 3. Cài dependencies

Chạy một lần:

```powershell
corepack pnpm install
python -m pip install -r services\ai-worker\requirements.txt
corepack pnpm db:generate
corepack pnpm --filter api prisma migrate deploy
```

## 4. Terminal 1 - chạy AI Worker

### Cách đơn giản: chạy một script

Từ thư mục project:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start-local.ps1
```

Script sẽ tự mở ba cửa sổ PowerShell cho Worker, API và frontend. Sau đó mở
`http://localhost:3000`. Khi muốn dừng toàn bộ:

```powershell
.\scripts\stop-local.ps1
```

Nếu muốn kiểm tra thủ công từng service, tiếp tục theo các bước bên dưới.

Mở terminal thứ nhất:

```powershell
cd C:\path\to\chinese-video-to-learning-json

python -m uvicorn app.main:app `
  --app-dir services\ai-worker `
  --host 127.0.0.1 `
  --port 8000
```

Giữ terminal này mở.

Mở terminal khác để kiểm tra:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Kết quả đúng:

```json
{
  "status": "ok"
}
```

## 5. Terminal 2 - chạy NestJS API

Mở terminal thứ hai:

```powershell
cd C:\path\to\chinese-video-to-learning-json

corepack pnpm --filter api start:dev
```

Giữ terminal này mở.

Mở terminal khác để kiểm tra:

```powershell
Invoke-RestMethod http://localhost:3001/health
```

Kết quả đúng:

```json
{
  "status": "ok"
}
```

Nếu nhận `AI worker is unavailable`, API đang chạy nhưng worker chưa chạy hoặc
`AI_WORKER_URL` chưa được đặt trong đúng terminal trước khi khởi động API.

## 6. Terminal 3 - chạy frontend

Mở terminal thứ ba:

```powershell
cd C:\path\to\chinese-video-to-learning-json
corepack pnpm --filter web dev
```

Mở trình duyệt:

```text
http://localhost:3000
```

Frontend hiện là skeleton. Flow test chính hiện tại thực hiện qua API. API và worker
tự động đọc `.env` ở thư mục gốc, nên không cần set lại biến môi trường mỗi lần chạy.

## 7. Test lấy metadata YouTube

Trong PowerShell mới:

```powershell
cd C:\path\to\chinese-video-to-learning-json

$body = @{
  sourceUrl = "https://www.youtube.com/watch?v=VIDEO_ID"
} | ConvertTo-Json

$video = Invoke-RestMethod `
  http://localhost:3001/videos/youtube `
  -Method Post `
  -ContentType "application/json" `
  -Body $body

$video | ConvertTo-Json -Depth 5
$video.id
```

Kết quả phải có video ID database, YouTube ID, title, channel, duration và thumbnail.
Lưu giá trị `$video.id` để dùng ở bước tiếp theo.

## 8. Test tải media local

```powershell
$videoId = $video.id

$downloaded = Invoke-RestMethod `
  "http://localhost:3001/videos/$videoId/media" `
  -Method Post

$downloaded | ConvertTo-Json -Depth 5
```

Media tạm được lưu trong thư mục `media`. Nếu endpoint trả lỗi, kiểm tra:

- Worker vẫn đang chạy ở port `8000`.
- URL YouTube còn truy cập được.
- `yt-dlp` đã được cài.
- Thư mục `media` có quyền ghi.

## 9. Test tách audio bằng FFmpeg

Hiện endpoint audio nhận `videoId` nhưng database cần biết `mediaPath`. Có thể gọi
worker trực tiếp để kiểm tra nhanh:

```powershell
$audioBody = @{
  media_path = $downloaded.mediaPath
  output_directory = "C:/Users/admin/Documents/ToolsYTB/media/audio"
} | ConvertTo-Json

$audio = Invoke-RestMethod `
  http://localhost:8000/media/extract-audio `
  -Method Post `
  -ContentType "application/json" `
  -Body $audioBody

$audio | ConvertTo-Json
```

Kết quả phải có `audio_path` trỏ tới file WAV mono 16 kHz.

## 10. Test transcription

```powershell
$transcribeBody = @{
  audio_path = $audio.audio_path
} | ConvertTo-Json

$transcript = Invoke-RestMethod `
  http://localhost:8000/transcribe `
  -Method Post `
  -ContentType "application/json" `
  -Body $transcribeBody

$transcript.language
$transcript.chunks | Select-Object -First 3 | ConvertTo-Json -Depth 8
```

Lần đầu chạy faster-whisper sẽ tải model `small`, có thể mất nhiều thời gian và
dung lượng. Kết quả thật phải có:

- `language = zh`
- `chunks[].text`
- `chunks[].start`
- `chunks[].end`
- `chunks[].words[]` nếu model trả word timestamps

Không dùng dữ liệu mẫu nếu Whisper hoặc FFmpeg thất bại.

## 11. Test chia câu và căn timestamp

Sau khi cập nhật worker, khởi động lại worker rồi gửi chunks từ file transcript:

```powershell
$transcriptJson = Get-Content .\transcript-result.json -Raw -Encoding UTF8
$rawTranscript = $transcriptJson | ConvertFrom-Json

$alignmentBody = @{
  chunks = $rawTranscript.chunks
} | ConvertTo-Json -Depth 20

$aligned = Invoke-RestMethod `
  http://localhost:8000/align `
  -Method Post `
  -ContentType "application/json" `
  -Body $alignmentBody

$aligned.segments |
  Select-Object -First 3 |
  ConvertTo-Json -Depth 10
```

Mỗi segment phải có `id`, `start`, `end`, `hanzi`. Timestamp được lấy từ word đầu
và word cuối, ở dạng số giây decimal. Endpoint không dịch, không tạo Pinyin và
không tự viết lại nội dung; các bước đó thuộc các phase sau.

## 12. Test tạo Pinyin

Gửi các segment đã căn timestamp tới worker:

```powershell
$pinyinBody = @{
  segments = $aligned.segments
} | ConvertTo-Json -Depth 20

$withPinyin = Invoke-RestMethod `
  http://localhost:8000/pinyin `
  -Method Post `
  -ContentType "application/json" `
  -Body $pinyinBody

$withPinyin.segments |
  Select-Object -First 3 |
  ConvertTo-Json -Depth 10
```

Pinyin được tạo local bằng `pypinyin`, có dấu thanh và không gọi LLM. Timestamp,
Hanzi và thứ tự segment được giữ nguyên.

## 13. Test dịch tiếng Việt

Đặt API key DeepSeek vào `OPENAI_API_KEY`, cùng cấu hình OpenAI-compatible trong
`.env`, sau đó restart worker:

```env
OPENAI_API_KEY=your_deepseek_key
OPENAI_BASE_URL=https://api.deepseek.com
TRANSLATION_MODEL=deepseek-chat
```

Không commit hoặc chia sẻ API key. Gửi các segment đã có Pinyin:

```powershell
$translationBody = @{
  segments = $withPinyin.segments
} | ConvertTo-Json -Depth 20

$translated = Invoke-RestMethod `
  http://localhost:8000/translate `
  -Method Post `
  -ContentType "application/json" `
  -Body $translationBody

$translated.segments |
  Select-Object -First 3 |
  ConvertTo-Json -Depth 10
```

Provider chỉ trả kết quả thành công khi có đúng bản dịch theo từng `id`. Không có
API key, lỗi provider hoặc JSON không hợp lệ sẽ trả lỗi, không sinh dữ liệu giả.

## 14. Test validation và export JSON

Tạo payload video từ metadata và segments đã dịch:

```powershell
$videoPayload = @{
  id = $video.id
  youtubeId = "VIDEO_ID"
  title = $video.title
  titleHanzi = $null
  level = 2
  topic = "Conversation"
  channel = $video.channel
  durationSec = $video.durationSec
  thumbnailUrl = $video.thumbnailUrl
  totalSentences = $translated.segments.Count
}

$exportBody = @{
  video = $videoPayload
  segments = $translated.segments
} | ConvertTo-Json -Depth 20

$validation = Invoke-RestMethod `
  http://localhost:8000/validate `
  -Method Post -ContentType "application/json" -Body $exportBody
$validation | ConvertTo-Json -Depth 10

$learningJson = Invoke-RestMethod `
  http://localhost:8000/export/json `
  -Method Post -ContentType "application/json" -Body $exportBody
$learningJson | ConvertTo-Json -Depth 20 |
  Out-File .\learning-result.json -Encoding utf8
```

Export chỉ thành công khi `valid` là `true`. Validator kiểm tra timestamp, duration,
thứ tự/id, overlap, nội dung rỗng, duplicate, số Pinyin tối thiểu và tổng số câu.

## 15. Dừng ứng dụng

Trong từng terminal đang chạy server, nhấn:

```text
Ctrl+C
```

Không cần Redis cho MVP hiện tại. Video/audio chỉ là file tạm local; transcript và
metadata mới là dữ liệu lưu trong Supabase.

## 16. Lỗi thường gặp

### `Environment variable not found: DATABASE_URL`

Đặt `$env:DATABASE_URL` trong chính terminal khởi động API, rồi khởi động lại API.

### `AI worker is unavailable: fetch failed`

Kiểm tra:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Sau đó kiểm tra:

```powershell
$env:AI_WORKER_URL
```

Phải là `http://localhost:8000` trong terminal API.

### `ffmpeg is not recognized`

Cài FFmpeg, thêm vào PATH, đóng toàn bộ terminal cũ và mở terminal mới.

### `ModuleNotFoundError: faster_whisper`

Chạy:

```powershell
python -m pip install -r services\ai-worker\requirements.txt
```

### Supabase không kết nối được

Kiểm tra connection string, password mới, `?sslmode=require`, và URL-encode các ký
tự đặc biệt trong password.
