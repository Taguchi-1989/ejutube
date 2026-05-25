/**
 * Minimal local types for YouTube IFrame API.
 * We use these instead of @types/youtube globals to avoid UMD module conflicts
 * in strict TypeScript ES module mode.
 */

export interface YTPlayer {
  playVideo(): void;
  pauseVideo(): void;
  stopVideo(): void;
  seekTo(seconds: number, allowSeekAhead?: boolean): void;
  mute(): void;
  unMute(): void;
  setVolume(volume: number): void;
  getVolume(): number;
  getCurrentTime(): number;
  getDuration(): number;
  getPlayerState(): number;
  destroy(): void;
}

export const YT_PLAYER_STATE = {
  UNSTARTED: -1,
  ENDED: 0,
  PLAYING: 1,
  PAUSED: 2,
  BUFFERING: 3,
  CUED: 5,
} as const;

export interface YTPlayerVars {
  autoplay?: 0 | 1;
  cc_load_policy?: 0 | 1;
  cc_lang_pref?: string;
  rel?: 0 | 1;
  modestbranding?: 0 | 1;
  playsinline?: 0 | 1;
}

export interface YTPlayerOptions {
  videoId: string;
  playerVars?: YTPlayerVars;
  events?: {
    onReady?: (event: { target: YTPlayer }) => void;
    onStateChange?: (event: { data: number; target: YTPlayer }) => void;
    onError?: (event: { data: number }) => void;
  };
}

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    YT: {
      Player: new (container: HTMLElement | string, options: YTPlayerOptions) => YTPlayer;
      PlayerState: typeof YT_PLAYER_STATE;
    };
    onYouTubeIframeAPIReady: () => void;
  }
}
