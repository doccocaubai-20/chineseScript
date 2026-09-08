export const PROCESSING_STEPS = [
  "INGESTING",
  "EXTRACTING_AUDIO",
  "TRANSCRIBING",
  "ALIGNING",
  "GENERATING_PINYIN",
  "TRANSLATING",
  "VALIDATING",
  "COMPLETED",
] as const;

export type ProcessingStep = (typeof PROCESSING_STEPS)[number];

export interface WorkerJobRequest {
  jobId: string;
  videoId: string;
  sourceUrl: string;
  callbackUrl: string;
}

export interface TimestampedWord {
  text: string;
  start: number;
  end: number;
}

export interface TranscriptChunk {
  text: string;
  start: number;
  end: number;
  words: TimestampedWord[];
}

export interface AlignedSegment {
  id: number;
  start: number;
  end: number;
  hanzi: string;
}

export interface PinyinSegment extends AlignedSegment {
  pinyin: string;
}
