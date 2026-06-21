import { useEffect, useState } from "react";
import type { JobStatusResponse } from "../types/api";

const TERMINAL: Set<string> = new Set(["completed", "failed"]);

interface UseJobPollingOptions {
  intervalMs?: number;
  fetchStatus: (jobId: string) => Promise<JobStatusResponse>;
}

export function useJobPolling(
  jobId: string | null,
  { intervalMs = 2000, fetchStatus }: UseJobPollingOptions,
) {
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      setLoading(true);
      try {
        const status = await fetchStatus(jobId!);
        if (cancelled) return;
        setJob(status);
        setError(null);
        if (!TERMINAL.has(status.status)) {
          timer = setTimeout(poll, intervalMs);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Polling failed");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId, intervalMs, fetchStatus]);

  return { job, loading, error };
}
