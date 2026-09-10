# Chinese Video to Learning JSON

Monorepo for converting Chinese videos into timestamped learning segments:

```text
YouTube audio -> FFmpeg -> faster-whisper -> sentence alignment
-> Pinyin -> Vietnamese translation -> validation -> JSON
```

## Workspace

- `apps/web`: Next.js frontend.
- `apps/api`: NestJS API and Prisma persistence.
- `services/ai-worker`: Python/FastAPI media and AI processing service.
- `packages/contracts`: shared TypeScript contract types.
- `docs`: architecture and JSON export contract.

## Tải TikTok nhanh

Không cần Docker, API hay web app. Cài `yt-dlp` một lần:

```powershell
python -m pip install yt-dlp
```

Sau đó chạy công cụ độc lập và dán link TikTok:

```powershell
.\scripts\download-tiktok.ps1
```

Hoặc truyền link trực tiếp:

```powershell
.\scripts\download-tiktok.ps1 "https://www.tiktok.com/@user/video/123"
```

Video được lưu trong `media\tiktok`.

## Prerequisites

- Node.js 20+
- pnpm 9+
- Python 3.10+
- Docker Desktop
- FFmpeg available to the AI worker

Phase 4 requires FFmpeg on `PATH`. On Windows, install it with a trusted package
manager or download the official build, then verify with:

```powershell
ffmpeg -version
```

The first transcription with faster-whisper also downloads the configured model
(`small` by default). The model is cached locally; no transcript is fabricated when
FFmpeg, the model, or the input media is unavailable.

## Local setup

1. Copy `.env.example` to `.env`. The default database is local PostgreSQL:

   ```env
   DATABASE_URL=postgresql://app:app@localhost:55432/chinese_video
   ```

   If `.env` previously contained Supabase settings, run
   `.\scripts\use-local-db.ps1` to update it automatically.

2. Start infrastructure:

   ```powershell
   pnpm db:up
   ```

3. Install TypeScript dependencies:

   ```powershell
   pnpm install
   ```

4. Generate the Prisma client and validate the schema:

   ```powershell
   pnpm db:generate
   pnpm db:validate
   ```

5. Apply database migrations:

   ```powershell
   pnpm db:migrate
   ```

6. Start the applications in separate terminals. The API and worker automatically
   load `.env` from the project root:

   ```powershell
   pnpm dev:api
   pnpm dev:web
   ```

7. Start the worker:

   ```powershell
   cd services/ai-worker
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

The API health endpoint is `http://localhost:3001/health`; the worker health
endpoint is `http://localhost:8000/health`; the web app is `http://localhost:3000`.

Processing runs as a background job. The process endpoint returns immediately;
the web app polls the job status and displays the current step and progress.
Completed pipeline stages are saved as checkpoints, so retrying a failed job
reuses downloaded media, transcripts, Pinyin, and translations when available.
Normalized WAV audio is transcribed in chunks controlled by
`AUDIO_CHUNK_DURATION_SEC` (600 seconds by default), with timestamps offset back
to the original audio timeline.

Detailed local testing steps are in [docs/LOCAL-TESTING.md](docs/LOCAL-TESTING.md).

For a simpler Windows workflow, run `.\scripts\start-local.ps1`. It starts the local
PostgreSQL container and opens the worker, API, and web app in separate PowerShell
windows. Run `.\scripts\stop-local.ps1` to stop the applications and PostgreSQL
container. The database volume is preserved.

To create a YouTube source through the API, send:

```powershell
Invoke-RestMethod http://localhost:3001/videos/youtube `
  -Method Post -ContentType "application/json" `
  -Body '{"sourceUrl":"https://www.youtube.com/watch?v=VIDEO_ID"}'
```

The API validates the host, asks the local worker to resolve metadata with `yt-dlp`,
and persists the source in local PostgreSQL. Processing downloads only the best available
audio stream; the YouTube video itself is embedded in the web player. FFmpeg then
normalizes that temporary audio for Whisper.

Phase 2 creates skeletons only. No transcript or timestamp is fabricated; processing
features are added in later phases. Pinyin is generated locally with `pypinyin`.
Vietnamese translation uses an OpenAI-compatible provider; DeepSeek is the default
configuration in `.env.example`.
