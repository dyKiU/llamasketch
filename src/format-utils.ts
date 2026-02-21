/**
 * Pure formatting utilities.
 * No DOM dependencies; extracted for unit testing.
 */

/** Format byte count as "1.2 MB" or "456.7 KB". */
export function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / 1024).toFixed(1) + " KB";
}

/**
 * Pick `count` random words from a word list and join with spaces.
 * Uses the provided random function for testability (defaults to Math.random).
 */
export function randomPrompt(
  wordList: string[],
  count: number = 3,
  randFn: () => number = Math.random,
): string {
  if (!wordList.length) return "";
  const words: string[] = [];
  for (let i = 0; i < count; i++) {
    words.push(wordList[Math.floor(randFn() * wordList.length)]);
  }
  return words.join(" ");
}

/** Map a pipeline status string to a progress percentage (0–100). */
export const STATUS_PROGRESS: Record<string, number> = {
  queued: 10,
  uploading: 25,
  submitted: 40,
  processing: 60,
  downloading: 85,
  completed: 100,
};

export function getProgressPercent(status: string): number | undefined {
  return STATUS_PROGRESS[status];
}
