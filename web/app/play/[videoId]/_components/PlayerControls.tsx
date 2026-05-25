"use client";

interface PlayerControlsProps {
  isPlaying: boolean;
  onPlayPause: () => void;
  onPrevChunk: () => void;
  onNextChunk: () => void;
  jpAudioEnabled: boolean;
  onToggleJpAudio: () => void;
  ytAudioEnabled: boolean;
  onToggleYtAudio: () => void;
  captionsEnabled: boolean;
  onToggleCaptions: () => void;
  audioOffset: number;
  onAudioOffsetChange: (value: number) => void;
  onSaveOffset: () => void;
}

export function PlayerControls({
  isPlaying,
  onPlayPause,
  onPrevChunk,
  onNextChunk,
  jpAudioEnabled,
  onToggleJpAudio,
  ytAudioEnabled,
  onToggleYtAudio,
  captionsEnabled,
  onToggleCaptions,
  audioOffset,
  onAudioOffsetChange,
  onSaveOffset,
}: PlayerControlsProps) {
  return (
    <div
      className="flex flex-wrap items-center gap-2 px-3 py-2 rounded-lg"
      style={{
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-subtle)",
      }}
    >
      {/* Transport */}
      <div className="flex items-center gap-1">
        <button
          onClick={onPrevChunk}
          title="前のチャンク (←)"
          aria-label="前のチャンクへ"
          className="px-2 py-1 rounded text-sm transition-colors hover:opacity-80"
          style={{
            background: "var(--bg-overlay)",
            color: "var(--text-secondary)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          &#9664;&#9664;
        </button>

        <button
          onClick={onPlayPause}
          title="再生 / 停止 (Space)"
          aria-label={isPlaying ? "一時停止" : "再生"}
          className="px-3 py-1 rounded text-sm font-medium transition-colors"
          style={{
            background: isPlaying ? "var(--accent-blue)" : "var(--bg-overlay)",
            color: isPlaying ? "#fff" : "var(--text-primary)",
            border: `1px solid ${isPlaying ? "var(--accent-blue)" : "var(--border-default)"}`,
          }}
        >
          {isPlaying ? "停止" : "再生"}
        </button>

        <button
          onClick={onNextChunk}
          title="次のチャンク (→)"
          aria-label="次のチャンクへ"
          className="px-2 py-1 rounded text-sm transition-colors hover:opacity-80"
          style={{
            background: "var(--bg-overlay)",
            color: "var(--text-secondary)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          &#9654;&#9654;
        </button>
      </div>

      <div
        className="w-px h-5 self-center"
        style={{ background: "var(--border-subtle)" }}
      />

      {/* Toggle buttons */}
      <div className="flex items-center gap-1 flex-wrap">
        <ToggleButton
          label="日本語音声"
          active={jpAudioEnabled}
          onClick={onToggleJpAudio}
          title="日本語音声のオン/オフ"
        />
        <ToggleButton
          label="YouTube音声"
          active={ytAudioEnabled}
          onClick={onToggleYtAudio}
          title="YouTube音声のオン/オフ"
        />
        <ToggleButton
          label="英語字幕"
          active={captionsEnabled}
          onClick={onToggleCaptions}
          title="英語字幕のオン/オフ"
        />
      </div>

      <div
        className="w-px h-5 self-center hidden sm:block"
        style={{ background: "var(--border-subtle)" }}
      />

      {/* Audio offset */}
      <div className="flex items-center gap-2 ml-auto">
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          音ズレ補正
        </span>
        <button
          onClick={() =>
            onAudioOffsetChange(Math.round((audioOffset - 0.1) * 10) / 10)
          }
          title="音声を 0.1s 早める ([)"
          aria-label="音声を0.1秒早める"
          className="px-2 py-0.5 rounded text-xs"
          style={{
            background: "var(--bg-overlay)",
            color: "var(--text-secondary)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          -0.1s
        </button>
        <span
          className="text-xs font-mono tabular-nums min-w-[3rem] text-center"
          style={{ color: "var(--accent-amber)" }}
        >
          {audioOffset >= 0 ? "+" : ""}
          {audioOffset.toFixed(1)}s
        </span>
        <button
          onClick={() =>
            onAudioOffsetChange(Math.round((audioOffset + 0.1) * 10) / 10)
          }
          title="音声を 0.1s 遅らせる (])"
          aria-label="音声を0.1秒遅らせる"
          className="px-2 py-0.5 rounded text-xs"
          style={{
            background: "var(--bg-overlay)",
            color: "var(--text-secondary)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          +0.1s
        </button>
        <button
          onClick={onSaveOffset}
          className="px-2 py-0.5 rounded text-xs"
          style={{
            background: "var(--accent-amber-dim)",
            color: "var(--accent-amber)",
            border: "1px solid var(--accent-amber)",
          }}
        >
          保存
        </button>
      </div>
    </div>
  );
}

function ToggleButton({
  label,
  active,
  onClick,
  title,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  title: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="px-2 py-0.5 rounded text-xs transition-colors"
      style={{
        background: active ? "var(--accent-green-dim)" : "var(--bg-overlay)",
        color: active ? "var(--accent-green)" : "var(--text-muted)",
        border: `1px solid ${active ? "var(--accent-green)" : "var(--border-subtle)"}`,
      }}
    >
      {label}
    </button>
  );
}
