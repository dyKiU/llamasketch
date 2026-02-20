import { describe, it, expect } from "vitest";
import {
  createQueue,
  addSubmission,
  shouldDisplay,
  removeEntry,
  findEntry,
  activeCount,
  MAX_QUEUE,
} from "../src/queue-manager";

describe("QueueManager", () => {
  it("creates empty state", () => {
    const q = createQueue();
    expect(q.submissions).toEqual([]);
    expect(q.sequenceNumber).toBe(0);
  });

  it("adds submissions with incrementing seqNum", () => {
    const q = createQueue();
    const { entry: e1 } = addSubmission(q, "job-a");
    const { entry: e2 } = addSubmission(q, "job-b");
    const { entry: e3 } = addSubmission(q, "job-c");

    expect(e1.seqNum).toBe(1);
    expect(e2.seqNum).toBe(2);
    expect(e3.seqNum).toBe(3);
    expect(q.submissions).toHaveLength(3);
  });

  it("does NOT evict when under capacity", () => {
    const q = createQueue();
    const { evicted: ev1 } = addSubmission(q, "job-a");
    const { evicted: ev2 } = addSubmission(q, "job-b");

    expect(ev1).toBeNull();
    expect(ev2).toBeNull();
    expect(q.submissions).toHaveLength(2);
  });

  it("evicts oldest when at capacity (3)", () => {
    const q = createQueue();
    addSubmission(q, "job-a");
    addSubmission(q, "job-b");
    addSubmission(q, "job-c");
    expect(q.submissions).toHaveLength(MAX_QUEUE);

    const { evicted } = addSubmission(q, "job-d");
    expect(evicted).not.toBeNull();
    expect(evicted!.jobId).toBe("job-a");
    expect(q.submissions).toHaveLength(MAX_QUEUE);
    expect(q.submissions.map((e) => e.jobId)).toEqual([
      "job-b",
      "job-c",
      "job-d",
    ]);
  });

  it("shouldDisplay returns true for newest completed", () => {
    const q = createQueue();
    addSubmission(q, "job-a");
    addSubmission(q, "job-b");

    const entryA = findEntry(q, "job-a")!;
    const entryB = findEntry(q, "job-b")!;

    entryA.status = "completed";
    entryB.status = "completed";

    // Only newest completed should display
    expect(shouldDisplay(q, entryA)).toBe(false);
    expect(shouldDisplay(q, entryB)).toBe(true);
  });

  it("shouldDisplay returns true for older completed if newer is still polling", () => {
    const q = createQueue();
    addSubmission(q, "job-a");
    addSubmission(q, "job-b");

    const entryA = findEntry(q, "job-a")!;
    const entryB = findEntry(q, "job-b")!;

    entryA.status = "completed";
    entryB.status = "polling";

    expect(shouldDisplay(q, entryA)).toBe(true);
    expect(shouldDisplay(q, entryB)).toBe(false);
  });

  it("removeEntry works correctly", () => {
    const q = createQueue();
    addSubmission(q, "job-a");
    addSubmission(q, "job-b");
    addSubmission(q, "job-c");

    removeEntry(q, "job-b");
    expect(q.submissions).toHaveLength(2);
    expect(q.submissions.map((e) => e.jobId)).toEqual(["job-a", "job-c"]);
  });

  it("activeCount counts pending and polling entries", () => {
    const q = createQueue();
    addSubmission(q, "job-a");
    addSubmission(q, "job-b");
    addSubmission(q, "job-c");

    expect(activeCount(q)).toBe(3);

    findEntry(q, "job-a")!.status = "completed";
    expect(activeCount(q)).toBe(2);

    findEntry(q, "job-b")!.status = "failed";
    expect(activeCount(q)).toBe(1);
  });
});
