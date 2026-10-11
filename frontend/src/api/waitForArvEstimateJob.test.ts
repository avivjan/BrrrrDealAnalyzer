// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import api, {
  apiClient,
  ARV_ESTIMATE_MAXIMUM_WAIT_MILLISECONDS,
  ARV_ESTIMATE_POLL_INTERVAL_MILLISECONDS,
  ARV_ESTIMATE_STILL_RUNNING_MESSAGE,
  waitForArvEstimateJob,
} from "./index";
import type { ArvEstimateJobRes, ArvEstimateRes } from "../types/arvEstimate";

const CLAUDE_ARV_ESTIMATE = { target_arv: 205000 } as ArvEstimateRes;

function arvEstimateJob(overrides: Partial<ArvEstimateJobRes> = {}): ArvEstimateJobRes {
  return { arv_estimate_job_id: "job-1", status: "RUNNING", arv_estimate: null, failure_message: null, ...overrides };
}

/** A fake clock: every `sleep` advances it instead of waiting. */
function fakeClock() {
  let nowInMilliseconds = 0;
  const sleptMilliseconds: number[] = [];
  return {
    sleptMilliseconds,
    sleep: async (milliseconds: number) => {
      sleptMilliseconds.push(milliseconds);
      nowInMilliseconds += milliseconds;
    },
    now: () => nowInMilliseconds,
  };
}

describe("waitForArvEstimateJob", () => {
  it("polls a running job every few seconds until it succeeds", async () => {
    const clock = fakeClock();
    const getJob = vi
      .fn()
      .mockResolvedValueOnce(arvEstimateJob())
      .mockResolvedValueOnce(arvEstimateJob({ status: "SUCCEEDED", arv_estimate: CLAUDE_ARV_ESTIMATE }));

    const arvEstimate = await waitForArvEstimateJob(arvEstimateJob(), getJob, clock.sleep, clock.now);

    expect(arvEstimate).toBe(CLAUDE_ARV_ESTIMATE);
    expect(getJob).toHaveBeenCalledTimes(2);
    expect(getJob).toHaveBeenCalledWith("job-1");
    expect(clock.sleptMilliseconds).toEqual([ARV_ESTIMATE_POLL_INTERVAL_MILLISECONDS, ARV_ESTIMATE_POLL_INTERVAL_MILLISECONDS]);
  });

  it("throws a failed job's safe message where the popup reads API errors", async () => {
    const clock = fakeClock();
    const getJob = vi.fn().mockResolvedValue(arvEstimateJob({ status: "FAILED", failure_message: "Claude declined to estimate this property." }));

    await expect(waitForArvEstimateJob(arvEstimateJob(), getJob, clock.sleep, clock.now)).rejects.toMatchObject({
      response: { data: { detail: "Claude declined to estimate this property." } },
    });
  });

  it("gives up after the maximum wait", async () => {
    const clock = fakeClock();
    const getJob = vi.fn().mockResolvedValue(arvEstimateJob());

    await expect(waitForArvEstimateJob(arvEstimateJob(), getJob, clock.sleep, clock.now)).rejects.toMatchObject({
      response: { data: { detail: ARV_ESTIMATE_STILL_RUNNING_MESSAGE } },
    });
    expect(getJob).toHaveBeenCalledTimes(ARV_ESTIMATE_MAXIMUM_WAIT_MILLISECONDS / ARV_ESTIMATE_POLL_INTERVAL_MILLISECONDS);
  });

  it("lets a poll's own error through (a 404 after a server restart carries its detail)", async () => {
    const clock = fakeClock();
    const notFoundError = Object.assign(new Error("Request failed with status code 404"), {
      response: { status: 404, data: { detail: "This ARV estimate is no longer available (the server may have restarted); start a new one." } },
    });
    const getJob = vi.fn().mockImplementation(async () => {
      throw notFoundError;
    });

    await expect(waitForArvEstimateJob(arvEstimateJob(), getJob, clock.sleep, clock.now)).rejects.toBe(notFoundError);
  });

  it("returns at once when the job is already finished", async () => {
    const clock = fakeClock();
    const getJob = vi.fn();
    const arvEstimate = await waitForArvEstimateJob(
      arvEstimateJob({ status: "SUCCEEDED", arv_estimate: CLAUDE_ARV_ESTIMATE }),
      getJob,
      clock.sleep,
      clock.now,
    );
    expect(arvEstimate).toBe(CLAUDE_ARV_ESTIMATE);
    expect(getJob).not.toHaveBeenCalled();
  });
});

describe("api.estimateArvWithClaude", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("starts the job with one POST, then polls its GET until the estimate is ready", async () => {
    vi.useFakeTimers();
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: arvEstimateJob({ arv_estimate_job_id: "abc123" }) });
    const get = vi
      .spyOn(apiClient, "get")
      .mockResolvedValueOnce({ data: arvEstimateJob({ arv_estimate_job_id: "abc123" }) })
      .mockResolvedValueOnce({ data: arvEstimateJob({ arv_estimate_job_id: "abc123", status: "SUCCEEDED", arv_estimate: CLAUDE_ARV_ESTIMATE }) });

    const arvEstimatePromise = api.estimateArvWithClaude({ deal_type: "FLIP", property_address: "1 Oak Ave", investor_situation_note: "" });
    await vi.advanceTimersByTimeAsync(ARV_ESTIMATE_POLL_INTERVAL_MILLISECONDS * 2);

    await expect(arvEstimatePromise).resolves.toBe(CLAUDE_ARV_ESTIMATE);
    expect(post).toHaveBeenCalledOnce();
    expect(post.mock.calls[0]![0]).toBe("/arv-estimate");
    expect(get.mock.calls.map((call) => call[0])).toEqual(["/arv-estimate/abc123", "/arv-estimate/abc123"]);
  });
});
