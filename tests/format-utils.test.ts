import { describe, it, expect } from "vitest";
import { formatSize, randomPrompt, getProgressPercent } from "../src/format-utils";

describe("format-utils", () => {
  describe("formatSize", () => {
    it("formats bytes as KB", () => {
      expect(formatSize(1024)).toBe("1.0 KB");
      expect(formatSize(2048)).toBe("2.0 KB");
      expect(formatSize(1536)).toBe("1.5 KB");
    });

    it("formats bytes as MB when >= 1MB", () => {
      expect(formatSize(1024 * 1024)).toBe("1.0 MB");
      expect(formatSize(1024 * 1024 * 2.5)).toBe("2.5 MB");
    });

    it("formats fractional KB", () => {
      expect(formatSize(512)).toBe("0.5 KB");
    });

    it("formats large MB values", () => {
      expect(formatSize(1024 * 1024 * 15.3)).toBe("15.3 MB");
    });
  });

  describe("randomPrompt", () => {
    it("returns empty string for empty word list", () => {
      expect(randomPrompt([])).toBe("");
    });

    it("returns count words joined by spaces", () => {
      const words = ["alpha", "beta", "gamma", "delta", "epsilon"];
      let callIdx = 0;
      // Deterministic random: always picks index 0, 1, 2
      const mockRand = () => {
        const vals = [0.0, 0.2, 0.4]; // floor(0*5)=0, floor(0.2*5)=1, floor(0.4*5)=2
        return vals[callIdx++ % vals.length];
      };
      expect(randomPrompt(words, 3, mockRand)).toBe("alpha beta gamma");
    });

    it("defaults to 3 words", () => {
      const words = ["one"];
      const result = randomPrompt(words, undefined, () => 0);
      expect(result.split(" ")).toHaveLength(3);
    });

    it("handles count of 1", () => {
      const words = ["solo"];
      expect(randomPrompt(words, 1, () => 0)).toBe("solo");
    });
  });

  describe("STATUS_PROGRESS", () => {
    it("has correct mappings for all pipeline stages", () => {
      expect(getProgressPercent("queued")).toBe(10);
      expect(getProgressPercent("uploading")).toBe(25);
      expect(getProgressPercent("submitted")).toBe(40);
      expect(getProgressPercent("processing")).toBe(60);
      expect(getProgressPercent("downloading")).toBe(85);
      expect(getProgressPercent("completed")).toBe(100);
    });

    it("returns undefined for unknown status", () => {
      expect(getProgressPercent("invalid")).toBeUndefined();
    });
  });
});
