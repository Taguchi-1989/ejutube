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
// SIGTERM fires on Unix; "exit" fires on both Unix and Windows.
process.on("SIGTERM", () => {
  for (const [, job] of jobs) {
    try {
      job.process.kill();
    } catch {
      // already exited
    }
  }
});

// L1: also handle process exit (works on Windows where SIGTERM may not fire).
// Gate on production to avoid orphaning in-flight pipelines during Next.js
// HMR restarts in development — each HMR cycle fires "exit", which would kill
// any running child process. In dev, let ChildProcesses survive HMR naturally.
if (process.env.NODE_ENV === "production") {
  process.on("exit", () => {
    for (const [, job] of jobs) {
      try {
        job.process.kill();
      } catch {
        // already exited
      }
    }
  });
}

/**
 * Spawn `yt-ja process <url>` for the given video_id and register it.
 *
 * Returns `{ info, created: true }` when a new job was started, or
 * `{ info, created: false }` when a job for this videoId was already running.
 * The check-and-insert is performed in a single synchronous block, which is
 * safe in Node's single-threaded event loop (M2: eliminates TOCTOU race).
 */
export function startJob(
  videoId: string,
  url: string
): { info: JobInfo; created: boolean } {
  // Atomic check: if a running job already exists, return it immediately.
  const existing = jobs.get(videoId);
  if (existing !== undefined && existing.exit_code === null) {
    return { info: existing, created: false };
  }

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

  // M1: handle spawn errors (e.g. yt-ja not in PATH) so they don't crash Next.js.
  child.on("error", (err) => {
    info.stderr = String(err);
    info.exit_code = -1;
  });

  child.stderr?.on("data", (chunk: Buffer) => {
    info.stderr = (info.stderr + chunk.toString()).slice(-2000);
  });

  child.on("exit", (code, signal) => {
    // A process terminated by a signal reports code === null. Leaving
    // exit_code null would make the job look perpetually "running", so map a
    // signal kill to a non-zero (failed) exit code.
    info.exit_code = code ?? (signal ? -1 : 0);
  });

  jobs.set(videoId, info);
  return { info, created: true };
}

/** Return the registered JobInfo for a video_id, or undefined if not found. */
export function getJob(videoId: string): JobInfo | undefined {
  return jobs.get(videoId);
}
