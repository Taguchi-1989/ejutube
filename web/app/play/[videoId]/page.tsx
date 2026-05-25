"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useParams } from "next/navigation";
import type { PlayerJson, PlayerChunk, ProcessingStatus, JobStatus } from "@/lib/types";
import type { YTPlayer } from "@/lib/youtube-types";
import { YouTubePlayer } from "./_components/YouTubePlayer";
import { JapaneseAudio } from "./_components/JapaneseAudio";
import { PlayerControls } from "./_components/PlayerControls";
import { ChapterList } from "./_components/ChapterList";
import { useChunkSync } from "./_components/useChunkSync";

const PROCESSING_STAGES: ProcessingStatus[] = [
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
];

function stageProgress(status: ProcessingStatus | "running" | "failed_unknown"): number {
  if (status === "running" || status === "created") return 5;
  const idx = PROCESSING_STAGES.indexOf(status as ProcessingStatus);
  if (idx < 0) return 0;
  return Math.round(((idx + 1) / PROCESSING_STAGES.length) * 100);
}

function stageLabel(status: ProcessingStatus | "running" | "failed_unknown"): string {
  const labels: Partial<Record<ProcessingStatus | "running" | "failed_unknown", string>> = {
    running: "起動中",
    created: "作成済み",
    metadata_loaded: "メタデータ取得",
    subtitle_fetched: "字幕取得",
    subtitle_normalized: "字幕正規化",
    chunked: "チャンク分割",
    translated: "翻訳",
    narration_script_created: "ナレーション生成",
    tts_generated: "音声合成",
    sync_generated: "同期生成",
    completed: "完了",
    failed_no_subtitle: "失敗: 字幕なし",
    failed_translation: "失敗: 翻訳エラー",
    failed_tts: "失敗: 音声合成エラー",
    failed_sync: "失敗: 同期エラー",
    failed_unknown: "失敗: 不明なエラー",
  };
  return labels[status] ?? status;
}

function isFailed(status: ProcessingStatus | "running" | "failed_unknown"): boolean {
  return status.startsWith("failed_");
}

function isComplete(status: ProcessingStatus | "running" | "failed_unknown"): boolean {
  return status === "completed";
}

/**
 * Polls /api/jobs/{videoId} every 3s while enabled.
 * Stops automatically when status is completed or a failed_* state.
 */
function useJobStatus(videoId: string, enabled: boolean) {
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`/api/jobs/${videoId}`);
        if (!cancelled && res.ok) {
          const data = await res.json() as JobStatus;
          setJobStatus(data);
        }
      } catch {
        // network error — keep polling
      }
    }

    poll();
    const id = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [videoId, enabled]);

  return jobStatus;
}

export default function PlayerPage() {
  const params = useParams<{ videoId: string }>();
  const videoId = params.videoId;

  const [playerData, setPlayerData] = useState<PlayerJson | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  /** True while waiting for the pipeline to complete (player.json not yet available). */
  const [processingPending, setProcessingPending] = useState(false);
  const [stderrExpanded, setStderrExpanded] = useState(false);

  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [jpAudioEnabled, setJpAudioEnabled] = useState(true);
  const [ytAudioEnabled, setYtAudioEnabled] = useState(false);
  const [captionsEnabled, setCaptionsEnabled] = useState(true);
  const [audioOffset, setAudioOffset] = useState(0);
  const [activeTab, setActiveTab] = useState<"chapters" | "original" | "summary" | "commands" | "glossary">("chapters");

  const playerRef = useRef<YTPlayer | null>(null);

  // Load player.json. If it returns 404, switch to polling mode.
  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await fetch(`/api/videos/${videoId}/player`);
        if (res.status === 404) {
          // Pipeline may still be running — switch to polling panel.
          setProcessingPending(true);
          return;
        }
        if (!res.ok) {
          throw new Error(`player.json の読み込みに失敗しました (${res.status})`);
        }
        const data: PlayerJson = await res.json();
        setPlayerData(data);
        setAudioOffset(data.audio_offset);
        setProcessingPending(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : "不明なエラー");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [videoId]);

  // Poll job status while pipeline is running; reload player.json when done.
  const jobStatus = useJobStatus(videoId, processingPending);
  useEffect(() => {
    if (!jobStatus) return;
    if (isComplete(jobStatus.status)) {
      // Pipeline finished — load the player data.
      setProcessingPending(false);
      fetch(`/api/videos/${videoId}/player`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data: PlayerJson | null) => {
          if (data) {
            setPlayerData(data);
            setAudioOffset(data.audio_offset);
          }
        })
        .catch(() => {});
    }
  }, [jobStatus, videoId]);

  const currentChunk = useChunkSync(playerData?.chunks ?? [], currentTime);

  const handleTimeUpdate = useCallback((seconds: number) => {
    setCurrentTime(seconds);
  }, []);

  const handleStateChange = useCallback((state: number) => {
    // YT.PlayerState.PLAYING = 1, PAUSED = 2, ENDED = 0
    if (state === 1) {
      setIsPlaying(true);
    } else if (state === 2 || state === 0) {
      setIsPlaying(false);
    }
  }, []);

  const handlePlayPause = useCallback(() => {
    if (!playerRef.current) return;
    try {
      const state = playerRef.current.getPlayerState();
      if (state === 1) {
        playerRef.current.pauseVideo();
      } else {
        playerRef.current.playVideo();
      }
    } catch {
      // player not ready
    }
  }, []);

  const seekToChunk = useCallback((chunk: PlayerChunk) => {
    if (!playerRef.current) return;
    try {
      playerRef.current.seekTo(chunk.start, true);
      setCurrentTime(chunk.start);
    } catch {
      // ignore
    }
  }, []);

  const handlePrevChunk = useCallback(() => {
    if (!playerData) return;
    const chunks = playerData.chunks;
    const idx = chunks.findIndex((c) => c.chunk_id === currentChunk?.chunk_id);
    if (idx > 0) seekToChunk(chunks[idx - 1]);
    else if (chunks.length > 0) seekToChunk(chunks[0]);
  }, [playerData, currentChunk, seekToChunk]);

  const handleNextChunk = useCallback(() => {
    if (!playerData) return;
    const chunks = playerData.chunks;
    const idx = chunks.findIndex((c) => c.chunk_id === currentChunk?.chunk_id);
    if (idx >= 0 && idx < chunks.length - 1) seekToChunk(chunks[idx + 1]);
  }, [playerData, currentChunk, seekToChunk]);

  const handleSaveOffset = useCallback(async () => {
    try {
      await fetch(`/api/videos/${videoId}/offset`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audio_offset: audioOffset }),
      });
    } catch {
      // silently ignore
    }
  }, [videoId, audioOffset]);

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      switch (e.key) {
        case " ":
          e.preventDefault();
          handlePlayPause();
          break;
        case "ArrowLeft":
          e.preventDefault();
          handlePrevChunk();
          break;
        case "ArrowRight":
          e.preventDefault();
          handleNextChunk();
          break;
        case "[":
          setAudioOffset((prev) => Math.round((prev - 0.1) * 10) / 10);
          break;
        case "]":
          setAudioOffset((prev) => Math.round((prev + 0.1) * 10) / 10);
          break;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handlePlayPause, handlePrevChunk, handleNextChunk]);

  if (loading) {
    return (
      <div
        className="flex items-center justify-center min-h-screen"
        style={{ background: "var(--bg-base)", color: "var(--text-secondary)" }}
      >
        <p className="text-sm">読み込み中...</p>
      </div>
    );
  }

  // Pipeline still running — show processing panel.
  if (processingPending) {
    const currentStatus = jobStatus?.status ?? "running";
    const failed = isFailed(currentStatus);
    const progressPct = stageProgress(currentStatus);

    return (
      <div
        className="flex flex-col items-center justify-center min-h-screen gap-6 px-4"
        style={{ background: "var(--bg-base)" }}
      >
        <div
          className="w-full max-w-md rounded-xl p-6 flex flex-col gap-4"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <div className="flex items-center gap-2">
            <h1 className="text-base font-medium" style={{ color: "var(--text-primary)" }}>
              {failed ? "処理に失敗しました" : "処理中..."}
            </h1>
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-xs" style={{ color: "var(--text-muted)" }}>
              <span>現在のステージ: {stageLabel(currentStatus)}</span>
              <span>{progressPct}%</span>
            </div>
            <div
              className="w-full rounded-full overflow-hidden"
              style={{ height: 6, background: "var(--bg-elevated)" }}
            >
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${progressPct}%`,
                  background: failed ? "var(--accent-red)" : "var(--accent-blue)",
                }}
              />
            </div>
          </div>

          {failed && jobStatus?.stderr && (
            <div className="flex flex-col gap-1">
              <button
                className="text-xs text-left"
                style={{ color: "var(--text-muted)" }}
                onClick={() => setStderrExpanded((v) => !v)}
              >
                {stderrExpanded ? "エラー詳細を閉じる" : "エラー詳細を表示"}
              </button>
              {stderrExpanded && (
                <pre
                  className="text-xs p-3 rounded overflow-x-auto"
                  style={{
                    background: "var(--bg-elevated)",
                    color: "var(--accent-red)",
                    maxHeight: 200,
                    overflowY: "auto",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-all",
                  }}
                >
                  {jobStatus.stderr}
                </pre>
              )}
            </div>
          )}

          {!failed && (
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              完了後、自動的にプレイヤーが表示されます。
            </p>
          )}
        </div>

        <a
          href="/"
          className="text-sm underline"
          style={{ color: "var(--accent-blue)" }}
        >
          一覧に戻る
        </a>
      </div>
    );
  }

  if (error || !playerData) {
    return (
      <div
        className="flex flex-col items-center justify-center min-h-screen gap-4 px-4"
        style={{ background: "var(--bg-base)" }}
      >
        <p className="text-sm" style={{ color: "var(--accent-red)" }}>
          {error ?? "データが見つかりません"}
        </p>
        <a
          href="/"
          className="text-sm underline"
          style={{ color: "var(--accent-blue)" }}
        >
          トップに戻る
        </a>
      </div>
    );
  }

  const tabs: { key: typeof activeTab; label: string }[] = [
    { key: "chapters", label: "チャプター" },
    { key: "original", label: "原文" },
    { key: "summary", label: "要約" },
    { key: "commands", label: "コマンド" },
    { key: "glossary", label: "用語集" },
  ];

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}
    >
      {/* Header */}
      <header
        className="px-4 py-3 flex items-center gap-3 shrink-0"
        style={{
          background: "var(--bg-surface)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <a
          href="/"
          className="text-sm"
          style={{ color: "var(--text-muted)" }}
        >
          ← 一覧
        </a>
        <span style={{ color: "var(--border-subtle)" }}>|</span>
        <h1
          className="text-sm font-medium truncate"
          style={{ color: "var(--text-primary)" }}
        >
          {videoId}
        </h1>
        <span
          className="ml-auto text-xs font-mono"
          style={{ color: "var(--text-muted)" }}
        >
          {currentChunk
            ? `チャンク ${currentChunk.chunk_id} / ${playerData.chunks.length}`
            : `チャンク — / ${playerData.chunks.length}`}
        </span>
      </header>

      {/* Main layout */}
      <main className="flex-1 flex flex-col lg:flex-row gap-0 overflow-hidden">
        {/* Left column: video + controls */}
        <div
          className="flex flex-col gap-3 p-4 lg:w-[55%] lg:shrink-0"
          style={{ borderRight: "1px solid var(--border-subtle)" }}
        >
          {/* YouTube player */}
          <div className="rounded-lg overflow-hidden" style={{ background: "#000" }}>
            <YouTubePlayer
              videoId={videoId}
              onTimeUpdate={handleTimeUpdate}
              onStateChange={handleStateChange}
              playerRef={playerRef}
              isMuted={!ytAudioEnabled}
              captionsEnabled={captionsEnabled}
            />
          </div>

          {/* Controls */}
          <PlayerControls
            isPlaying={isPlaying}
            onPlayPause={handlePlayPause}
            onPrevChunk={handlePrevChunk}
            onNextChunk={handleNextChunk}
            jpAudioEnabled={jpAudioEnabled}
            onToggleJpAudio={() => setJpAudioEnabled((v) => !v)}
            ytAudioEnabled={ytAudioEnabled}
            onToggleYtAudio={() => setYtAudioEnabled((v) => !v)}
            captionsEnabled={captionsEnabled}
            onToggleCaptions={() => setCaptionsEnabled((v) => !v)}
            audioOffset={audioOffset}
            onAudioOffsetChange={setAudioOffset}
            onSaveOffset={handleSaveOffset}
          />

          {/* Keyboard shortcuts hint */}
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            キーボード: Space=再生停止 / ←→=チャンク移動 / []=音ズレ補正
          </p>
        </div>

        {/* Right column: subtitle panel */}
        <div className="flex flex-col flex-1 overflow-hidden">
          {/* Current subtitle */}
          <div
            className="px-4 pt-4 pb-3 shrink-0"
            style={{ borderBottom: "1px solid var(--border-subtle)" }}
          >
            <div
              className="rounded-lg p-4"
              style={{
                background: "var(--chunk-active-bg)",
                border: "1px solid var(--chunk-active-border)",
              }}
            >
              <p
                className="text-xs uppercase tracking-wider mb-2"
                style={{ color: "var(--accent-blue)", opacity: 0.7 }}
              >
                現在の日本語字幕
              </p>
              <p
                className="leading-relaxed"
                style={{
                  fontSize: "1.35rem",
                  color: "var(--text-primary)",
                  minHeight: "3rem",
                }}
              >
                {currentChunk?.subtitle_ja ?? "—"}
              </p>
            </div>

            {currentChunk?.narration_ja && (
              <div
                className="mt-3 rounded-lg p-3"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <p
                  className="text-xs uppercase tracking-wider mb-1.5"
                  style={{ color: "var(--text-muted)" }}
                >
                  読み上げテキスト
                </p>
                <p
                  className="text-sm leading-relaxed"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {currentChunk.narration_ja}
                </p>
              </div>
            )}
          </div>

          {/* Tabs */}
          <div
            className="flex gap-0 shrink-0"
            style={{ borderBottom: "1px solid var(--border-subtle)" }}
          >
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className="px-3 py-2 text-xs transition-colors"
                style={{
                  color:
                    activeTab === tab.key
                      ? "var(--text-primary)"
                      : "var(--text-muted)",
                  borderBottom:
                    activeTab === tab.key
                      ? "2px solid var(--accent-blue)"
                      : "2px solid transparent",
                  background: "transparent",
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-4">
            {activeTab === "chapters" && (
              <ChapterList
                chunks={playerData.chunks}
                currentChunkId={currentChunk?.chunk_id ?? null}
                onChunkClick={(chunk) => {
                  seekToChunk(chunk);
                }}
              />
            )}

            {activeTab === "original" && (
              <div className="flex flex-col gap-3">
                {playerData.chunks.map((chunk) => {
                  const isActive = chunk.chunk_id === currentChunk?.chunk_id;
                  return (
                    <div
                      key={chunk.chunk_id}
                      className="text-sm leading-relaxed p-2 rounded"
                      style={{
                        color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                        background: isActive ? "var(--chunk-active-bg)" : "transparent",
                      }}
                    >
                      <span
                        className="text-xs font-mono mr-2"
                        style={{ color: "var(--text-muted)" }}
                      >
                        {formatTime(chunk.start)}
                      </span>
                      {chunk.subtitle_ja}
                    </div>
                  );
                })}
              </div>
            )}

            {(activeTab === "summary" ||
              activeTab === "commands" ||
              activeTab === "glossary") && (
              <div className="flex items-center justify-center h-32">
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                  未生成
                </p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Japanese audio controller (no DOM output) */}
      <JapaneseAudio
        videoId={videoId}
        currentChunk={currentChunk}
        isPlaying={isPlaying}
        isEnabled={jpAudioEnabled}
        audioOffset={audioOffset}
        playerRef={playerRef}
      />
    </div>
  );
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
