import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useJobPolling } from "../hooks/useJobPolling";
import type { JobStatusResponse } from "../types/api";

function makeStatus(
  status: JobStatusResponse["status"],
  percent: number,
): JobStatusResponse {
  return {
    job_id: "job-test",
    status,
    workflow: "stand_delineation",
    created_at: "2026-06-21T10:00:00Z",
    updated_at: "2026-06-21T10:00:30Z",
    progress: { percent, stage: "segment", detail: "Processing" },
    error: null,
  };
}

describe("useJobPolling", () => {
  it("polls until job reaches a terminal status", async () => {
    const fetchStatus = vi
      .fn()
      .mockResolvedValueOnce(makeStatus("running", 20))
      .mockResolvedValueOnce(makeStatus("running", 60))
      .mockResolvedValueOnce(makeStatus("completed", 100));

    const { result } = renderHook(() =>
      useJobPolling("job-test", { fetchStatus, intervalMs: 50 }),
    );

    await waitFor(() => {
      expect(result.current.job?.status).toBe("completed");
    });

    expect(fetchStatus).toHaveBeenCalledTimes(3);
    expect(result.current.job?.progress?.percent).toBe(100);
  });

  it("stops polling after failure", async () => {
    const fetchStatus = vi
      .fn()
      .mockResolvedValueOnce(makeStatus("running", 30))
      .mockResolvedValueOnce({
        ...makeStatus("failed", 30),
        error: "Segmentation error",
      });

    const { result } = renderHook(() =>
      useJobPolling("job-test", { fetchStatus, intervalMs: 50 }),
    );

    await waitFor(() => {
      expect(result.current.job?.status).toBe("failed");
    });

    expect(fetchStatus).toHaveBeenCalledTimes(2);
    expect(result.current.job?.error).toBe("Segmentation error");
  });

  it("clears state when jobId is null", async () => {
    const fetchStatus = vi.fn();
    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) =>
        useJobPolling(id, { fetchStatus, intervalMs: 50 }),
      { initialProps: { id: "job-test" as string | null } },
    );

    await waitFor(() => expect(fetchStatus).toHaveBeenCalled());

    rerender({ id: null });
    expect(result.current.job).toBeNull();
  });
});
