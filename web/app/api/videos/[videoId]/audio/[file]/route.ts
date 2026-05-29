import { NextRequest } from "next/server";
import fs from "fs";
import { getAudioFilePath } from "@/lib/output-dir";

export const dynamic = "force-dynamic";

/**
 * Serves a chunk's TTS audio file (output/{videoId}/audio/NNNN.wav).
 *
 * The JapaneseAudio component requests `/api/videos/{videoId}/audio/{file}`
 * and seeks within the clip (audio.currentTime), so this handler supports
 * HTTP Range requests. Per-chunk clips are small (a few seconds of WAV), so
 * the file is read into memory and sliced rather than streamed — this avoids
 * Node-stream/Web-Response body mismatches and keeps the handler simple.
 */
export async function GET(
  req: NextRequest,
  ctx: RouteContext<"/api/videos/[videoId]/audio/[file]">
): Promise<Response> {
  const { videoId, file } = await ctx.params;

  let audioPath: string;
  try {
    // getAudioFilePath validates the videoId and basename-sanitizes the file
    // (guards against path traversal).
    audioPath = getAudioFilePath(videoId, file);
  } catch {
    return new Response("Invalid videoId", { status: 400 });
  }

  // Only ever serve .wav files produced by the pipeline.
  if (!audioPath.toLowerCase().endsWith(".wav")) {
    return new Response("Not found", { status: 404 });
  }

  let data: Buffer;
  try {
    const stat = fs.statSync(audioPath);
    if (!stat.isFile()) {
      return new Response("Not found", { status: 404 });
    }
    data = fs.readFileSync(audioPath);
  } catch {
    return new Response("Not found", { status: 404 });
  }

  const total = data.length;
  const baseHeaders: Record<string, string> = {
    "Content-Type": "audio/wav",
    "Accept-Ranges": "bytes",
    "Cache-Control": "no-cache",
  };

  // Range request: serve the requested byte slice with 206.
  const rangeHeader = req.headers.get("range");
  if (rangeHeader) {
    const match = /^bytes=(\d*)-(\d*)$/.exec(rangeHeader.trim());
    if (match) {
      const startStr = match[1];
      const endStr = match[2];

      let start: number;
      let end: number;
      if (startStr === "" && endStr !== "") {
        // suffix range: last N bytes
        start = Math.max(0, total - Number(endStr));
        end = total - 1;
      } else {
        start = startStr === "" ? 0 : Number(startStr);
        end = endStr === "" ? total - 1 : Number(endStr);
      }

      // Unsatisfiable range.
      if (
        !Number.isFinite(start) ||
        !Number.isFinite(end) ||
        start > end ||
        start >= total
      ) {
        return new Response("Range Not Satisfiable", {
          status: 416,
          headers: { "Content-Range": `bytes */${total}` },
        });
      }

      end = Math.min(end, total - 1);
      const slice = data.subarray(start, end + 1);
      return new Response(new Uint8Array(slice), {
        status: 206,
        headers: {
          ...baseHeaders,
          "Content-Range": `bytes ${start}-${end}/${total}`,
          "Content-Length": String(slice.length),
        },
      });
    }
  }

  // No (valid) Range header: serve the whole file.
  return new Response(new Uint8Array(data), {
    status: 200,
    headers: {
      ...baseHeaders,
      "Content-Length": String(total),
    },
  });
}
