import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { ExportBar } from "../components/ExportBar";
import { JobProgressPanel } from "../components/JobProgressPanel";
import { JobSubmitForm } from "../components/JobSubmitForm";
import { MapViewer } from "../components/MapViewer";
import { SegmentPanel } from "../components/SegmentPanel";
import { useJobPolling } from "../hooks/useJobPolling";
import type { GeoFeature, ModelSummary } from "../types/api";

const ANALYST_KEY = "terra_analyst_id";

export function ReviewPage() {
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [features, setFeatures] = useState<import("../types/api").FeatureCollection | null>(null);
  const [selected, setSelected] = useState<GeoFeature | null>(null);
  const [analystId, setAnalystId] = useState(() => localStorage.getItem(ANALYST_KEY) ?? "");
  const [approved, setApproved] = useState(false);

  const fetchStatus = useCallback((id: string) => api.getJobStatus(id), []);
  const { job, loading: jobLoading } = useJobPolling(jobId, { fetchStatus });

  useEffect(() => {
    api.listModels().then((r) => setModels(r.models)).catch(console.error);
  }, []);

  useEffect(() => {
    if (analystId) localStorage.setItem(ANALYST_KEY, analystId);
  }, [analystId]);

  useEffect(() => {
    if (job?.status !== "completed" || !jobId) return;
    api.getJobFeatures(jobId).then(setFeatures).catch(console.error);
  }, [job?.status, jobId]);

  const handleCorrection = useCallback(
    async (objectId: number, coverType: string, canopyClass: string, reason: string) => {
      if (!jobId) return;
      await api.submitCorrection(jobId, {
        object_id: objectId,
        cover_type: coverType,
        canopy_closure_class: canopyClass,
        analyst_id: analystId,
        reason: reason || undefined,
      });
      const updated = await api.getJobFeatures(jobId);
      setFeatures(updated);
      const refreshed = updated.features.find(
        (f) => Number(f.properties.object_id) === objectId,
      );
      if (refreshed) setSelected(refreshed);
    },
    [jobId, analystId],
  );

  async function handleApprove() {
    if (!jobId || !analystId) return;
    await api.approveJob(jobId, analystId);
    setApproved(true);
  }

  const jobCompleted = job?.status === "completed";

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-forest-700">Terra OBIA</h1>
            <p className="text-sm text-slate-500">Stand delineation review</p>
          </div>
          <div className="flex items-center gap-3">
            <label htmlFor="analyst-id" className="text-sm text-slate-600">
              Analyst ID
            </label>
            <input
              id="analyst-id"
              type="text"
              value={analystId}
              onChange={(e) => setAnalystId(e.target.value)}
              placeholder="e.g. jsmith"
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </div>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-7xl flex-1 gap-4 p-4 lg:grid-cols-12">
        <aside className="space-y-4 lg:col-span-3">
          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">New analysis</h2>
            <JobSubmitForm models={models} onJobSubmitted={setJobId} />
          </section>

          <JobProgressPanel job={job} loading={jobLoading} />
          <ExportBar jobId={jobId} jobCompleted={jobCompleted} />

          {jobCompleted && (
            <button
              type="button"
              onClick={handleApprove}
              disabled={approved || !analystId}
              className="w-full rounded-md border border-forest-600 px-4 py-2 text-sm font-medium text-forest-600 hover:bg-forest-600 hover:text-white disabled:opacity-50"
            >
              {approved ? "Approved for delivery" : "Approve for delivery"}
            </button>
          )}
        </aside>

        <section className="flex flex-col gap-4 lg:col-span-6">
          <div className="h-[520px]">
            <MapViewer
              features={features}
              selectedObjectId={
                selected ? Number(selected.properties.object_id) : null
              }
              onSelectFeature={setSelected}
            />
          </div>
          <div className="flex flex-wrap gap-4 text-xs text-slate-600">
            <span className="flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded-sm bg-[#2d6a4f]" /> Conifer
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded-sm bg-[#bc6c25]" /> Deciduous
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded-sm bg-[#457b9d]" /> Mixed
            </span>
            <span className="text-slate-400">Opacity reflects confidence</span>
          </div>
        </section>

        <aside className="lg:col-span-3">
          <SegmentPanel
            feature={selected}
            analystId={analystId}
            onSubmitOverride={handleCorrection}
          />
        </aside>
      </main>
    </div>
  );
}
