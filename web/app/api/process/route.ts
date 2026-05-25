import { NextRequest } from "next/server";
import fs from "fs";
import { getPlayerJsonPath, validateVideoId } from "@/lib/output-dir";
import { startJob } from "@/lib/jobs";
import type { ProcessApiResult } from "@/lib/types";

export const dynamic = "force-dynamic";

/** YouTube video_id: 11 chars from [A-Za-z0-9_-]. */
const VIDEO_ID_RE = /[A-Za-z0-9_-]{11}/;

/**
 * Extract an 11-character YouTube video_id from a URL or bare ID string.
 * Returns null if no valid video_id is found.
 *
 * Handles:
 *   https://www.youtube.com/watch?v=XXXXXXXXXXX
 *   https://youtu.be/XXXXXXXXXXX
 *   https://www.youtube.com/embed/XXXXXXXXXXX
 *   https://www.youtube.com/shorts/XXXXXXXXXXX
 *   XXXXXXXXXXX  (bare id)
 */
function extractVideoId(url: string): string | null {
  // Bare 11-char id
  if (/^[A-Za-z0-9_-]{11}$/.test(url.trim())) {
    return url.trim();
  }

  // Try URL-based extraction
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }

  const hostname = parsed.hostname.replace(/^www\./, "");

  if (hostname === "youtu.be") {
    const id = parsed.pathname.slice(1).split("?")[0];
    if (VIDEO_ID_RE.test(id)) return id.match(VIDEO_ID_RE)![0];
  }

  if (hostname === "youtube.com") {
    // watch?v=
    const v = parsed.searchParams.get("v");
    if (v && VIDEO_ID_RE.test(v)) return v.match(VIDEO_ID_RE)![0];

    // /embed/ID, /shorts/ID
    const match = parsed.pathname.match(/\/(embed|shorts|v)\/([A-Za-z0-9_-]{11})/);
    if (match) return match[2];
  }

  return null;
}

export async function POST(req: NextRequest): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (
    typeof body !== "object" ||
    body === null ||
    !("url" in body) ||
    typeof (body as Record<string, unknown>).url !== "string"
  ) {
    return Response.json(
      { error: "Body must be { url: string }" },
      { status: 400 }
    );
  }

  const url = (body as { url: string }).url.trim();

  const videoId = extractVideoId(url);
  if (!videoId) {
    return Response.json({ error: "Invalid YouTube URL" }, { status: 400 });
  }

  // Validate with the canonical helper (guards against regex edge cases)
  try {
    validateVideoId(videoId);
  } catch {
    return Response.json({ error: "Invalid YouTube URL" }, { status: 400 });
  }

  // Already fully processed?
  const playerPath = getPlayerJsonPath(videoId);
  if (fs.existsSync(playerPath)) {
    const result: ProcessApiResult = { video_id: videoId, status: "already_processed" };
    return Response.json(result, { status: 200 });
  }

  // Kick off the pipeline (or return the already-running job).
  // startJob is atomic: it performs the check-and-insert in a single
  // synchronous block, eliminating the TOCTOU race between two concurrent
  // POSTs for the same videoId.
  const { created } = startJob(videoId, url);

  if (!created) {
    const result: ProcessApiResult = { video_id: videoId, status: "in_progress" };
    return Response.json(result, { status: 200 });
  }

  const result: ProcessApiResult = { video_id: videoId, status: "started" };
  return Response.json(result, { status: 201 });
}
