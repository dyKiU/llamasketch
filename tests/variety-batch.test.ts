import { describe, it, expect, vi } from "vitest";
import {
  createBatch,
  fireJobs,
  completeJob,
  failJob,
  abortBatch,
  completedCount,
  settledCount,
  allDone,
} from "../src/variety-batch";

describe("variety-batch", () => {
  it("creates empty batch with given generation", () => {
    const b = createBatch(1);
    expect(b.generation).toBe(1);
    expect(b.jobs).toEqual([]);
    expect(b.totalFired).toBe(0);
  });

  it("fireJobs creates N pending jobs and calls submitFn N times", async () => {
    const b = createBatch(1);
    let callCount = 0;
    const submitFn = () => {
      callCount++;
      return Promise.resolve(`ext-${callCount}`);
    };

    const jobs = fireJobs(b, 4, submitFn);
    expect(jobs).toHaveLength(4);
    expect(b.jobs).toHaveLength(4);
    expect(b.totalFired).toBe(4);
    expect(callCount).toBe(4);

    // Let promises resolve
    await vi.waitFor(() => {
      expect(b.jobs.filter((j) => j.status === "submitted")).toHaveLength(4);
    });

    expect(b.jobs[0].externalId).toBe("ext-1");
    expect(b.jobs[3].externalId).toBe("ext-4");
  });

  it("fireJobs marks failed on submitFn rejection", async () => {
    const b = createBatch(1);
    const submitFn = () => Promise.reject(new Error("network error"));

    fireJobs(b, 2, submitFn);

    await vi.waitFor(() => {
      expect(b.jobs.filter((j) => j.status === "failed")).toHaveLength(2);
    });
  });

  it("completeJob marks a submitted job as completed", async () => {
    const b = createBatch(1);
    fireJobs(b, 2, () => Promise.resolve("job-A"));

    await vi.waitFor(() => {
      expect(b.jobs[0].status).toBe("submitted");
    });

    expect(completeJob(b, "job-A")).toBe(true);
    expect(b.jobs[0].status).toBe("completed");
    expect(completedCount(b)).toBe(1);
  });

  it("failJob marks a submitted job as failed", async () => {
    const b = createBatch(1);
    let n = 0;
    fireJobs(b, 2, () => Promise.resolve(`j-${++n}`));

    await vi.waitFor(() => {
      expect(settledCount(b)).toBe(0); // all submitted, none settled
      expect(b.jobs.every((j) => j.status === "submitted")).toBe(true);
    });

    expect(failJob(b, "j-1")).toBe(true);
    expect(b.jobs[0].status).toBe("failed");
    expect(settledCount(b)).toBe(1);
  });

  it("allDone returns true when all jobs settled", async () => {
    const b = createBatch(1);
    let n = 0;
    fireJobs(b, 2, () => Promise.resolve(`j-${++n}`));

    await vi.waitFor(() => {
      expect(b.jobs.every((j) => j.status === "submitted")).toBe(true);
    });

    expect(allDone(b)).toBe(false);
    completeJob(b, "j-1");
    expect(allDone(b)).toBe(false);
    failJob(b, "j-2");
    expect(allDone(b)).toBe(true);
  });

  it("onProgress fires on each status change", async () => {
    const b = createBatch(1);
    const calls: [number, number][] = [];
    b.onProgress = (c, t) => calls.push([c, t]);

    let n = 0;
    fireJobs(b, 3, () => Promise.resolve(`j-${++n}`));

    await vi.waitFor(() => {
      expect(b.jobs.every((j) => j.status === "submitted")).toBe(true);
    });

    // 3 calls from submitFn resolving (0 completed each time, total 3)
    expect(calls.length).toBe(3);
    expect(calls[0]).toEqual([0, 3]);

    completeJob(b, "j-1");
    expect(calls[calls.length - 1]).toEqual([1, 3]);

    completeJob(b, "j-2");
    expect(calls[calls.length - 1]).toEqual([2, 3]);
  });

  it("onAllDone fires when last job settles", async () => {
    const b = createBatch(1);
    let doneFired = false;
    b.onAllDone = () => {
      doneFired = true;
    };

    let n = 0;
    fireJobs(b, 2, () => Promise.resolve(`j-${++n}`));

    await vi.waitFor(() => {
      expect(b.jobs.every((j) => j.status === "submitted")).toBe(true);
    });

    completeJob(b, "j-1");
    expect(doneFired).toBe(false);

    completeJob(b, "j-2");
    expect(doneFired).toBe(true);
  });

  it("abortBatch bumps generation and calls cancelFn", async () => {
    const b = createBatch(1);
    let n = 0;
    fireJobs(b, 3, () => Promise.resolve(`j-${++n}`));

    await vi.waitFor(() => {
      expect(b.jobs.every((j) => j.status === "submitted")).toBe(true);
    });

    const cancelled: string[] = [];
    abortBatch(b, (id) => cancelled.push(id));

    expect(b.generation).toBe(2);
    expect(b.jobs).toEqual([]);
    expect(b.totalFired).toBe(0);
    expect(cancelled.sort()).toEqual(["j-1", "j-2", "j-3"]);
  });

  it("stale generation: submits after abort are ignored", async () => {
    const b = createBatch(1);

    // submitFn that resolves asynchronously
    const resolvers: ((v: string) => void)[] = [];
    const submitFn = () => new Promise<string>((res) => resolvers.push(res));

    fireJobs(b, 2, submitFn);
    expect(b.jobs).toHaveLength(2);

    // Abort before submits resolve
    abortBatch(b);
    expect(b.generation).toBe(2);
    expect(b.jobs).toEqual([]);

    // Now resolve the old promises — should be silently ignored
    resolvers.forEach((r, i) => r(`old-${i}`));
    await new Promise((r) => setTimeout(r, 10));

    // Batch remains empty
    expect(b.jobs).toEqual([]);
  });

  it("fireJobs can extend an existing batch", async () => {
    const b = createBatch(1);
    let n = 0;
    fireJobs(b, 3, () => Promise.resolve(`j-${++n}`));
    expect(b.totalFired).toBe(3);

    // Extend with 2 more
    fireJobs(b, 2, () => Promise.resolve(`j-${++n}`));
    expect(b.totalFired).toBe(5);
    expect(b.jobs).toHaveLength(5);

    await vi.waitFor(() => {
      expect(b.jobs.every((j) => j.status === "submitted")).toBe(true);
    });

    expect(b.jobs[3].externalId).toBe("j-4");
    expect(b.jobs[4].externalId).toBe("j-5");
  });
});
