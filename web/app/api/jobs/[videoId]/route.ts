import { NextRequest } from "next/server";
import fs from "fs";
import { validateVideoId, getMetadataPath } from "@/lib/output-dir";
import { getJob } from "@/lib/jobs";
import type { Metadata, JobStatus, ProcessingStatus } from "@/lib/types";

const VALID_STATUSES = new Set<ProcessingStatus>([
  "created",
  "metadata_loaded",
  "subtitle_fetched",
  "subtitle_normalized",
  "chunked",
  "translated",
  "narration_script_created",
  "tts_generated",
  "sync_generated",
  "completed",
  "failed_no_subtitle",
  "failed_translation",
  "failed_tts",
  "failed_sync",
  "failed_unknown",
]);

function validateStatus(s: unknown): ProcessingStatus {
  if (typeof s === "string" && VALID_STATUSES.has(s as ProcessingStatus)) {
    return s as ProcessingStatus;
  }
  return "failed_unknown";
}

export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  ctx: RouteContext<"/api/jobs/[videoId]">
): Promise<Response> {
  const { videoId } = await ctx.params;

  try {
    validateVideoId(videoId);
  } catch {
    return Response.json({ error: "Invalid videoId" }, { status: 400 });
  }

  // Check in-memory registry first.
  const job = getJob(videoId);
  if (job) {
    const isRunning = job.exit_code === null;
    const failed = !isRunning && job.exit_code !== 0;

    // If the process has exited cleanly, try to read the actual status from metadata.json.
    let resolvedStatus: JobStatus["status"] = isRunning ? "running" : "completed";
    if (!isRunning) {
      try {
        const metaPath = getMetadataPath(videoId);
        if (fs.existsSync(metaPath)) {
          const meta: Metadata = JSON.parse(fs.readFileSync(metaPath, "utf-8"));
          resolvedStatus = validateStatus(meta.status);
        }
      } catch {
        // fall through to exit_code-based status
        resolvedStatus = failed ? "failed_unknown" : "completed";
      }
    }

    const response: JobStatus = {
      video_id: videoId,
      status: resolvedStatus,
      started_at: job.started_at,
      exit_code: job.exit_code,
    };
    if (failed && job.stderr) {
      response.stderr = job.stderr;
    }
    return Response.json(response);
  }

  // Not in memory (server restart). Fall back to metadata.json.
  const metaPath = getMetadataPath(videoId);
  if (!fs.existsSync(metaPath)) {
    return Response.json({ error: "Job not found" }, { status: 404 });
  }

  try {
    const meta: Metadata = JSON.parse(fs.readFileSync(metaPath, "utf-8"));
    const response: JobStatus = {
      video_id: videoId,
      status: validateStatus(meta.status),
      started_at: null,
      exit_code: null,
    };
    return Response.json(response);
  } catch {
    return Response.json({ error: "Failed to read metadata" }, { status: 500 });
  }
}
