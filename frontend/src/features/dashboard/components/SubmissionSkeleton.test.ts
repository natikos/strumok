import { describe, it } from "vitest";

import { expectLoading } from "@/shared/testing/loading";
import { mountWithPlugins } from "@/shared/testing/mount";

import SubmissionSkeleton from "./SubmissionSkeleton.vue";

describe("SubmissionSkeleton", () => {
  it("is an aria-busy container of skeleton lines so assistive tech knows the form is loading", () => {
    const wrapper = mountWithPlugins(SubmissionSkeleton);

    expectLoading(wrapper);
  });
});
