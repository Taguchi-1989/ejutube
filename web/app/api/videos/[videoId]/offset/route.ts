import { NextRequest } from "next/server";
import fs from "fs";
import { getPlayerJsonPath } from "@/lib/output-dir";
import type { PlayerJson } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function PATCH(
  req: NextRequest,
  ctx: RouteContext<"/api/videos/[videoId]/offset">
): Promise<Response> {
  const { videoId } = await ctx.params;

  let playerPath: string;
  try {
    playerPath = getPlayerJsonPath(videoId);
  } catch {
    return Response.json({ error: "Invalid videoId" }, { status: 400 });
  }

  if (!fs.existsSync(playerPath)) {
    return Response.json({ error: "player.json not found" }, { status: 404 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (
    typeof body !== "object" ||
    body === null ||
    !("audio_offset" in body) ||
    typeof (body as Record<string, unknown>).audio_offset !== "number" ||
    // Reject NaN/Infinity — they pass `typeof === "number"` but serialize to
    // null in JSON, which would corrupt the stored audio_offset.
    !Number.isFinite((body as Record<string, unknown>).audio_offset)
  ) {
    return Response.json(
      { error: "Body must be { audio_offset: number }" },
      { status: 400 }
    );
  }

  const rawOffset = (body as { audio_offset: number }).audio_offset;
  // Clamp to [-60, 60] seconds to prevent runaway values
  const newOffset = Math.max(-60, Math.min(60, rawOffset));

  try {
    const raw = fs.readFileSync(playerPath, "utf-8");
    const player: PlayerJson = JSON.parse(raw);
    // Note: concurrent pipeline re-runs (build_player_json) may clobber this
    // write. Accepted tradeoff for a local single-user tool.
    player.audio_offset = newOffset;
    fs.writeFileSync(playerPath, JSON.stringify(player, null, 2), "utf-8");
    return Response.json({ audio_offset: player.audio_offset });
  } catch {
    return Response.json({ error: "Failed to update player.json" }, { status: 500 });
  }
}
