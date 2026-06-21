import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { JobProgressPanel } from "../components/JobProgressPanel";
import type { JobStatusResponse } from "../types/api";

const runningJob: JobStatusResponse = {
  job_id: "job-abc123",
  status: "running",
  workflow: "stand_delineation",
  created_at: "2026-06-21T10:00:00Z",
  updated_at: "2026-06-21T10:01:00Z",
  progress: {
    percent: 45,
    stage: "classify",
    detail: "Classifying tile 3 of 6",
  },
  error: null,
};

describe("JobProgressPanel", () => {
  it("shows idle state when no job is active", () => {
    render(<JobProgressPanel job={null} />);
    expect(screen.getByTestId("job-progress")).toHaveTextContent(
      "Submit a job to monitor",
    );
  });

  it("renders progress bar and stage for a running job", () => {
    render(<JobProgressPanel job={runningJob} />);
    expect(screen.getByTestId("job-status-badge")).toHaveTextContent("running");
    expect(screen.getByTestId("job-stage")).toHaveTextContent("Classifying attributes");
    expect(screen.getByTestId("job-percent")).toHaveTextContent("45%");
    expect(screen.getByTestId("job-progress-bar")).toHaveAttribute("aria-valuenow", "45");
    expect(screen.getByTestId("job-detail")).toHaveTextContent("tile 3 of 6");
  });

  it("shows 100% when job is completed without progress payload", () => {
    const completed: JobStatusResponse = {
      ...runningJob,
      status: "completed",
      progress: null,
    };
    render(<JobProgressPanel job={completed} />);
    expect(screen.getByTestId("job-percent")).toHaveTextContent("100%");
  });
});
