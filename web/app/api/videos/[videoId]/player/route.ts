import { NextRequest } from "next/server";
import fs from "fs";
import { getPlayerJsonPath } from "@/lib/output-dir";
import type { PlayerJson } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  ctx: RouteContext<"/api/videos/[videoId]/player">
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

  try {
    const raw = fs.readFileSync(playerPath, "utf-8");
    const player: PlayerJson = JSON.parse(raw);
    return Response.json(player);
  } catch {
    return Response.json({ error: "Failed to read player.json" }, { status: 500 });
  }
}
