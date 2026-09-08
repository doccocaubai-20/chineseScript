CREATE SCHEMA IF NOT EXISTS "public";

CREATE TYPE "VideoSourceType" AS ENUM ('YOUTUBE', 'UPLOAD');
CREATE TYPE "VideoStatus" AS ENUM ('CREATED', 'PROCESSING', 'COMPLETED', 'FAILED');
CREATE TYPE "JobStatus" AS ENUM ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED');

CREATE TABLE "Video" (
    "id" TEXT NOT NULL,
    "sourceType" "VideoSourceType" NOT NULL,
    "youtubeId" TEXT,
    "sourceUrl" TEXT,
    "title" TEXT NOT NULL,
    "titleHanzi" TEXT,
    "level" INTEGER,
    "topic" TEXT,
    "channel" TEXT,
    "durationSec" DOUBLE PRECISION,
    "thumbnailUrl" TEXT,
    "mediaPath" TEXT,
    "status" "VideoStatus" NOT NULL DEFAULT 'CREATED',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Video_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "Segment" (
    "id" TEXT NOT NULL,
    "videoId" TEXT NOT NULL,
    "start" DOUBLE PRECISION NOT NULL,
    "end" DOUBLE PRECISION NOT NULL,
    "hanzi" TEXT NOT NULL,
    "pinyin" TEXT NOT NULL,
    "vi" TEXT NOT NULL,
    "order" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "Segment_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "ProcessingJob" (
    "id" TEXT NOT NULL,
    "videoId" TEXT NOT NULL,
    "status" "JobStatus" NOT NULL DEFAULT 'QUEUED',
    "currentStep" TEXT,
    "progress" INTEGER NOT NULL DEFAULT 0,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "startedAt" TIMESTAMP(3),
    "finishedAt" TIMESTAMP(3),
    CONSTRAINT "ProcessingJob_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "Video_youtubeId_key" ON "Video"("youtubeId");
CREATE INDEX "Segment_videoId_start_idx" ON "Segment"("videoId", "start");
CREATE UNIQUE INDEX "Segment_videoId_order_key" ON "Segment"("videoId", "order");
CREATE INDEX "ProcessingJob_videoId_status_idx" ON "ProcessingJob"("videoId", "status");

ALTER TABLE "Segment"
    ADD CONSTRAINT "Segment_videoId_fkey"
    FOREIGN KEY ("videoId") REFERENCES "Video"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "ProcessingJob"
    ADD CONSTRAINT "ProcessingJob_videoId_fkey"
    FOREIGN KEY ("videoId") REFERENCES "Video"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;
