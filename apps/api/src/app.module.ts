import { Controller, Get, Module } from "@nestjs/common";
import { PrismaService } from "./prisma.service";
import { VideosController } from "./videos.controller";
import { VideosService } from "./videos.service";

@Controller("health")
class HealthController {
  @Get()
  health(): { status: string } {
    return { status: "ok" };
  }
}

@Module({
  controllers: [HealthController, VideosController],
  providers: [PrismaService, VideosService],
})
export class AppModule {}
