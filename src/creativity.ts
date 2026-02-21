/**
 * Pure creativity/denoise range logic.
 * No DOM dependencies; extracted for unit testing.
 */

export interface CreativityRange {
  min: number;
  max: number;
}

/** Pad the tracked range by 0.05 each side and enforce a minimum spread of 0.10. */
export function getEffectiveRange(
  range: CreativityRange | null,
): CreativityRange {
  if (!range) return { min: 0, max: 1 };
  const pad = 0.05;
  let min = Math.max(0, range.min - pad);
  let max = Math.min(1, range.max + pad);
  if (max - min < 0.10) {
    const mid = (min + max) / 2;
    min = Math.max(0, mid - 0.05);
    max = Math.min(1, mid + 0.05);
  }
  return { min, max };
}

/** Map a 0–1 slider value to a denoise value within the effective range. */
export function sliderToDenoise(
  sliderPercent: number,
  range: CreativityRange | null,
): number {
  const { min, max } = getEffectiveRange(range);
  return min + sliderPercent * (max - min);
}

/** Update the tracked creativity range with a new observed value. */
export function updateCreativityRange(
  current: CreativityRange | null,
  newVal: number,
): CreativityRange {
  if (!current) {
    return { min: newVal, max: newVal };
  }
  return {
    min: Math.min(current.min, newVal),
    max: Math.max(current.max, newVal),
  };
}
