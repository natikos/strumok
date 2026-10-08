import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";

import { useCountdown } from "./useCountdown";

function mountCountdown() {
  let countdown!: ReturnType<typeof useCountdown>;
  const wrapper = mount(
    defineComponent({
      setup() {
        countdown = useCountdown();
        return () => null;
      },
    })
  );
  return { countdown, wrapper };
}

describe("useCountdown", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("counts down to zero and formats mm:ss", () => {
    const { countdown } = mountCountdown();

    countdown.start(75);
    expect(countdown.formatted.value).toBe("01:15");

    vi.advanceTimersByTime(74_000);
    expect(countdown.seconds.value).toBe(1);

    vi.advanceTimersByTime(1_000);
    expect(countdown.seconds.value).toBe(0);
  });

  it("restarting replaces the running countdown", () => {
    const { countdown } = mountCountdown();

    countdown.start(10);
    vi.advanceTimersByTime(3_000);
    countdown.start(20);
    vi.advanceTimersByTime(1_000);

    expect(countdown.seconds.value).toBe(19);
  });
});
