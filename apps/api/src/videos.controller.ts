import { Body, Controller, Get, Param, Post } from "@nestjs/common";
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

  @Post(":id/transcribe")
  transcribe(@Param("id") id: string, @Body("audioPath") audioPath: string) {
    return this.videosService.transcribe(id, audioPath);
  }

  @Post(":id/process")
  process(@Param("id") id: string) {
    return this.videosService.process(id);
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
