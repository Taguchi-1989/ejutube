import fs from "fs";
import { listVideoIds, getMetadataPath } from "@/lib/output-dir";
import type { Metadata, VideoSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const ids = listVideoIds();

  const summaries: VideoSummary[] = ids.flatMap((videoId) => {
    const metaPath = getMetadataPath(videoId);
    try {
      const raw = fs.readFileSync(metaPath, "utf-8");
      const meta: Metadata = JSON.parse(raw);
      const summary: VideoSummary = {
        video_id: meta.video_id,
        title: meta.title,
        channel: meta.channel,
        duration: meta.duration,
        status: meta.status,
        thumbnail_url: `https://img.youtube.com/vi/${meta.video_id}/mqdefault.jpg`,
      };
      return [summary];
    } catch {
      return [];
    }
  });

  return Response.json(summaries);
}
