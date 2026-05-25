"use client";

import { useEffect, useRef } from "react";
import type { PlayerChunk } from "@/lib/types";
import type { YTPlayer } from "@/lib/youtube-types";

interface JapaneseAudioProps {
  videoId: string;
  currentChunk: PlayerChunk | null;
  isPlaying: boolean;
  isEnabled: boolean;
  audioOffset: number;
  playerRef: React.RefObject<YTPlayer | null>;
}

/**
 * Manages HTMLAudioElement playback for the current chunk's Japanese TTS audio.
 * Sync rules:
 * - YouTube pause -> JP audio pause
 * - YouTube play  -> JP audio play (from chunk start + audio_offset)
 * - Chunk change  -> load new audio, play if currently playing
 * - 404 audio     -> silently skip
 */
export function JapaneseAudio({
  videoId,
  currentChunk,
  isPlaying,
  isEnabled,
  audioOffset,
  playerRef,
}: JapaneseAudioProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const currentChunkIdRef = useRef<number | null>(null);

  // Ensure audio element exists
  useEffect(() => {
    if (!audioRef.current) {
      audioRef.current = new Audio();
      audioRef.current.preload = "auto";
    }
    return () => {
      audioRef.current?.pause();
    };
  }, []);

  // Handle chunk changes
  useEffect(() => {
    if (!currentChunk || !audioRef.current) return;
    if (currentChunk.chunk_id === currentChunkIdRef.current) return;

    currentChunkIdRef.current = currentChunk.chunk_id;
    const audio = audioRef.current;

    // No TTS audio for this chunk — clear the element and stop playback
    if (!currentChunk.audio) {
      audio.pause();
      audio.src = "";
      return;
    }

    const audioUrl = `/api/videos/${videoId}/audio/${encodeURIComponent(
      currentChunk.audio.replace(/^audio\//, "")
    )}`;

    audio.pause();
    audio.src = audioUrl;
    audio.currentTime = 0;
    audio.load();

    audio.onerror = () => {
      // 404 or missing file — silently continue
      audio.src = "";
    };

    if (isPlaying && isEnabled) {
      // Compute the offset into the chunk from the YouTube player time
      let offsetWithinChunk = 0;
      try {
        const ytTime = playerRef.current?.getCurrentTime?.() ?? currentChunk.start;
        offsetWithinChunk = Math.max(0, ytTime - currentChunk.start + audioOffset);
      } catch {
        offsetWithinChunk = Math.max(0, audioOffset);
      }

      audio.addEventListener(
        "canplay",
        () => {
          audio.currentTime = offsetWithinChunk;
          audio.play().catch(() => {
            // Autoplay blocked — user interaction required
          });
        },
        { once: true }
      );
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentChunk?.chunk_id, videoId]);

  // Handle play/pause
  useEffect(() => {
    if (!audioRef.current || !isEnabled) {
      audioRef.current?.pause();
      return;
    }

    const audio = audioRef.current;

    if (isPlaying) {
      if (audio.src && audio.src !== window.location.href) {
        audio.play().catch(() => {
          // autoplay blocked
        });
      }
    } else {
      audio.pause();
    }
  }, [isPlaying, isEnabled]);

  // Apply audio offset changes
  useEffect(() => {
    if (!audioRef.current || !currentChunk) return;
    // audioOffset changes are applied next time audio is loaded
    // (re-loading on every offset change is too disruptive)
  }, [audioOffset, currentChunk]);

  // Mute/unmute
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.muted = !isEnabled;
    }
  }, [isEnabled]);

  // This component renders nothing — it's purely an audio controller
  return null;
}
