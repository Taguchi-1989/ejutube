/**
 * CONTRACT / REPLICA TEST for web/lib/jobs.ts.
 *
 * This file is intentionally a contract test: it does NOT import the real
 * web/lib/jobs.ts source. Instead, it replicates the module's logic inline
 * using a fake EventEmitter so the tests can run under plain Node without a
 * bundler or tsx/ts-node setup.
 *
 * IMPORTANT: When changing logic in web/lib/jobs.ts, update the replica in
 * makeJobsModule() below to match. The two must stay in sync.
 *
 * Real source: web/lib/jobs.ts
 *
 * Run with:
 *   node --test web/__tests__/jobs-contract.test.mjs
 */

import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";

// ---------------------------------------------------------------------------
// Minimal replica of the jobs.ts module (keeps logic identical to source).
// ---------------------------------------------------------------------------

class FakeChildProcess extends EventEmitter {
  constructor() {
    super();
    this.stderr = new EventEmitter();
    this.killed = false;
  }
  kill() {
    this.killed = true;
  }
}

/**
 * Factory that returns a fresh jobs store and its associated startJob /
 * getJob functions — equivalent to what jobs.ts exports, but with spawn
 * replaced by a factory argument so tests can control the subprocess.
 */
function makeJobsModule(spawnFactory) {
  const jobs = new Map();

  function startJob(videoId, url) {
    // Atomic check-and-insert (M2).
    const existing = jobs.get(videoId);
    if (existing !== undefined && existing.exit_code === null) {
      return { info: existing, created: false };
    }

    const child = spawnFactory(videoId, url);

    const info = {
      process: child,
      started_at: new Date().toISOString(),
      exit_code: null,
      stderr: "",
    };

    // M1: handle spawn errors (e.g. binary not in PATH).
    child.on("error", (err) => {
      info.stderr = String(err);
      info.exit_code = -1;
    });

    child.stderr?.on("data", (chunk) => {
      info.stderr = (info.stderr + chunk.toString()).slice(-2000);
    });

    child.on("exit", (code) => {
      info.exit_code = code;
    });

    jobs.set(videoId, info);
    return { info, created: true };
  }

  function getJob(videoId) {
    return jobs.get(videoId);
  }

  return { startJob, getJob };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("startJob", () => {
  test("registers a job with status pending (exit_code null)", () => {
    const child = new FakeChildProcess();
    const { startJob, getJob } = makeJobsModule(() => child);

    const { created } = startJob("abc1234567a", "https://youtu.be/abc1234567a");

    assert.equal(created, true);
    const job = getJob("abc1234567a");
    assert.ok(job, "job should be registered");
    assert.equal(job.exit_code, null, "exit_code should be null initially");
    assert.ok(job.started_at, "started_at should be set");
  });

  test("duplicate startJob for same videoId returns created: false (M2)", () => {
    const child = new FakeChildProcess();
    let spawnCount = 0;
    const { startJob } = makeJobsModule(() => {
      spawnCount++;
      return child;
    });

    const r1 = startJob("dup1234567a", "https://youtu.be/dup1234567a");
    const r2 = startJob("dup1234567a", "https://youtu.be/dup1234567a");

    assert.equal(r1.created, true, "first call should create");
    assert.equal(r2.created, false, "second call for running job should not create");
    assert.equal(spawnCount, 1, "spawn should only be called once");
    assert.equal(r1.info, r2.info, "both calls return the same JobInfo");
  });

  test("allows re-start after a job exits (exit_code non-null)", () => {
    const child1 = new FakeChildProcess();
    const child2 = new FakeChildProcess();
    const children = [child1, child2];
    let idx = 0;
    const { startJob, getJob } = makeJobsModule(() => children[idx++]);

    startJob("vid1234567a", "https://youtu.be/vid1234567a");
    // Simulate exit
    child1.emit("exit", 0);

    const r2 = startJob("vid1234567a", "https://youtu.be/vid1234567a");
    assert.equal(r2.created, true, "should create new job after previous exited");
    assert.equal(getJob("vid1234567a").exit_code, null, "new job exit_code is null");
  });

  test("spawn error event sets exit_code: -1 and stderr (M1)", () => {
    const child = new FakeChildProcess();
    const { startJob, getJob } = makeJobsModule(() => child);

    startJob("err1234567a", "https://youtu.be/err1234567a");

    // Simulate 'yt-ja' not found in PATH.
    child.emit("error", new Error("spawn yt-ja ENOENT"));

    const job = getJob("err1234567a");
    assert.equal(job.exit_code, -1, "exit_code should be -1 after spawn error");
    assert.ok(
      job.stderr.includes("ENOENT") || job.stderr.includes("yt-ja"),
      `stderr should contain error text, got: ${job.stderr}`
    );
  });
});

describe("getJob", () => {
  test("returns undefined for unknown videoId", () => {
    const { getJob } = makeJobsModule(() => new FakeChildProcess());
    assert.equal(getJob("unknown1234"), undefined);
  });

  test("returns registered job for known videoId", () => {
    const child = new FakeChildProcess();
    const { startJob, getJob } = makeJobsModule(() => child);
    startJob("known123456", "https://youtu.be/known123456");
    const job = getJob("known123456");
    assert.ok(job);
    assert.equal(job.process, child);
  });
});
