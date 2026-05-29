"use client";

import { useMemo } from "react";
import type { PlayerChunk } from "@/lib/types";

/**
 * Binary search for the current chunk given currentTime.
 * Returns the chunk whose start <= currentTime < end, or null if none.
 */
function findCurrentChunk(
  chunks: PlayerChunk[],
  currentTime: number
): PlayerChunk | null {
  if (chunks.length === 0) return null;

  let lo = 0;
  let hi = chunks.length - 1;

  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const chunk = chunks[mid];

    if (currentTime < chunk.start) {
      hi = mid - 1;
    } else if (currentTime >= chunk.end) {
      lo = mid + 1;
    } else {
      return chunk;
    }
  }

  // If past the last chunk's end, return the last chunk
  if (chunks.length > 0 && currentTime >= chunks[chunks.length - 1].start) {
    return chunks[chunks.length - 1];
  }

  return null;
}

export function useChunkSync(
  chunks: PlayerChunk[],
  currentTime: number
): PlayerChunk | null {
  return useMemo(
    () => findCurrentChunk(chunks, currentTime),
    [chunks, currentTime]
  );
}
