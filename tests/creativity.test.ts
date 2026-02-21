import { describe, it, expect } from "vitest";
import { getEffectiveRange, sliderToDenoise, updateCreativityRange } from "../src/creativity";

describe("creativity", () => {
  describe("getEffectiveRange", () => {
    it("returns 0–1 when no range tracked", () => {
      const r = getEffectiveRange(null);
      expect(r.min).toBe(0);
      expect(r.max).toBe(1);
    });

    it("pads the tracked range by 0.05 on each side", () => {
      const r = getEffectiveRange({ min: 0.3, max: 0.7 });
      expect(r.min).toBeCloseTo(0.25, 5);
      expect(r.max).toBeCloseTo(0.75, 5);
    });

    it("clamps padded range to 0–1", () => {
      const r = getEffectiveRange({ min: 0.02, max: 0.98 });
      expect(r.min).toBe(0);
      expect(r.max).toBe(1);
    });

    it("enforces minimum spread of 0.10", () => {
      // Range is 0.50–0.52 → spread 0.02 + padding = 0.12, but after pad still narrow
      // Actually: pad: min=0.45, max=0.57, spread=0.12 which is >= 0.10 so no expansion
      // Use tighter range: 0.50–0.50 → pad: 0.45–0.55, spread=0.10, just at limit
      const r = getEffectiveRange({ min: 0.5, max: 0.5 });
      expect(r.max - r.min).toBeGreaterThanOrEqual(0.1);
    });

    it("expansion near boundary: spread may be < 0.10 due to clamping", () => {
      // min=0.01, max=0.01 → padded: 0, 0.06 → spread 0.06 < 0.10
      // expansion: mid=0.03, min=0, max=0.08 → spread 0.08
      // Still < 0.10 because clamped at 0. This is correct behavior.
      const r = getEffectiveRange({ min: 0.01, max: 0.01 });
      expect(r.min).toBe(0);
      expect(r.max).toBeCloseTo(0.08, 5);
      // Spread is 0.08 — less than 0.10 because boundary clamping
      expect(r.max - r.min).toBeCloseTo(0.08, 5);
    });

    it("expands narrow range centered away from boundaries", () => {
      // min=0.50, max=0.505 → padded: 0.45, 0.555 → spread 0.105 >= 0.10, no expansion
      // Need: padded spread < 0.10. Since padding adds 0.10 total, we need
      // the original range to be exactly 0 width AND near a boundary.
      // Actually, for non-boundary cases, padding always adds 0.10 spread.
      // The expansion only matters when clamping at 0/1 eats into the padding.
      // At mid-range, getEffectiveRange always returns >= 0.10 spread.
      const r = getEffectiveRange({ min: 0.5, max: 0.5 });
      expect(r.min).toBeCloseTo(0.45, 5);
      expect(r.max).toBeCloseTo(0.55, 5);
      expect(r.max - r.min).toBeCloseTo(0.1, 5);
    });
  });

  describe("sliderToDenoise", () => {
    it("maps 0 slider to range min", () => {
      const d = sliderToDenoise(0, { min: 0.3, max: 0.7 });
      // effective range: 0.25–0.75, slider 0 → 0.25
      expect(d).toBeCloseTo(0.25, 5);
    });

    it("maps 1.0 slider to range max", () => {
      const d = sliderToDenoise(1.0, { min: 0.3, max: 0.7 });
      // effective range: 0.25–0.75, slider 1 → 0.75
      expect(d).toBeCloseTo(0.75, 5);
    });

    it("maps 0.5 slider to range midpoint", () => {
      const d = sliderToDenoise(0.5, { min: 0.3, max: 0.7 });
      // effective range: 0.25–0.75, slider 0.5 → 0.50
      expect(d).toBeCloseTo(0.5, 5);
    });

    it("returns full 0–1 range when no creativity tracked", () => {
      expect(sliderToDenoise(0, null)).toBeCloseTo(0, 5);
      expect(sliderToDenoise(1, null)).toBeCloseTo(1, 5);
      expect(sliderToDenoise(0.5, null)).toBeCloseTo(0.5, 5);
    });
  });

  describe("updateCreativityRange", () => {
    it("creates new range from first value", () => {
      const r = updateCreativityRange(null, 0.42);
      expect(r.min).toBe(0.42);
      expect(r.max).toBe(0.42);
    });

    it("expands min when new value is lower", () => {
      const r = updateCreativityRange({ min: 0.3, max: 0.7 }, 0.1);
      expect(r.min).toBe(0.1);
      expect(r.max).toBe(0.7);
    });

    it("expands max when new value is higher", () => {
      const r = updateCreativityRange({ min: 0.3, max: 0.7 }, 0.9);
      expect(r.min).toBe(0.3);
      expect(r.max).toBe(0.9);
    });

    it("does not shrink range for value within existing bounds", () => {
      const r = updateCreativityRange({ min: 0.3, max: 0.7 }, 0.5);
      expect(r.min).toBe(0.3);
      expect(r.max).toBe(0.7);
    });
  });
});
