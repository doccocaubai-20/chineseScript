# Chinese Video Learning JSON - Architecture

## 1. Goal and MVP boundary

The system converts a Chinese YouTube video into editable learning data:

```text
YouTube URL
  -> metadata and media ingestion
  -> FFmpeg audio extraction
  -> faster-whisper Chinese ASR with word timestamps
  -> sentence segmentation and timestamp alignment
  -> Hanzi normalization
  -> tone-marked Pinyin
  -> Vietnamese translation
  -> validation
  -> transcript UI and JSON export
```

The MVP supports YouTube URLs and produces a transcript view plus JSON. MP4 upload,
editing operations, authentication, persistence enhancements, and horizontal worker
scaling are designed as extensions rather than separate implementations.

## 2. Components

### Web: `apps/web`

Next.js and TypeScript provide the user interface:

- YouTube URL form and future MP4 upload form.
- Job progress and per-step errors.
- HTML5 video preview.
- Transcript table/editor.
- Segment click-to-seek and sentence playback.
- JSON download/copy.

Tailwind CSS and shadcn/ui are used for consistent UI primitives. The browser does
not run FFmpeg, Whisper, translation, or long-running processing.

### API: `apps/api`

NestJS owns the application boundary:

- Validates input DTOs and returns consistent errors.
- Resolves YouTube metadata and creates ingestion records.
- Creates and monitors processing jobs.
- Reads/writes videos and segments through Prisma.
- Coordinates the local processing flow and exposes job progress.
- Exposes segment editing and JSON export endpoints.

The local MVP runs one processing flow at a time. A queue is added when background
processing or multi-user concurrency is required.

### AI worker: `services/ai-worker`

Python and FastAPI host processing capabilities and provider adapters:

- Media download and FFmpeg extraction.
- faster-whisper transcription with word-level timestamps where available.
- Chinese sentence segmentation and alignment.
- Hanzi cleanup.
- Pinyin generation through a specialized library.
- Vietnamese translation through a provider abstraction.
- Final quality validation.

The worker reports progress and structured errors to the job coordinator. It does not
write arbitrary JSON blobs as the source of truth.

### Infrastructure

- PostgreSQL stores video metadata, segments, and processing jobs.
- Prisma is the schema and data-access layer for the NestJS API.
- Redis/BullMQ is deferred until background processing or multi-user concurrency is
  required.
- Local development uses Docker Compose for PostgreSQL only.
- Media files should use object storage in production; local MVP may use a configured
  filesystem directory with explicit size and retention limits.

## 3. Processing contract

Each processing job has these ordered steps:

1. `INGESTING`: validate URL, resolve metadata, download media.
2. `EXTRACTING_AUDIO`: inspect audio and create an ASR-compatible file with FFmpeg.
3. `TRANSCRIBING`: run Chinese ASR and retain chunks/words with timestamps.
4. `ALIGNING`: segment by Chinese sentence boundaries and derive sentence times from
   the first and last matched words.
5. `GENERATING_PINYIN`: generate tone-marked Pinyin using the Hanzi text.
6. `TRANSLATING`: translate each segment while preserving segment order and identity.
7. `VALIDATING`: run schema and quality checks.
8. `COMPLETED`: expose the resulting video and segments for the UI/export.

Failures are terminal for the current job, include a user-safe message and a
diagnostic code, and do not crash the API process. Retryable provider/media failures
are retried by BullMQ with a bounded attempt count.

## 4. Timestamp alignment

Whisper segment timestamps are only coarse input. Sentence timestamps are calculated
from the words assigned to each sentence:

```text
sentence.start = firstAssignedWord.start
sentence.end   = lastAssignedWord.end
```

The segmenter must:

- Prefer punctuation and Chinese clause boundaries.
- Avoid splitting a phrase in the middle of a meaningful unit.
- Preserve the original recognized Hanzi; only normalize whitespace and punctuation.
- Use a documented fallback to chunk timestamps when word timestamps are missing.
- Reject or flag a sentence when it has no usable time range.

The validator enforces `0 <= start < end <= durationSec`, sorted order, bounded
overlap, and sequential IDs. Manual editor changes go through the same validation
before export.

## 5. Data model

### `Video`

Stores source and generated metadata: `id`, `sourceType`, `youtubeId`, `sourceUrl`,
`title`, `titleHanzi`, `level`, `topic`, `channel`, `durationSec`, `thumbnailUrl`,
`mediaPath`, `status`, `createdAt`, and `updatedAt`.

### `Segment`

Stores editable source-of-truth rows: `id`, `videoId`, `start`, `end`, `hanzi`,
`pinyin`, `vi`, `order`, `createdAt`, and `updatedAt`. A video has many segments;
deleting a video deletes its segments.

### `ProcessingJob`

Stores `id`, `videoId`, `status`, `currentStep`, `progress`, `attempts`, `errorCode`,
`errorMessage`, `createdAt`, `startedAt`, and `finishedAt`. A video can have more
than one historical job, while only one active job is allowed by application logic.

JSON is generated from `Video` and ordered `Segment` rows at export time.

## 6. API surface

The initial REST boundary is:

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/videos/youtube` | Validate URL and create a video source |
| `POST` | `/api/jobs` | Enqueue processing for a video |
| `GET` | `/api/jobs/:id` | Read job status/progress/error |
| `GET` | `/api/videos/:id` | Read video metadata/status |
| `GET` | `/api/videos/:id/segments` | Read ordered segments |
| `PUT` | `/api/videos/:id/segments/:segmentId` | Edit one segment |
| `DELETE` | `/api/videos/:id/segments/:segmentId` | Delete one segment |
| `POST` | `/api/videos/:id/segments/split` | Split a segment |
| `POST` | `/api/videos/:id/segments/merge` | Merge adjacent segments |
| `GET` | `/api/videos/:id/export/json` | Generate and download schema JSON |

All request bodies and responses will use explicit DTOs/schema validation. The
worker-facing contract is versioned separately from UI payloads so provider changes
do not leak into the frontend.

## 7. Provider abstractions

The worker will define interfaces equivalent to:

- `SpeechToTextProvider.transcribe(audioPath, options) -> TimestampedTranscript`
- `PinyinProvider.convert(hanzi) -> PinyinResult`
- `TranslationProvider.translate(segments, context) -> TranslatedSegment[]`

Default providers are faster-whisper, a specialized Chinese Pinyin library, and an
LLM translation adapter. API keys and model names come only from environment
configuration. Provider errors are typed as retryable or non-retryable.

## 8. Security and operational constraints

- No API keys in source control; provide `.env.example` during project initialization.
- Validate YouTube URLs and reject unsupported hosts/URL forms.
- Enforce configurable file-size, duration, timeout, and concurrency limits.
- Store downloaded media outside the source tree and clean it after retention expiry.
- Sanitize user-edited text before rendering; React output remains escaped by default.
- Never log API keys, raw authorization headers, or full provider responses containing
  secrets.

## 9. Technology trade-offs

The TypeScript API and Python worker intentionally split responsibilities. NestJS is
well suited to HTTP, DTOs, Prisma, and BullMQ orchestration; Python has the stronger
Whisper/media and NLP ecosystem. The trade-off is an explicit job/progress contract
between services, which is preferable to coupling the browser to AI dependencies.

The worker must be provisioned with enough CPU/GPU, disk, and model cache space.
Development and deployment documentation must state these requirements rather than
silently falling back to fake transcript data.

## 10. Phase 2 exit criteria

Before implementing the first processing feature, Phase 2 must provide:

- Monorepo workspace and package scripts.
- Docker Compose for PostgreSQL.

## 11. Phase 4 ASR implementation

The local worker normalizes media to mono 16 kHz PCM WAV with FFmpeg, then calls
faster-whisper using `WHISPER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8`, and
`WHISPER_MODEL=small` by default. Word timestamps are retained in the worker
response; sentence segmentation is intentionally a later phase. If FFmpeg or the
model is unavailable, the endpoint returns an explicit error rather than fallback
text.
- NestJS API skeleton with health endpoint.
- Python worker skeleton with typed job contract.
- Next.js UI skeleton.
- Prisma schema migration for the three core models.
- `.env.example` and setup instructions.
