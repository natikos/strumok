import { describe, expect, it } from "vitest";

import { detectReadingWarning } from "./reading-plausibility";

const history = [
  { day: 130, night: 0 },
  { day: 120, night: 0 },
  { day: 110, night: 0 },
  { day: 100, night: 0 },
];

describe("detectReadingWarning", () => {
  it("never warns without history", () => {
    expect(detectReadingWarning([], { day: 9999, night: 9999 })).toBeNull();
  });

  it("warns on a lower value on either meter", () => {
    expect(detectReadingWarning(history, { day: 129, night: 0 })).toEqual({ kind: "decrease" });
    expect(detectReadingWarning([{ day: 5, night: 5 }], { day: 6, night: 4 })).toEqual({
      kind: "decrease",
    });
  });

  it("warns on a spike only over 3x the median and over 50 kWh", () => {
    // median usage is 10 kWh, so 3x is 30 -- but the 50 kWh floor still applies.
    expect(detectReadingWarning(history, { day: 170, night: 0 })).toBeNull();
    expect(detectReadingWarning(history, { day: 190, night: 0 })).toEqual({
      kind: "spike",
      typicalKwh: 10,
      usageKwh: 60,
    });
  });

  it("uses whatever history exists and needs at least one past usage", () => {
    expect(detectReadingWarning([{ day: 100, night: 0 }], { day: 900, night: 0 })).toBeNull();
    expect(
      detectReadingWarning(
        [
          { day: 110, night: 0 },
          { day: 100, night: 0 },
        ],
        { day: 200, night: 0 }
      )
    ).toMatchObject({ kind: "spike" });
  });

  it("adds day and night together", () => {
    expect(detectReadingWarning(history, { day: 160, night: 40 })).toMatchObject({
      kind: "spike",
    });
  });
});
