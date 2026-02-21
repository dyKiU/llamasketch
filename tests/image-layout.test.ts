import { describe, it, expect } from "vitest";
import { calculateLayout } from "../src/image-layout";

describe("image-layout", () => {
  const CW = 512;
  const CH = 512;

  describe("stretch mode", () => {
    it("stretches any image to fill the canvas exactly", () => {
      const r = calculateLayout(1920, 1080, CW, CH, "stretch");
      // Source = entire image
      expect(r.sx).toBe(0);
      expect(r.sy).toBe(0);
      expect(r.sw).toBe(1920);
      expect(r.sh).toBe(1080);
      // Dest = entire canvas
      expect(r.dx).toBe(0);
      expect(r.dy).toBe(0);
      expect(r.dw).toBe(CW);
      expect(r.dh).toBe(CH);
    });

    it("works for square images", () => {
      const r = calculateLayout(256, 256, CW, CH, "stretch");
      expect(r.sw).toBe(256);
      expect(r.sh).toBe(256);
      expect(r.dw).toBe(CW);
      expect(r.dh).toBe(CH);
    });
  });

  describe("fill mode", () => {
    it("crops a landscape image to fill the square canvas", () => {
      // 1920x1080 → scale = max(512/1920, 512/1080) = 512/1080 ≈ 0.4741
      // sw = 512/0.4741 ≈ 1080, sh = 512/0.4741 ≈ 1080
      // sx = (1920 - 1080) / 2 = 420, sy = 0
      const r = calculateLayout(1920, 1080, CW, CH, "fill");
      const scale = Math.max(CW / 1920, CH / 1080);
      expect(r.sw).toBeCloseTo(CW / scale, 1);
      expect(r.sh).toBeCloseTo(CH / scale, 1);
      expect(r.sx).toBeCloseTo((1920 - r.sw) / 2, 1);
      expect(r.sy).toBeCloseTo((1080 - r.sh) / 2, 1);
      // Dest = full canvas
      expect(r.dx).toBe(0);
      expect(r.dy).toBe(0);
      expect(r.dw).toBe(CW);
      expect(r.dh).toBe(CH);
    });

    it("crops a portrait image to fill the square canvas", () => {
      // 800x1200 → scale = max(512/800, 512/1200) = 512/800 = 0.64
      // sw = 512/0.64 = 800, sh = 512/0.64 = 800
      // sx = 0, sy = (1200 - 800) / 2 = 200
      const r = calculateLayout(800, 1200, CW, CH, "fill");
      const scale = Math.max(CW / 800, CH / 1200);
      expect(r.sw).toBeCloseTo(CW / scale, 1);
      expect(r.sh).toBeCloseTo(CH / scale, 1);
      expect(r.sx).toBeCloseTo((800 - r.sw) / 2, 1);
      expect(r.sy).toBeCloseTo((1200 - r.sh) / 2, 1);
      expect(r.dw).toBe(CW);
      expect(r.dh).toBe(CH);
    });

    it("does nothing special for a square image", () => {
      const r = calculateLayout(512, 512, CW, CH, "fill");
      expect(r.sx).toBe(0);
      expect(r.sy).toBe(0);
      expect(r.sw).toBe(512);
      expect(r.sh).toBe(512);
      expect(r.dw).toBe(CW);
      expect(r.dh).toBe(CH);
    });
  });

  describe("fit mode", () => {
    it("letterboxes a landscape image (bars on top/bottom)", () => {
      // 1920x1080 → scale = min(512/1920, 512/1080) = 512/1920 ≈ 0.2667
      // dw = 1920 * 0.2667 ≈ 512, dh = 1080 * 0.2667 ≈ 288
      // dx = 0, dy = (512 - 288) / 2 = 112
      const r = calculateLayout(1920, 1080, CW, CH, "fit");
      const scale = Math.min(CW / 1920, CH / 1080);
      expect(r.sx).toBe(0);
      expect(r.sy).toBe(0);
      expect(r.sw).toBe(1920);
      expect(r.sh).toBe(1080);
      expect(r.dw).toBeCloseTo(1920 * scale, 1);
      expect(r.dh).toBeCloseTo(1080 * scale, 1);
      expect(r.dx).toBeCloseTo((CW - r.dw) / 2, 1);
      expect(r.dy).toBeCloseTo((CH - r.dh) / 2, 1);
    });

    it("pillarboxes a portrait image (bars on left/right)", () => {
      // 800x1200 → scale = min(512/800, 512/1200) = 512/1200 ≈ 0.4267
      // dw = 800 * 0.4267 ≈ 341.3, dh = 1200 * 0.4267 ≈ 512
      // dx = (512 - 341.3) / 2 ≈ 85.3, dy = 0
      const r = calculateLayout(800, 1200, CW, CH, "fit");
      const scale = Math.min(CW / 800, CH / 1200);
      expect(r.dw).toBeCloseTo(800 * scale, 1);
      expect(r.dh).toBeCloseTo(1200 * scale, 1);
      expect(r.dx).toBeCloseTo((CW - r.dw) / 2, 1);
      expect(r.dy).toBeCloseTo((CH - r.dh) / 2, 1);
    });

    it("fits a square image exactly", () => {
      const r = calculateLayout(512, 512, CW, CH, "fit");
      expect(r.dx).toBe(0);
      expect(r.dy).toBe(0);
      expect(r.dw).toBe(512);
      expect(r.dh).toBe(512);
    });

    it("uses full source image (no cropping)", () => {
      const r = calculateLayout(1000, 500, CW, CH, "fit");
      expect(r.sx).toBe(0);
      expect(r.sy).toBe(0);
      expect(r.sw).toBe(1000);
      expect(r.sh).toBe(500);
    });
  });
});
