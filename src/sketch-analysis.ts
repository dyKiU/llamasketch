// sketch-analysis.ts — Pure canvas analysis: bounding box, center of mass, coverage, tips
// No DOM dependencies. Operates on raw RGBA pixel data.

export const WHITE_THRESHOLD = 250;
const ALPHA_THRESHOLD = 128;

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface SketchStats {
  strokePixels: number;
  coverage: number;  // fraction of total canvas pixels that are strokes
  density: number;   // fraction of bounding box pixels that are strokes
  boundingBox: BoundingBox | null;
  centerOfMass: Point | null;
}

export interface SketchTip {
  id: string;
  message: string;
  priority: number;  // lower = more important
}

/** Returns true if the pixel at offset i is a visible stroke (not white, not transparent). */
function isStroke(data: Uint8ClampedArray, i: number): boolean {
  const a = data[i + 3];
  if (a < ALPHA_THRESHOLD) return false;
  const r = data[i];
  const g = data[i + 1];
  const b = data[i + 2];
  return r < WHITE_THRESHOLD || g < WHITE_THRESHOLD || b < WHITE_THRESHOLD;
}

/** Analyze raw RGBA pixel data and compute sketch statistics. */
export function analyzeSketch(
  data: Uint8ClampedArray,
  width: number,
  height: number
): SketchStats {
  let strokePixels = 0;
  let sumX = 0;
  let sumY = 0;
  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      if (isStroke(data, i)) {
        strokePixels++;
        sumX += x;
        sumY += y;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }

  const totalPixels = width * height;
  const coverage = totalPixels > 0 ? strokePixels / totalPixels : 0;

  if (strokePixels === 0) {
    return { strokePixels: 0, coverage: 0, density: 0, boundingBox: null, centerOfMass: null };
  }

  const boundingBox: BoundingBox = {
    x: minX,
    y: minY,
    w: maxX - minX + 1,
    h: maxY - minY + 1,
  };

  const bboxArea = boundingBox.w * boundingBox.h;
  const density = bboxArea > 0 ? strokePixels / bboxArea : 0;

  const centerOfMass: Point = {
    x: Math.round(sumX / strokePixels),
    y: Math.round(sumY / strokePixels),
  };

  return { strokePixels, coverage, density, boundingBox, centerOfMass };
}

/** Generate actionable tips based on sketch statistics. */
export function generateTips(
  stats: SketchStats,
  canvasWidth: number,
  canvasHeight: number
): SketchTip[] {
  if (stats.strokePixels === 0 || !stats.centerOfMass || !stats.boundingBox) {
    return [];
  }

  const tips: SketchTip[] = [];
  const cx = canvasWidth / 2;
  const cy = canvasHeight / 2;
  const diagonal = Math.sqrt(canvasWidth * canvasWidth + canvasHeight * canvasHeight);
  const dx = stats.centerOfMass.x - cx;
  const dy = stats.centerOfMass.y - cy;
  const dist = Math.sqrt(dx * dx + dy * dy);

  // Off-center: center of mass > 25% of canvas diagonal from center
  if (dist > diagonal * 0.25) {
    tips.push({
      id: "off-center",
      message: "Try centering your sketch for better results",
      priority: 1,
    });
  }

  // Low coverage: less than 5% of canvas has strokes
  if (stats.coverage < 0.05) {
    tips.push({
      id: "low-coverage",
      message: "Draw larger — small sketches may lose detail",
      priority: 2,
    });
  }

  // Sparse density: less than 5% of bounding box is filled
  if (stats.density < 0.05) {
    tips.push({
      id: "sparse",
      message: "Add more detail within your sketch area",
      priority: 3,
    });
  }

  tips.sort((a, b) => a.priority - b.priority);
  return tips;
}
