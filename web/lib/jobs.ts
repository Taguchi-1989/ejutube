/**
 * In-memory job registry for pipeline subprocesses.
 *
 * NOTE: This map is lost on server restart. The /api/jobs/[videoId] route
 * falls back to reading output/{videoId}/metadata.json in that case.
 */

import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";

export interface JobInfo {
  process: ChildProcess;
  started_at: string;
  exit_code: number | null;
  /** Tail of stderr output (last 2KB). */
  stderr: string;
}

const jobs = new Map<string, JobInfo>();

// Clean up all children when the server shuts down.
process.on("SIGTERM", () => {
  for (const [, job] of jobs) {
    try {
      job.process.kill();
    } catch {
      // already exited
    }
  }
});

/**
 * Spawn `yt-ja process <url>` for the given video_id and register it.
 * Returns the new JobInfo. Does NOT check for existing jobs — callers must do that.
 */
export function startJob(videoId: string, url: string): JobInfo {
  // Repo root is one level up from web/ (Next.js cwd is web/ at runtime).
  const cwd = path.resolve(process.cwd(), "..");

  const child = spawn("yt-ja", ["process", url], {
    cwd,
    // shell:true is required on Windows so that .cmd wrapper scripts resolve.
    shell: process.platform === "win32",
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    detached: false,
    windowsHide: true,
  });

  const info: JobInfo = {
    process: child,
    started_at: new Date().toISOString(),
    exit_code: null,
    stderr: "",
  };

  child.stderr?.on("data", (chunk: Buffer) => {
    info.stderr = (info.stderr + chunk.toString()).slice(-2000);
  });

  child.on("exit", (code) => {
    info.exit_code = code;
  });

  jobs.set(videoId, info);
  return info;
}

/** Return the registered JobInfo for a video_id, or undefined if not found. */
export function getJob(videoId: string): JobInfo | undefined {
  return jobs.get(videoId);
}

/** True if there is a running (not yet exited) job for this video_id. */
export function isJobRunning(videoId: string): boolean {
  const job = jobs.get(videoId);
  return job !== undefined && job.exit_code === null;
}
