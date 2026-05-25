"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import type { VideoSummary, ProcessingStatus } from "@/lib/types";

function statusLabel(status: ProcessingStatus): { label: string; color: string; bg: string } {
  switch (status) {
    case "completed":
      return { label: "完了", color: "var(--accent-green)", bg: "var(--accent-green-dim)" };
    case "created":
    case "metadata_loaded":
    case "subtitle_fetched":
    case "subtitle_normalized":
    case "chunked":
    case "translated":
    case "narration_script_created":
    case "tts_generated":
    case "sync_generated":
      return { label: "処理中", color: "var(--accent-amber)", bg: "var(--accent-amber-dim)" };
    default:
      return { label: "エラー", color: "var(--accent-red)", bg: "#2a0a0a" };
  }
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [loadingVideos, setLoadingVideos] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    async function loadVideos() {
      try {
        const res = await fetch("/api/videos");
        if (res.ok) {
          const data: VideoSummary[] = await res.json();
          setVideos(data);
        }
      } finally {
        setLoadingVideos(false);
      }
    }
    loadVideos();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;

    setSubmitting(true);
    setSubmitError(null);

    try {
      const res = await fetch("/api/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });

      if (res.status === 400) {
        const body = await res.json() as { error?: string };
        setSubmitError(body.error ?? "エラーが発生しました。URLを確認してください。");
        return;
      }

      if (!res.ok) {
        setSubmitError("エラーが発生しました。URLを確認してください。");
        return;
      }

      const data = await res.json() as { video_id: string };
      // Redirect immediately — the play page handles "not yet ready" state.
      router.push(`/play/${data.video_id}`);
    } catch {
      setSubmitError("ネットワークエラーが発生しました。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}
    >
      {/* Header */}
      <header
        className="px-6 py-4 shrink-0"
        style={{
          background: "var(--bg-surface)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div className="max-w-4xl mx-auto flex items-baseline gap-3">
          <h1
            className="text-lg font-semibold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            ejutube
          </h1>
          <span className="text-sm" style={{ color: "var(--text-muted)" }}>
            英語チュートリアル学習プレイヤー
          </span>
        </div>
      </header>

      <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-8 flex flex-col gap-8">
        {/* URL input section */}
        <section>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <label
              htmlFor="youtube-url"
              className="text-sm font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              YouTube URLを入力して処理を開始
            </label>
            <div className="flex gap-2">
              <input
                id="youtube-url"
                ref={inputRef}
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                required
                className="flex-1 px-3 py-2 rounded-md text-sm"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-primary)",
                  outline: "none",
                }}
                onFocus={(e) => {
                  (e.target as HTMLInputElement).style.borderColor = "var(--accent-blue)";
                }}
                onBlur={(e) => {
                  (e.target as HTMLInputElement).style.borderColor = "var(--border-default)";
                }}
              />
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 rounded-md text-sm font-medium transition-opacity disabled:opacity-50"
                style={{
                  background: "var(--accent-blue)",
                  color: "#fff",
                }}
              >
                {submitting ? "送信中..." : "処理開始"}
              </button>
            </div>
            {submitError && (
              <p
                className="text-sm"
                style={{ color: "var(--accent-red)" }}
              >
                {submitError}
              </p>
            )}
          </form>
        </section>

        {/* Video list section */}
        <section>
          <h2
            className="text-sm font-medium mb-4"
            style={{ color: "var(--text-secondary)" }}
          >
            処理済み動画
          </h2>

          {loadingVideos ? (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              読み込み中...
            </p>
          ) : videos.length === 0 ? (
            <div
              className="rounded-lg p-6 text-center"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                処理済みの動画はまだありません
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                上のフォームにYouTube URLを入力してください
              </p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {videos.map((video) => {
                const { label, color, bg } = statusLabel(video.status);
                return (
                  <a
                    key={video.video_id}
                    href={`/play/${video.video_id}`}
                    className="flex gap-3 p-3 rounded-lg transition-colors group"
                    style={{
                      background: "var(--bg-surface)",
                      border: "1px solid var(--border-subtle)",
                      textDecoration: "none",
                      color: "inherit",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLAnchorElement).style.borderColor =
                        "var(--border-default)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLAnchorElement).style.borderColor =
                        "var(--border-subtle)";
                    }}
                  >
                    {/* Thumbnail */}
                    <div
                      className="shrink-0 rounded overflow-hidden"
                      style={{
                        width: 100,
                        height: 56,
                        background: "var(--bg-elevated)",
                      }}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={video.thumbnail_url}
                        alt={video.title}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    </div>

                    {/* Info */}
                    <div className="flex flex-col gap-1 min-w-0 flex-1">
                      <p
                        className="text-sm font-medium leading-snug line-clamp-2"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {video.title}
                      </p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {video.channel}
                        <span className="mx-1">·</span>
                        {formatDuration(video.duration)}
                      </p>
                      <span
                        className="mt-auto text-xs px-1.5 py-0.5 rounded self-start"
                        style={{ color, background: bg }}
                      >
                        {label}
                      </span>
                    </div>
                  </a>
                );
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
