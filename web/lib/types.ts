/**
 * TypeScript types mirroring schemas/player.schema.json and schemas/metadata.schema.json
 */

// ---- player.schema.json ----

export interface PlayerChunk {
  chunk_id: number;
  start: number;
  end: number;
  /** Relative path from output/{video_id}/, e.g. "audio/0001.wav". Empty string when no TTS audio exists. */
  audio: string;
  subtitle_ja: string;
  narration_ja: string;
  summary: string;
}

export interface PlayerJson {
  video_id: string;
  audio_offset: number;
  chunks: PlayerChunk[];
}

// ---- metadata.schema.json ----

export type ProcessingStatus =
  | "created"
  | "metadata_loaded"
  | "subtitle_fetched"
  | "subtitle_normalized"
  | "chunked"
  | "translated"
  | "narration_script_created"
  | "tts_generated"
  | "sync_generated"
  | "completed"
  | "failed_no_subtitle"
  | "failed_translation"
  | "failed_tts"
  | "failed_sync"
  | "failed_unknown";

export interface Metadata {
  video_id: string;
  url: string;
  title: string;
  channel: string;
  duration: number;
  created_at: string;
  status: ProcessingStatus;
}

// ---- UI-only types ----

/** Slim summary returned by GET /api/videos */
export interface VideoSummary {
  video_id: string;
  title: string;
  channel: string;
  duration: number;
  status: ProcessingStatus;
  thumbnail_url: string;
}

/** @deprecated Stub type replaced by ProcessResult in /api/process/route.ts */
export interface ProcessJobResult {
  jobId: string;
  status: "queued";
}

export interface ProcessApiResult {
  video_id: string;
  status: "started" | "already_processed" | "in_progress";
}

export interface JobStatus {
  video_id: string;
  /** Current pipeline status. "running" means the process is alive but no metadata yet. */
  status: ProcessingStatus | "running" | "failed_unknown";
  started_at: string | null;
  exit_code: number | null;
  stderr?: string;
}
