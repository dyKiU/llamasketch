import { describe, it, expect } from "vitest";
import { analyzeSketch, generateTips, SketchStats } from "../src/sketch-analysis";

// Helper: create RGBA pixel data (all white = empty canvas)
function whiteCanvas(w: number, h: number): Uint8ClampedArray {
  const data = new Uint8ClampedArray(w * h * 4);
  data.fill(255);
  return data;
}

// Helper: set a single pixel to black
function setPixel(
  data: Uint8ClampedArray,
  x: number,
  y: number,
  w: number,
  r = 0,
  g = 0,
  b = 0,
  a = 255,
) {
  const i = (y * w + x) * 4;
  data[i] = r;
  data[i + 1] = g;
  data[i + 2] = b;
  data[i + 3] = a;
}

// Helper: fill a rectangular region with black
function fillRect(
  data: Uint8ClampedArray,
  x: number,
  y: number,
  rw: number,
  rh: number,
  w: number,
) {
  for (let dy = 0; dy < rh; dy++) {
    for (let dx = 0; dx < rw; dx++) {
      setPixel(data, x + dx, y + dy, w);
    }
  }
}

describe("sketch-analysis", () => {
  describe("analyzeSketch", () => {
    it("returns zero stats for an all-white canvas", () => {
      const data = whiteCanvas(64, 64);
      const stats = analyzeSketch(data, 64, 64);
      expect(stats.strokePixels).toBe(0);
      expect(stats.coverage).toBe(0);
      expect(stats.boundingBox).toBeNull();
      expect(stats.centerOfMass).toBeNull();
    });

    it("detects a single black pixel", () => {
      const data = whiteCanvas(64, 64);
      setPixel(data, 10, 20, 64);
      const stats = analyzeSketch(data, 64, 64);
      expect(stats.strokePixels).toBe(1);
      expect(stats.boundingBox).toEqual({ x: 10, y: 20, w: 1, h: 1 });
      expect(stats.centerOfMass).toEqual({ x: 10, y: 20 });
    });

    it("computes bounding box for a filled rectangle", () => {
      const data = whiteCanvas(100, 100);
      fillRect(data, 20, 30, 40, 20, 100); // 40x20 rect at (20,30)
      const stats = analyzeSketch(data, 100, 100);
      expect(stats.boundingBox).toEqual({ x: 20, y: 30, w: 40, h: 20 });
      expect(stats.strokePixels).toBe(800); // 40 * 20
    });

    it("computes center of mass correctly", () => {
      const data = whiteCanvas(100, 100);
      // Two pixels: (10,10) and (30,10) → center at (20,10)
      setPixel(data, 10, 10, 100);
      setPixel(data, 30, 10, 100);
      const stats = analyzeSketch(data, 100, 100);
      expect(stats.centerOfMass).toEqual({ x: 20, y: 10 });
    });

    it("treats near-white pixels (>= WHITE_THRESHOLD) as background", () => {
      const data = whiteCanvas(64, 64);
      // Set a pixel to 251,251,251 — should be treated as white (>= 250)
      setPixel(data, 5, 5, 64, 251, 251, 251);
      const stats = analyzeSketch(data, 64, 64);
      expect(stats.strokePixels).toBe(0);
    });

    it("treats pixels just below threshold as strokes", () => {
      const data = whiteCanvas(64, 64);
      // Set a pixel to 249,249,249 — should be a stroke (< 250)
      setPixel(data, 5, 5, 64, 249, 249, 249);
      const stats = analyzeSketch(data, 64, 64);
      expect(stats.strokePixels).toBe(1);
    });

    it("ignores transparent pixels", () => {
      const data = whiteCanvas(64, 64);
      // Black pixel but fully transparent — not a visible stroke
      setPixel(data, 5, 5, 64, 0, 0, 0, 0);
      const stats = analyzeSketch(data, 64, 64);
      expect(stats.strokePixels).toBe(0);
    });

    it("computes coverage as fraction of total pixels", () => {
      const data = whiteCanvas(10, 10);
      // Fill 25 out of 100 pixels
      fillRect(data, 0, 0, 5, 5, 10);
      const stats = analyzeSketch(data, 10, 10);
      expect(stats.coverage).toBeCloseTo(0.25);
    });

    it("computes density as fraction of bounding box filled", () => {
      const data = whiteCanvas(100, 100);
      // 10x10 rect at (0,0) → bbox is 10x10=100, all filled → density 1.0
      fillRect(data, 0, 0, 10, 10, 100);
      const stats = analyzeSketch(data, 100, 100);
      expect(stats.density).toBeCloseTo(1.0);
    });
  });

  describe("generateTips", () => {
    it("returns empty tips for an empty canvas", () => {
      const stats: SketchStats = {
        strokePixels: 0,
        coverage: 0,
        density: 0,
        boundingBox: null,
        centerOfMass: null,
      };
      const tips = generateTips(stats, 512, 512);
      expect(tips).toEqual([]);
    });

    it("tips off-center sketch", () => {
      // Sketch in top-left corner, far from center
      const stats: SketchStats = {
        strokePixels: 100,
        coverage: 0.1,
        density: 0.5,
        boundingBox: { x: 0, y: 0, w: 50, h: 50 },
        centerOfMass: { x: 25, y: 25 }, // far from (256, 256)
      };
      const tips = generateTips(stats, 512, 512);
      const ids = tips.map((t) => t.id);
      expect(ids).toContain("off-center");
    });

    it("tips low coverage", () => {
      const stats: SketchStats = {
        strokePixels: 100,
        coverage: 0.02, // 2% — below 5% threshold
        density: 0.5,
        boundingBox: { x: 230, y: 230, w: 50, h: 50 },
        centerOfMass: { x: 256, y: 256 },
      };
      const tips = generateTips(stats, 512, 512);
      const ids = tips.map((t) => t.id);
      expect(ids).toContain("low-coverage");
    });

    it("tips sparse density", () => {
      const stats: SketchStats = {
        strokePixels: 10,
        coverage: 0.1,
        density: 0.03, // 3% fill within bounding box — below 5%
        boundingBox: { x: 200, y: 200, w: 100, h: 100 },
        centerOfMass: { x: 256, y: 256 },
      };
      const tips = generateTips(stats, 512, 512);
      const ids = tips.map((t) => t.id);
      expect(ids).toContain("sparse");
    });

    it("returns no tips for well-centered, good-coverage sketch", () => {
      const stats: SketchStats = {
        strokePixels: 5000,
        coverage: 0.15, // 15% — good
        density: 0.6, // 60% — good
        boundingBox: { x: 150, y: 150, w: 200, h: 200 },
        centerOfMass: { x: 250, y: 250 }, // close to center
      };
      const tips = generateTips(stats, 512, 512);
      expect(tips).toHaveLength(0);
    });

    it("orders tips by priority (lower = more important)", () => {
      // Trigger all three tips
      const stats: SketchStats = {
        strokePixels: 10,
        coverage: 0.01,
        density: 0.02,
        boundingBox: { x: 0, y: 0, w: 30, h: 30 },
        centerOfMass: { x: 15, y: 15 },
      };
      const tips = generateTips(stats, 512, 512);
      expect(tips.length).toBeGreaterThanOrEqual(2);
      for (let i = 1; i < tips.length; i++) {
        expect(tips[i].priority).toBeGreaterThanOrEqual(tips[i - 1].priority);
      }
    });
  });
});
