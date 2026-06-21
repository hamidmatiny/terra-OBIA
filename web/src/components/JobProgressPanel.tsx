import type { JobStatusResponse } from "../types/api";
import { STAGE_LABELS } from "../lib/colors";

interface JobProgressPanelProps {
  job: JobStatusResponse | null;
  loading?: boolean;
}

export function JobProgressPanel({ job, loading }: JobProgressPanelProps) {
  if (loading && !job) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4" data-testid="job-progress">
        <p className="text-sm text-slate-500">Loading job status…</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-4" data-testid="job-progress">
        <p className="text-sm text-slate-500">
          Submit a job to monitor pipeline progress here.
        </p>
      </div>
    );
  }

  const percent = job.progress?.percent ?? (job.status === "completed" ? 100 : 0);
  const stageKey = job.progress?.stage ?? job.status;
  const stageLabel = STAGE_LABELS[stageKey] ?? stageKey;

  const statusColors: Record<string, string> = {
    queued: "bg-slate-100 text-slate-700",
    running: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4" data-testid="job-progress">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-800">Job progress</h3>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusColors[job.status] ?? ""}`}
          data-testid="job-status-badge"
        >
          {job.status}
        </span>
      </div>

      <p className="mb-1 font-mono text-xs text-slate-500">{job.job_id}</p>

      <div className="mb-2">
        <div className="mb-1 flex justify-between text-xs text-slate-600">
          <span data-testid="job-stage">{stageLabel}</span>
          <span data-testid="job-percent">{percent}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-forest-600 transition-all duration-500"
            style={{ width: `${percent}%` }}
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            data-testid="job-progress-bar"
          />
        </div>
      </div>

      {job.progress?.detail && (
        <p className="text-xs text-slate-500" data-testid="job-detail">
          {job.progress.detail}
        </p>
      )}

      {job.error && (
        <p className="mt-2 text-xs text-red-600" role="alert">
          {job.error}
        </p>
      )}
    </div>
  );
}
