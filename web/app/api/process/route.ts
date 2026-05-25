import { NextRequest } from "next/server";
import type { ProcessJobResult } from "@/lib/types";

export const dynamic = "force-dynamic";

// TODO: Integrate with the Python pipeline (Stage 1A/1C/1D).
// Currently a stub that logs the URL and returns a queued job response.

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

  const url = (body as { url: string }).url;
  console.log("[process] Received URL:", url);

  const result: ProcessJobResult = {
    jobId: "stub",
    status: "queued",
  };

  return Response.json(result, { status: 202 });
}
