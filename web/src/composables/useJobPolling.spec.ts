import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getJob } from "../api/client";
import type { JobRecord } from "../types/project";
import { useJobPolling } from "./useJobPolling";

vi.mock("../api/client", () => ({
  ApiError: class ApiError extends Error {},
  getJob: vi.fn(),
}));

describe("useJobPolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(getJob).mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("成功后停止轮询", async () => {
    const onFinished = vi.fn();
    vi.mocked(getJob)
      .mockResolvedValueOnce(jobRecord({ status: "running", progress: 0.4 }))
      .mockResolvedValueOnce(jobRecord({ status: "succeeded", progress: 1 }));
    const polling = useJobPolling({ intervalMs: 10, onFinished });

    await polling.start("job_1", jobRecord({ status: "pending", progress: 0 }));
    expect(polling.isPolling.value).toBe(true);

    await vi.advanceTimersByTimeAsync(10);

    expect(polling.isPolling.value).toBe(false);
    expect(polling.job.value?.status).toBe("succeeded");
    expect(onFinished).toHaveBeenCalledWith(expect.objectContaining({ status: "succeeded" }));
  });

  it("失败后停止轮询", async () => {
    const onFinished = vi.fn();
    vi.mocked(getJob).mockResolvedValueOnce(
      jobRecord({
        status: "failed",
        progress: 0.4,
        error: {
          code: "quality_gate_failed",
          step: "quality_gate",
          reason: "Export quality checks did not pass.",
          retryable: true,
          suggested_correction: "Fix failed checks.",
          details: {},
        },
      }),
    );
    const polling = useJobPolling({ intervalMs: 10, onFinished });

    await polling.start("job_1");

    expect(polling.isPolling.value).toBe(false);
    expect(polling.job.value?.status).toBe("failed");
    expect(onFinished).toHaveBeenCalledWith(expect.objectContaining({ status: "failed" }));
    expect(getJob).toHaveBeenCalledTimes(1);
  });
});

function jobRecord(overrides: Partial<JobRecord>): JobRecord {
  return {
    schema_version: "1.0",
    id: "job_1",
    project_id: "prj_1",
    type: "export_final",
    status: "pending",
    progress: 0,
    summary: "Queued.",
    created_at: "2026-05-21T00:00:00Z",
    started_at: null,
    updated_at: "2026-05-21T00:00:00Z",
    finished_at: null,
    error: null,
    output_paths: [],
    ...overrides,
  };
}
