import { describe, it, expect } from "vitest";
import {
  createToolState,
  setTool,
  setStrokeWidth,
  strokeColor,
  toCanvasCoords,
  MIN_WIDTH,
  MAX_WIDTH,
  DEFAULT_WIDTH,
} from "../src/canvas-tools";

describe("CanvasTools", () => {
  it("defaults to pencil with width 3", () => {
    const state = createToolState();
    expect(state.tool).toBe("pencil");
    expect(state.strokeWidth).toBe(DEFAULT_WIDTH);
    expect(state.strokeWidth).toBe(3);
  });

  it("switches tools and returns correct stroke colors", () => {
    let state = createToolState();
    expect(strokeColor(state)).toBe("#000000"); // pencil = black

    state = setTool(state, "eraser");
    expect(state.tool).toBe("eraser");
    expect(strokeColor(state)).toBe("#ffffff"); // eraser = white

    state = setTool(state, "pencil");
    expect(state.tool).toBe("pencil");
    expect(strokeColor(state)).toBe("#000000");
  });

  it("clamps stroke width to 1-30 range", () => {
    let state = createToolState();

    state = setStrokeWidth(state, 0);
    expect(state.strokeWidth).toBe(MIN_WIDTH);

    state = setStrokeWidth(state, -5);
    expect(state.strokeWidth).toBe(MIN_WIDTH);

    state = setStrokeWidth(state, 50);
    expect(state.strokeWidth).toBe(MAX_WIDTH);

    state = setStrokeWidth(state, 15);
    expect(state.strokeWidth).toBe(15);
  });

  it("computes canvas coordinates with CSS-to-pixel scaling", () => {
    // Canvas is 512x512, displayed at 256x256 CSS pixels
    const { x, y } = toCanvasCoords(128, 64, 256, 256, 512, 512);
    expect(x).toBe(256); // 128/256 * 512
    expect(y).toBe(128); // 64/256 * 512
  });

  it("handles 1:1 scaling (no scaling needed)", () => {
    const { x, y } = toCanvasCoords(100, 200, 512, 512, 512, 512);
    expect(x).toBe(100);
    expect(y).toBe(200);
  });

  it("handles non-square scaling", () => {
    // Canvas 512x512, displayed at 400x200
    const { x, y } = toCanvasCoords(200, 100, 400, 200, 512, 512);
    expect(x).toBe(256); // 200/400 * 512
    expect(y).toBe(256); // 100/200 * 512
  });
});
