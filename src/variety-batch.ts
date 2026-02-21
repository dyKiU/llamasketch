/**
 * Pure variety-batch scheduling logic.
 * No DOM or fetch dependencies — submit/cancel are injected callbacks.
 * Extracted for unit testing.
 */

export type JobStatus = "pending" | "submitted" | "completed" | "failed";

export interface VJob {
  id: number;
  externalId: string | null; // set after submitFn resolves
  status: JobStatus;
}

export interface BatchState {
  generation: number;
  jobs: VJob[];
  totalFired: number; // cumulative across extensions
  onProgress: ((completed: number, total: number) => void) | null;
  onAllDone: (() => void) | null;
}

export function createBatch(generation: number): BatchState {
  return {
    generation,
    jobs: [],
    totalFired: 0,
    onProgress: null,
    onAllDone: null,
  };
}

/**
 * Fire `count` jobs using `submitFn`. Each call to submitFn should return
 * a promise resolving to an externalId string (e.g. job_id from the API).
 * Jobs whose generation doesn't match are silently dropped.
 */
export function fireJobs(
  batch: BatchState,
  count: number,
  submitFn: () => Promise<string>,
): VJob[] {
  const newJobs: VJob[] = [];

  for (let i = 0; i < count; i++) {
    const job: VJob = {
      id: batch.totalFired + i,
      externalId: null,
      status: "pending",
    };
    batch.jobs.push(job);
    newJobs.push(job);

    const gen = batch.generation;
    submitFn()
      .then((externalId) => {
        if (batch.generation !== gen) return;
        job.externalId = externalId;
        job.status = "submitted";
        _emitProgress(batch);
      })
      .catch(() => {
        if (batch.generation !== gen) return;
        job.status = "failed";
        _emitProgress(batch);
      });
  }

  batch.totalFired += count;
  return newJobs;
}

/**
 * Mark a job as completed by its externalId.
 * Returns true if found and updated, false otherwise.
 */
export function completeJob(batch: BatchState, externalId: string): boolean {
  const job = batch.jobs.find(
    (j) => j.externalId === externalId && j.status === "submitted",
  );
  if (!job) return false;
  job.status = "completed";
  _emitProgress(batch);
  return true;
}

/**
 * Mark a job as failed by its externalId.
 */
export function failJob(batch: BatchState, externalId: string): boolean {
  const job = batch.jobs.find(
    (j) => j.externalId === externalId && j.status === "submitted",
  );
  if (!job) return false;
  job.status = "failed";
  _emitProgress(batch);
  return true;
}

/**
 * Abort: bumps generation (so in-flight submits are ignored),
 * calls cancelFn for each submitted job, and clears the job list.
 */
export function abortBatch(
  batch: BatchState,
  cancelFn?: (externalId: string) => void,
): void {
  batch.generation++;
  for (const job of batch.jobs) {
    if (
      cancelFn &&
      job.externalId &&
      (job.status === "pending" || job.status === "submitted")
    ) {
      cancelFn(job.externalId);
    }
  }
  batch.jobs = [];
  batch.totalFired = 0;
}

/** Count of completed jobs. */
export function completedCount(batch: BatchState): number {
  return batch.jobs.filter((j) => j.status === "completed").length;
}

/** Count of settled (completed + failed) jobs. */
export function settledCount(batch: BatchState): number {
  return batch.jobs.filter(
    (j) => j.status === "completed" || j.status === "failed",
  ).length;
}

/** Whether all fired jobs have settled. */
export function allDone(batch: BatchState): boolean {
  return batch.jobs.length > 0 && settledCount(batch) === batch.jobs.length;
}

function _emitProgress(batch: BatchState): void {
  const done = completedCount(batch);
  const total = batch.jobs.length;
  if (batch.onProgress) batch.onProgress(done, total);
  if (allDone(batch) && batch.onAllDone) batch.onAllDone();
}
