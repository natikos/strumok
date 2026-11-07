import Skeleton from "primevue/skeleton";
import { describe, expect, it } from "vitest";

import { mountWithPlugins } from "@/shared/testing/mount";

import SubmissionSkeleton from "./SubmissionSkeleton.vue";

describe("SubmissionSkeleton", () => {
  it("is an aria-busy container of skeleton lines so assistive tech knows the form is loading", () => {
    const wrapper = mountWithPlugins(SubmissionSkeleton);

    expect(wrapper.attributes("aria-busy")).toBe("true");
    expect(wrapper.findAllComponents(Skeleton).length).toBeGreaterThan(0);
  });
});
