import {
  BadRequestException,
  Injectable,
  ServiceUnavailableException,
} from "@nestjs/common";
import { readFile } from "node:fs/promises";
import { Prisma, VideoSourceType } from "@prisma/client";
import { IsArray, IsUrl } from "class-validator";
import { PrismaService } from "./prisma.service";

export class CreateYouTubeVideoDto {
  @IsUrl({ protocols: ["http", "https"], require_protocol: true })
  sourceUrl!: string;
}

interface YouTubeMetadata {
  youtube_id: string;
  title: string;
  channel?: string | null;
  duration_sec?: number | null;
  thumbnail_url?: string | null;
  source_url: string;
}

interface YouTubeDownload {
  youtube_id: string;
  media_path: string;
}

interface AudioExtraction {
  audio_path: string;
}

interface TranscriptionResult {
  audio_path: string;
  language: string;
  chunks: Array<{
    text: string;
    start: number;
    end: number;
    words: Array<{ text: string; start: number; end: number }>;
  }>;
}

interface PipelineCheckpoint {
  mediaPath?: string;
  audioPath?: string;
  transcript?: TranscriptionResult;
  aligned?: { segments: SegmentResult[] };
  withPinyin?: { segments: SegmentResult[] };
  translated?: { segments: SegmentResult[] };
}

interface SegmentResult {
  id: number;
  start: number;
  end: number;
  hanzi: string;
  pinyin: string;
  vi: string;
}

export class UpdateSegmentsDto {
  @IsArray()
  segments!: SegmentResult[];
}

function isYouTubeUrl(sourceUrl: string): boolean {
  try {
    const url = new URL(sourceUrl);
    return ["youtube.com", "www.youtube.com", "youtu.be", "www.youtu.be"].includes(
      url.hostname.toLowerCase(),
    );
  } catch {
    return false;
  }
}

@Injectable()
export class VideosService {
  constructor(private readonly prisma: PrismaService) {}

  async createFromYouTube(sourceUrl: string) {
    if (!isYouTubeUrl(sourceUrl)) {
      throw new BadRequestException("Only YouTube URLs are supported");
    }

    let response: Response;
    try {
      response = await fetch(
        `${process.env.AI_WORKER_URL ?? "http://127.0.0.1:8000"}/youtube/metadata`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ source_url: sourceUrl }),
        },
      );
    } catch (error) {
      throw new ServiceUnavailableException(
        `AI worker is unavailable: ${error instanceof Error ? error.message : "unknown error"}`,
      );
    }

    if (!response.ok) {
      const detail = await response.text();
      throw new BadRequestException(detail || "Unable to read YouTube metadata");
    }

    const metadata = (await response.json()) as YouTubeMetadata;
    const video = await this.prisma.video.upsert({
      where: { youtubeId: metadata.youtube_id },
      update: {
        sourceUrl: metadata.source_url,
        title: metadata.title,
        channel: metadata.channel ?? undefined,
        durationSec: metadata.duration_sec ?? undefined,
        thumbnailUrl: metadata.thumbnail_url ?? undefined,
      },
      create: {
        sourceType: VideoSourceType.YOUTUBE,
        youtubeId: metadata.youtube_id,
        sourceUrl: metadata.source_url,
        title: metadata.title,
        channel: metadata.channel ?? undefined,
        durationSec: metadata.duration_sec ?? undefined,
        thumbnailUrl: metadata.thumbnail_url ?? undefined,
      },
    });
    return this.get(video.id);
  }

  async downloadMedia(videoId: string) {
    const video = await this.prisma.video.findUnique({ where: { id: videoId } });
    if (!video?.sourceUrl) {
      throw new BadRequestException("Video does not have a downloadable source URL");
    }

    let response: Response;
    try {
      response = await fetch(
        `${process.env.AI_WORKER_URL ?? "http://127.0.0.1:8000"}/youtube/download`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            source_url: video.sourceUrl,
            output_directory: process.env.MEDIA_ROOT ?? "./media/downloads",
          }),
        },
      );
    } catch (error) {
      throw new ServiceUnavailableException(
        `AI worker is unavailable: ${error instanceof Error ? error.message : "unknown error"}`,
      );
    }

    if (!response.ok) {
      const detail = await response.text();
      throw new BadRequestException(detail || "Unable to download YouTube media");
    }

    const downloaded = (await response.json()) as YouTubeDownload;
    return this.prisma.video.update({
      where: { id: videoId },
      data: { mediaPath: downloaded.media_path },
    });
  }

  async extractAudio(videoId: string) {
    const video = await this.prisma.video.findUnique({ where: { id: videoId } });
    if (!video?.mediaPath) {
      throw new BadRequestException("Video does not have downloaded media");
    }

    const response = await this.callWorker("/media/extract-audio", {
      media_path: video.mediaPath,
      output_directory: process.env.MEDIA_ROOT ?? "./media/audio",
    });
    const extracted = response as AudioExtraction;
    return { videoId, audioPath: extracted.audio_path };
  }

  async transcribe(videoId: string, audioPath: string) {
    const result = (await this.callWorker("/transcribe", {
      audio_path: audioPath,
    })) as TranscriptionResult;
    return { videoId, ...result };
  }

  async process(videoId: string) {
    const video = await this.prisma.video.findUnique({ where: { id: videoId } });
    if (!video?.sourceUrl) {
      throw new BadRequestException("Video does not have a source URL");
    }

    const latestJob = await this.prisma.processingJob.findFirst({
      where: { videoId },
      orderBy: { createdAt: "desc" },
    });
    if (latestJob?.status === "QUEUED" || latestJob?.status === "RUNNING") {
      return latestJob;
    }

    const job = await this.prisma.processingJob.create({
      data: {
        videoId,
        checkpoint: latestJob?.checkpoint ?? undefined,
      },
    });
    void this.runProcess(videoId, job.id, (latestJob?.checkpoint as PipelineCheckpoint | null) ?? {});
    return job;
  }

  private async runProcess(videoId: string, jobId: string, initialCheckpoint: PipelineCheckpoint) {
    let checkpoint = initialCheckpoint;
    try {
      const video = await this.prisma.video.findUnique({ where: { id: videoId } });
      if (!video?.sourceUrl) throw new BadRequestException("Video does not have a source URL");
      await this.updateJob(jobId, { status: "RUNNING", currentStep: "DOWNLOADING", progress: 5 });
      await this.prisma.video.update({ where: { id: videoId }, data: { status: "PROCESSING" } });

      if (!checkpoint.mediaPath) {
        const downloaded = (await this.callWorker("/youtube/download", {
          source_url: video.sourceUrl,
          output_directory: process.env.MEDIA_ROOT ?? "./media/downloads",
        })) as YouTubeDownload;
        checkpoint = { ...checkpoint, mediaPath: downloaded.media_path };
        await this.prisma.video.update({ where: { id: videoId }, data: { mediaPath: downloaded.media_path } });
        await this.updateJob(jobId, { checkpoint, currentStep: "EXTRACTING_AUDIO", progress: 20 });
      }

      if (!checkpoint.audioPath) {
        const extracted = (await this.callWorker("/media/extract-audio", {
          media_path: checkpoint.mediaPath,
          output_directory: process.env.MEDIA_ROOT ?? "./media/audio",
        })) as AudioExtraction;
        checkpoint = { ...checkpoint, audioPath: extracted.audio_path };
        await this.updateJob(jobId, { checkpoint, currentStep: "TRANSCRIBING", progress: 35 });
      }

      if (!checkpoint.transcript) {
        const transcript = await this.transcribeAudio(checkpoint.audioPath!);
        checkpoint = { ...checkpoint, transcript };
        await this.updateJob(jobId, { checkpoint, currentStep: "ALIGNING", progress: 55 });
      }

      if (!checkpoint.aligned) {
        const aligned = (await this.callWorker("/align", { chunks: checkpoint.transcript?.chunks ?? [] })) as { segments: SegmentResult[] };
        checkpoint = { ...checkpoint, aligned };
        await this.updateJob(jobId, { checkpoint, currentStep: "GENERATING_PINYIN", progress: 65 });
      }

      if (!checkpoint.withPinyin) {
        const withPinyin = (await this.callWorker("/pinyin", { segments: checkpoint.aligned?.segments ?? [] })) as { segments: SegmentResult[] };
        checkpoint = { ...checkpoint, withPinyin };
        await this.updateJob(jobId, { checkpoint, currentStep: "TRANSLATING", progress: 75 });
      }

      if (!checkpoint.translated) {
        const translated = (await this.callWorker("/translate", { segments: checkpoint.withPinyin?.segments ?? [] })) as { segments: SegmentResult[] };
        checkpoint = { ...checkpoint, translated };
        await this.updateJob(jobId, { checkpoint, currentStep: "VALIDATING", progress: 90 });
      }

      await this.prisma.$transaction([
        this.prisma.segment.deleteMany({ where: { videoId } }),
        ...(checkpoint.translated?.segments ?? []).map((segment) =>
          this.prisma.segment.create({
            data: {
              videoId,
              start: segment.start,
              end: segment.end,
              hanzi: segment.hanzi,
              pinyin: segment.pinyin,
              vi: segment.vi,
              order: segment.id,
            },
          }),
        ),
        this.prisma.video.update({ where: { id: videoId }, data: { status: "COMPLETED" } }),
      ]);
      await this.updateJob(jobId, {
        status: "COMPLETED",
        currentStep: "COMPLETED",
        progress: 100,
        checkpoint,
        finishedAt: new Date(),
      });
      return this.get(videoId);
    } catch (error) {
      await this.prisma.video.update({ where: { id: videoId }, data: { status: "FAILED" } });
      await this.updateJob(jobId, {
        status: "FAILED",
        errorMessage: error instanceof Error ? error.message : "Pipeline failed",
        checkpoint,
        finishedAt: new Date(),
      });
      throw error;
    }
  }

  async get(videoId: string) {
    return this.prisma.video.findUnique({
      where: { id: videoId },
      include: { segments: { orderBy: { order: "asc" } } },
    });
  }

  async getJob(videoId: string) {
    return this.prisma.processingJob.findFirst({
      where: { videoId },
      orderBy: { createdAt: "desc" },
    });
  }

  async updateSegments(videoId: string, segments: SegmentResult[]) {
    const video = await this.prisma.video.findUnique({ where: { id: videoId } });
    if (!video) throw new BadRequestException("Video not found");
    const duration = video.durationSec;
    if (duration == null || duration <= 0) {
      throw new BadRequestException("Video duration is required before saving segments");
    }
    for (const [index, segment] of segments.entries()) {
      if (
        segment.id !== index + 1 ||
        !Number.isFinite(segment.start) ||
        !Number.isFinite(segment.end) ||
        segment.start < 0 ||
        segment.start >= segment.end ||
        segment.end > duration ||
        !segment.hanzi?.trim() ||
        !segment.pinyin?.trim() ||
        !segment.vi?.trim()
      ) {
        throw new BadRequestException(`Invalid segment at index ${index}`);
      }
      const previous = segments[index - 1];
      if (previous && segment.start < previous.end - 0.25) {
        throw new BadRequestException(`Segment ${index + 1} overlaps the previous segment`);
      }
    }
    await this.prisma.$transaction([
      this.prisma.segment.deleteMany({ where: { videoId } }),
      ...segments.map((segment, index) => this.prisma.segment.create({
        data: {
          videoId,
          start: segment.start,
          end: segment.end,
          hanzi: segment.hanzi,
          pinyin: segment.pinyin,
          vi: segment.vi,
          order: index + 1,
        },
      })),
    ]);
    return this.get(videoId);
  }

  async export(videoId: string) {
    const video = await this.prisma.video.findUnique({
      where: { id: videoId },
      include: { segments: { orderBy: { order: "asc" } } },
    });
    if (!video) throw new BadRequestException("Video not found");
    return this.callWorker("/export/json", {
      video: {
        id: video.id,
        youtubeId: video.youtubeId,
        title: video.title,
        titleHanzi: video.titleHanzi,
        level: video.level,
        topic: video.topic,
        channel: video.channel,
        durationSec: video.durationSec,
        thumbnailUrl: video.thumbnailUrl,
        totalSentences: video.segments.length,
      },
      segments: video.segments.map((segment) => ({
        id: segment.order,
        start: segment.start,
        end: segment.end,
        hanzi: segment.hanzi,
        pinyin: segment.pinyin,
        vi: segment.vi,
      })),
    });
  }

  private async updateJob(
    jobId: string,
    data: {
      status?: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
      currentStep?: string;
      progress?: number;
      errorMessage?: string;
      finishedAt?: Date;
      checkpoint?: PipelineCheckpoint;
    },
  ) {
    return this.prisma.processingJob.update({
      where: { id: jobId },
      data: {
        ...data,
        checkpoint: data.checkpoint as Prisma.InputJsonValue | undefined,
      },
    });
  }

  private async callWorker(path: string, body: Record<string, unknown>): Promise<unknown> {
    let lastError: unknown;
    const timeoutMs = Number(process.env.AI_WORKER_TIMEOUT_MS ?? 1800000);
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        let response: Response;
        try {
          response = await fetch(
            `${process.env.AI_WORKER_URL ?? "http://127.0.0.1:8000"}${path}`,
            {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify(body),
              signal: controller.signal,
            },
          );
        } finally {
          clearTimeout(timeout);
        }
        if (response.ok) return response.json();
        const detail = (await response.text()) || "Worker request failed";
        if (response.status < 500 && response.status !== 408 && response.status !== 429) {
          throw new BadRequestException(detail);
        }
        lastError = new Error(detail);
      } catch (error) {
        if (error instanceof BadRequestException) throw error;
        lastError = error;
      }
      await new Promise((resolve) => setTimeout(resolve, attempt * 1000));
    }
    throw new ServiceUnavailableException(
      `AI worker is unavailable: ${lastError instanceof Error ? lastError.message : "unknown error"}`,
    );
  }

  private async transcribeAudio(audioPath: string): Promise<TranscriptionResult> {
    const remoteUrl = process.env.REMOTE_TRANSCRIBE_URL?.trim();
    if (!remoteUrl) {
      return (await this.callWorker("/transcribe", { audio_path: audioPath })) as TranscriptionResult;
    }

    const audio = await readFile(audioPath);
    const form = new FormData();
    form.append("file", new Blob([audio], { type: "audio/wav" }), "audio.wav");
    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      Number(process.env.AI_WORKER_TIMEOUT_MS ?? 1800000),
    );
    try {
      const response = await fetch(remoteUrl, {
        method: "POST",
        body: form,
        headers: process.env.REMOTE_TRANSCRIBE_TOKEN
          ? { authorization: `Bearer ${process.env.REMOTE_TRANSCRIBE_TOKEN}` }
          : undefined,
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new ServiceUnavailableException(
          (await response.text()) || "Remote transcription failed",
        );
      }
      return (await response.json()) as TranscriptionResult;
    } catch (error) {
      if (error instanceof ServiceUnavailableException) throw error;
      throw new ServiceUnavailableException(
        `Remote transcription is unavailable: ${error instanceof Error ? error.message : "unknown error"}`,
      );
    } finally {
      clearTimeout(timeout);
    }
  }
}
