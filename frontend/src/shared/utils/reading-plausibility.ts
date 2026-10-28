export type ReadingWarning =
  | { kind: "decrease" }
  | { kind: "spike"; typicalKwh: number; usageKwh: number };

export interface MeterPair {
  day: number;
  night: number;
}

const SPIKE_FACTOR = 3;
const SPIKE_FLOOR_KWH = 50;

function median(values: number[]): number {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);

  if (ordered.length % 2 === 1) {
    return ordered[middle] ?? 0;
  }

  return ((ordered[middle - 1] ?? 0) + (ordered[middle] ?? 0)) / 2;
}

/**
 * Mirrors the backend's detect_review_reason: `history` is the household's real
 * readings newest first. The reading is never blocked; this only tells the
 * resident before they send, and the backend flags it for the head either way.
 */
export function detectReadingWarning(
  history: MeterPair[],
  entered: MeterPair
): ReadingWarning | null {
  const previous = history[0];

  if (!previous) {
    return null;
  }

  if (entered.day < previous.day || entered.night < previous.night) {
    return { kind: "decrease" };
  }

  const usageKwh = entered.day - previous.day + (entered.night - previous.night);
  const recentUsages: number[] = [];

  for (let index = 0; index < 3; index += 1) {
    const newer = history[index];
    const older = history[index + 1];

    if (!newer || !older) {
      break;
    }

    recentUsages.push(newer.day - older.day + (newer.night - older.night));
  }

  if (recentUsages.length === 0) {
    return null;
  }

  const typicalKwh = median(recentUsages);

  if (usageKwh > SPIKE_FLOOR_KWH && usageKwh > SPIKE_FACTOR * typicalKwh) {
    return { kind: "spike", typicalKwh, usageKwh };
  }

  return null;
}
