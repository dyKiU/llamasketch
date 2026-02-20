/**
 * Pure tool-state logic for the Live Sketch canvas.
 * No DOM dependencies; extracted for unit testing.
 */

export type ToolType = "pencil" | "eraser";

export interface ToolState {
  tool: ToolType;
  strokeWidth: number;
}

export const MIN_WIDTH = 1;
export const MAX_WIDTH = 30;
export const DEFAULT_WIDTH = 3;

export function createToolState(): ToolState {
  return { tool: "pencil", strokeWidth: DEFAULT_WIDTH };
}

export function setTool(state: ToolState, tool: ToolType): ToolState {
  return { ...state, tool };
}

export function setStrokeWidth(state: ToolState, width: number): ToolState {
  const clamped = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, width));
  return { ...state, strokeWidth: clamped };
}

/** Returns the canvas stroke color for the current tool. */
export function strokeColor(state: ToolState): string {
  return state.tool === "eraser" ? "#ffffff" : "#000000";
}

/**
 * Convert CSS (display) coordinates to logical canvas coordinates.
 * cssWidth/cssHeight = the CSS-rendered size of the canvas element.
 * canvasWidth/canvasHeight = the actual canvas resolution (e.g. 512x512).
 */
export function toCanvasCoords(
  cssX: number,
  cssY: number,
  cssWidth: number,
  cssHeight: number,
  canvasWidth: number,
  canvasHeight: number,
): { x: number; y: number } {
  return {
    x: (cssX / cssWidth) * canvasWidth,
    y: (cssY / cssHeight) * canvasHeight,
  };
}
