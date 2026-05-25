"use client";

import { useEffect, useRef } from "react";
import type { PlayerChunk } from "@/lib/types";

interface ChapterListProps {
  chunks: PlayerChunk[];
  currentChunkId: number | null;
  onChunkClick: (chunk: PlayerChunk) => void;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function ChapterList({ chunks, currentChunkId, onChunkClick }: ChapterListProps) {
  const activeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [currentChunkId]);

  return (
    <div className="flex flex-col gap-1">
      {chunks.map((chunk) => {
        const isActive = chunk.chunk_id === currentChunkId;
        return (
          <button
            key={chunk.chunk_id}
            ref={isActive ? activeRef : null}
            onClick={() => onChunkClick(chunk)}
            className="w-full text-left px-3 py-2 rounded-md transition-colors"
            style={{
              background: isActive ? "var(--chunk-active-bg)" : "transparent",
              border: `1px solid ${isActive ? "var(--chunk-active-border)" : "transparent"}`,
              color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
            }}
          >
            <div className="flex items-baseline gap-2">
              <span
                className="text-xs font-mono tabular-nums shrink-0"
                style={{ color: isActive ? "var(--accent-blue)" : "var(--text-muted)" }}
              >
                {formatTime(chunk.start)}
              </span>
              <span className="text-sm leading-snug line-clamp-2">
                {chunk.subtitle_ja}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
