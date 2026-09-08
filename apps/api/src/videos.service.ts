import {
  BadRequestException,
  Injectable,
  ServiceUnavailableException,
} from "@nestjs/common";
import { VideoSourceType } from "@prisma/client";
import { IsUrl } from "class-validator";
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

interface SegmentResult {
  id: number;
  start: number;
  end: number;
  hanzi: string;
  pinyin: string;
  vi: string;
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
        `${process.env.AI_WORKER_URL ?? "http://localhost:8000"}/youtube/metadata`,
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
    return this.prisma.video.create({
      data: {
        sourceType: VideoSourceType.YOUTUBE,
        youtubeId: metadata.youtube_id,
        sourceUrl: metadata.source_url,
        title: metadata.title,
        channel: metadata.channel ?? undefined,
        durationSec: metadata.duration_sec ?? undefined,
        thumbnailUrl: metadata.thumbnail_url ?? undefined,
      },
    });
  }

  async downloadMedia(videoId: string) {
    const video = await this.prisma.video.findUnique({ where: { id: videoId } });
    if (!video?.sourceUrl) {
      throw new BadRequestException("Video does not have a downloadable source URL");
    }

    let response: Response;
    try {
      response = await fetch(
        `${process.env.AI_WORKER_URL ?? "http://localhost:8000"}/youtube/download`,
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

    await this.prisma.video.update({ where: { id: videoId }, data: { status: "PROCESSING" } });
    try {
      const downloaded = (await this.callWorker("/youtube/download", {
        source_url: video.sourceUrl,
        output_directory: process.env.MEDIA_ROOT ?? "./media/downloads",
      })) as YouTubeDownload;
      await this.prisma.video.update({ where: { id: videoId }, data: { mediaPath: downloaded.media_path } });

      const extracted = (await this.callWorker("/media/extract-audio", {
        media_path: downloaded.media_path,
        output_directory: process.env.MEDIA_ROOT ?? "./media/audio",
      })) as AudioExtraction;
      const transcript = (await this.callWorker("/transcribe", {
        audio_path: extracted.audio_path,
      })) as TranscriptionResult;
      const aligned = (await this.callWorker("/align", { chunks: transcript.chunks })) as { segments: SegmentResult[] };
      const withPinyin = (await this.callWorker("/pinyin", { segments: aligned.segments })) as { segments: SegmentResult[] };
      const translated = (await this.callWorker("/translate", { segments: withPinyin.segments })) as { segments: SegmentResult[] };

      await this.prisma.$transaction([
        this.prisma.segment.deleteMany({ where: { videoId } }),
        ...translated.segments.map((segment) =>
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
      return this.get(videoId);
    } catch (error) {
      await this.prisma.video.update({ where: { id: videoId }, data: { status: "FAILED" } });
      throw error;
    }
  }

  async get(videoId: string) {
    return this.prisma.video.findUnique({
      where: { id: videoId },
      include: { segments: { orderBy: { order: "asc" } } },
    });
  }

  private async callWorker(path: string, body: Record<string, unknown>): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(
        `${process.env.AI_WORKER_URL ?? "http://localhost:8000"}${path}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(body),
        },
      );
    } catch (error) {
      throw new ServiceUnavailableException(
        `AI worker is unavailable: ${error instanceof Error ? error.message : "unknown error"}`,
      );
    }
    if (!response.ok) {
      throw new BadRequestException((await response.text()) || "Worker request failed");
    }
    return response.json();
  }
}
