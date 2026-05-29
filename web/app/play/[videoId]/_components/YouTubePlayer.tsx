"use client";

import { useEffect, useRef, useCallback } from "react";
import "@/lib/youtube-types";
import type { YTPlayer } from "@/lib/youtube-types";
import { YT_PLAYER_STATE } from "@/lib/youtube-types";

interface YouTubePlayerProps {
  videoId: string;
  onTimeUpdate: (seconds: number) => void;
  onStateChange?: (state: number) => void;
  playerRef: React.RefObject<YTPlayer | null>;
  isMuted: boolean;
  captionsEnabled: boolean;
}

export function YouTubePlayer({
  videoId,
  onTimeUpdate,
  onStateChange,
  playerRef,
  isMuted,
  captionsEnabled,
}: YouTubePlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isReadyRef = useRef(false);

  const startPolling = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(() => {
      if (playerRef.current && isReadyRef.current) {
        try {
          const t = playerRef.current.getCurrentTime();
          if (typeof t === "number" && !isNaN(t)) {
            onTimeUpdate(t);
          }
        } catch {
          // player may not be ready yet
        }
      }
    }, 250); // 4 Hz polling
  }, [onTimeUpdate, playerRef]);

  useEffect(() => {
    let mounted = true;
    // Capture the instance this effect creates so cleanup destroys exactly
    // that player, rather than reading the (possibly reassigned) ref.
    let createdPlayer: YTPlayer | null = null;

    function initPlayer() {
      if (!containerRef.current || !mounted) return;

      const player = new window.YT.Player(containerRef.current, {
        videoId,
        playerVars: {
          autoplay: 0,
          cc_load_policy: captionsEnabled ? 1 : 0,
          cc_lang_pref: "en",
          rel: 0,
          modestbranding: 1,
          playsinline: 1,
        },
        events: {
          onReady: (event) => {
            isReadyRef.current = true;
            if (isMuted) {
              event.target.mute();
            } else {
              event.target.setVolume(20);
            }
          },
          onStateChange: (event) => {
            onStateChange?.(event.data);
            if (event.data === YT_PLAYER_STATE.PLAYING) {
              startPolling();
            } else {
              if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
              }
            }
          },
        },
      });

      createdPlayer = player;
      (playerRef as React.MutableRefObject<YTPlayer | null>).current = player;
    }

    if (window.YT && window.YT.Player) {
      initPlayer();
    } else {
      const prevCallback = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        prevCallback?.();
        if (mounted) initPlayer();
      };

      if (!document.querySelector('script[src*="youtube.com/iframe_api"]')) {
        const script = document.createElement("script");
        script.src = "https://www.youtube.com/iframe_api";
        document.head.appendChild(script);
      }
    }

    return () => {
      mounted = false;
      if (intervalRef.current) clearInterval(intervalRef.current);
      try {
        createdPlayer?.destroy();
      } catch {
        // ignore
      }
      (playerRef as React.MutableRefObject<YTPlayer | null>).current = null;
      isReadyRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  // Sync mute state after player is ready
  useEffect(() => {
    if (!playerRef.current || !isReadyRef.current) return;
    try {
      if (isMuted) {
        playerRef.current.mute();
      } else {
        playerRef.current.unMute();
        playerRef.current.setVolume(20);
      }
    } catch {
      // player may not be ready
    }
  }, [isMuted, playerRef]);

  return (
    <div className="relative w-full" style={{ paddingBottom: "56.25%" }}>
      <div
        ref={containerRef}
        className="absolute inset-0 w-full h-full"
        id="yt-player-container"
      />
    </div>
  );
}
