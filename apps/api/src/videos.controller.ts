import { Body, Controller, Get, Param, Post, Req, Res } from "@nestjs/common";
import { createReadStream, statSync } from "node:fs";
import type { Request, Response } from "express";
import { CreateYouTubeVideoDto, UpdateSegmentsDto, VideosService } from "./videos.service";

@Controller("videos")
export class VideosController {
  constructor(private readonly videosService: VideosService) {}

  @Post("youtube")
  createFromYouTube(@Body() body: CreateYouTubeVideoDto) {
    return this.videosService.createFromYouTube(body.sourceUrl);
  }

  @Post(":id/media")
  downloadMedia(@Param("id") id: string) {
    return this.videosService.downloadMedia(id);
  }

  @Post(":id/audio")
  extractAudio(@Param("id") id: string) {
    return this.videosService.extractAudio(id);
  }

  @Get(":id/media")
  async streamMedia(@Param("id") id: string, @Req() request: Request, @Res() response: Response) {
    const mediaPath = await this.videosService.getMediaPath(id);
    const size = statSync(mediaPath).size;
    const range = request.headers.range;
    const match = range?.match(/^bytes=(\d*)-(\d*)$/);
    if (!match) {
      response.status(200).set({
        "Content-Type": "video/mp4",
        "Content-Length": String(size),
        "Accept-Ranges": "bytes",
        "Content-Disposition": "inline",
      });
      createReadStream(mediaPath).pipe(response);
      return;
    }

    const start = match[1] ? Number(match[1]) : Math.max(0, size - Number(match[2]) - 1);
    const end = match[2] ? Math.min(size - 1, Number(match[2])) : size - 1;
    if (start > end || start >= size) {
      response.status(416).set("Content-Range", `bytes */${size}`).end();
      return;
    }
    response.status(206).set({
      "Content-Type": "video/mp4",
      "Content-Length": String(end - start + 1),
      "Content-Range": `bytes ${start}-${end}/${size}`,
      "Accept-Ranges": "bytes",
      "Content-Disposition": "inline",
    });
    createReadStream(mediaPath, { start, end }).pipe(response);
  }

  @Post(":id/transcribe")
  transcribe(@Param("id") id: string, @Body("audioPath") audioPath: string) {
    return this.videosService.transcribe(id, audioPath);
  }

  @Post(":id/process")
  process(@Param("id") id: string) {
    return this.videosService.process(id);
  }

  @Post(":id/retry")
  retry(@Param("id") id: string) {
    return this.videosService.retry(id);
  }

  @Post(":id/transcript-import")
  importTranscript(@Param("id") id: string, @Body() body: unknown) {
    return this.videosService.importTranscript(id, body);
  }

  @Get(":id/job")
  getJob(@Param("id") id: string) {
    return this.videosService.getJob(id);
  }

  @Get(":id")
  get(@Param("id") id: string) {
    return this.videosService.get(id);
  }

  @Post(":id/segments")
  updateSegments(@Param("id") id: string, @Body() body: UpdateSegmentsDto) {
    return this.videosService.updateSegments(id, body.segments);
  }

  @Post(":id/export")
  export(@Param("id") id: string) {
    return this.videosService.export(id);
  }
}
