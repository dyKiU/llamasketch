/**
 * Pure image-to-canvas layout calculation.
 * No DOM or canvas context dependencies; extracted for unit testing.
 */

export type FitMode = "fit" | "fill" | "stretch";

export interface LayoutRect {
  /** Source crop rectangle */
  sx: number;
  sy: number;
  sw: number;
  sh: number;
  /** Destination rectangle on canvas */
  dx: number;
  dy: number;
  dw: number;
  dh: number;
}

/**
 * Calculate how an image of (imgW x imgH) maps onto a canvas of (cw x ch)
 * given the fit mode.
 */
export function calculateLayout(
  imgW: number,
  imgH: number,
  cw: number,
  ch: number,
  mode: FitMode,
): LayoutRect {
  if (mode === "stretch") {
    return { sx: 0, sy: 0, sw: imgW, sh: imgH, dx: 0, dy: 0, dw: cw, dh: ch };
  }

  if (mode === "fill") {
    const scale = Math.max(cw / imgW, ch / imgH);
    const sw = cw / scale;
    const sh = ch / scale;
    const sx = (imgW - sw) / 2;
    const sy = (imgH - sh) / 2;
    return { sx, sy, sw, sh, dx: 0, dy: 0, dw: cw, dh: ch };
  }

  // fit: scale to fit inside canvas, letterbox/pillarbox
  const scale = Math.min(cw / imgW, ch / imgH);
  const dw = imgW * scale;
  const dh = imgH * scale;
  const dx = (cw - dw) / 2;
  const dy = (ch - dh) / 2;
  return { sx: 0, sy: 0, sw: imgW, sh: imgH, dx, dy, dw, dh };
}
