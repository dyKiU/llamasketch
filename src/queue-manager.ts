/**
 * Pure queue logic for the Live Sketch submission queue.
 * Max 3 concurrent submissions — oldest evicted when full.
 * No DOM or fetch dependencies; extracted for unit testing.
 */

export interface QueueEntry {
  jobId: string;
  seqNum: number;
  status: "pending" | "polling" | "completed" | "failed" | "cancelled";
  pollTimer: number | null;
}

export interface QueueState {
  submissions: QueueEntry[];
  sequenceNumber: number;
}

export const MAX_QUEUE = 3;

export function createQueue(): QueueState {
  return { submissions: [], sequenceNumber: 0 };
}

/** Add a new submission, returning any evicted entry (or null). */
export function addSubmission(
  queue: QueueState,
  jobId: string,
): { entry: QueueEntry; evicted: QueueEntry | null } {
  queue.sequenceNumber++;
  const entry: QueueEntry = {
    jobId,
    seqNum: queue.sequenceNumber,
    status: "polling",
    pollTimer: null,
  };

  let evicted: QueueEntry | null = null;
  if (queue.submissions.length >= MAX_QUEUE) {
    // Evict oldest (lowest seqNum)
    queue.submissions.sort((a, b) => a.seqNum - b.seqNum);
    evicted = queue.submissions.shift()!;
  }

  queue.submissions.push(entry);
  return { entry, evicted };
}

/** Whether a completed entry should be displayed (newest completed wins). */
export function shouldDisplay(queue: QueueState, entry: QueueEntry): boolean {
  if (entry.status !== "completed") return false;
  // True only if no other entry with higher seqNum has also completed
  return !queue.submissions.some(
    (e) => e.seqNum > entry.seqNum && e.status === "completed",
  );
}

/** Remove an entry by jobId. */
export function removeEntry(queue: QueueState, jobId: string): void {
  queue.submissions = queue.submissions.filter((e) => e.jobId !== jobId);
}

/** Find an entry by jobId. */
export function findEntry(
  queue: QueueState,
  jobId: string,
): QueueEntry | undefined {
  return queue.submissions.find((e) => e.jobId === jobId);
}

/** Count of active (non-terminal) entries. */
export function activeCount(queue: QueueState): number {
  return queue.submissions.filter(
    (e) => e.status === "pending" || e.status === "polling",
  ).length;
}
