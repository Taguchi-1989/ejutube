import path from "path";
import fs from "fs";

/**
 * Returns the absolute path to the output directory.
 * Defaults to ../output relative to web/ (i.e., the project root output/).
 */
export function getOutputDir(): string {
  const envDir = process.env.OUTPUT_DIR;
  if (envDir) {
    return path.isAbsolute(envDir) ? envDir : path.resolve(process.cwd(), envDir);
  }
  // process.cwd() is the web/ dir when running next dev/build
  return path.resolve(process.cwd(), "../output");
}

const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;

export function validateVideoId(videoId: string): void {
  if (!VIDEO_ID_RE.test(videoId)) {
    throw new Error(`Invalid videoId: ${videoId}`);
  }
}

export function getVideoOutputDir(videoId: string): string {
  validateVideoId(videoId);
  return path.join(getOutputDir(), videoId);
}

export function getPlayerJsonPath(videoId: string): string {
  return path.join(getVideoOutputDir(videoId), "player.json");
}

export function getMetadataPath(videoId: string): string {
  return path.join(getVideoOutputDir(videoId), "metadata.json");
}

export function getAudioFilePath(videoId: string, file: string): string {
  // Sanitize: only allow filenames like 0001.wav (no path traversal)
  const safeName = path.basename(file);
  return path.join(getVideoOutputDir(videoId), "audio", safeName);
}

/** List all video IDs that have a metadata.json */
export function listVideoIds(): string[] {
  const dir = getOutputDir();
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((entry) => {
      const meta = path.join(dir, entry, "metadata.json");
      return fs.existsSync(meta);
    });
}
