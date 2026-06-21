import type {
  CorrectionPayload,
  CorrectionResponse,
  FeatureCollection,
  JobCreatePayload,
  JobResultsResponse,
  JobStatusResponse,
  ModelSummary,
} from "../types/api";

const API_KEY = import.meta.env.VITE_API_KEY ?? "";

function headers(): HeadersInit {
  const base: HeadersInit = { "Content-Type": "application/json" };
  if (API_KEY) {
    return { ...base, "X-API-Key": API_KEY };
  }
  return base;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { ...headers(), ...init?.headers },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listModels: () => request<{ models: ModelSummary[] }>("/v1/models"),

  submitJob: (payload: JobCreatePayload) =>
    request<{ job_id: string; status: string; message: string }>("/v1/jobs", {
      method: "POST",
      body: JSON.stringify({
        workflow: "stand_delineation",
        export_formats: ["geojson", "gpkg", "shp"],
        ...payload,
      }),
    }),

  getJobStatus: (jobId: string) =>
    request<JobStatusResponse>(`/v1/jobs/${jobId}`),

  getJobResults: (jobId: string) =>
    request<JobResultsResponse>(`/v1/jobs/${jobId}/results`),

  getJobFeatures: (jobId: string) =>
    request<FeatureCollection>(`/v1/jobs/${jobId}/features`),

  submitCorrection: (jobId: string, payload: CorrectionPayload) =>
    request<CorrectionResponse>(`/v1/jobs/${jobId}/corrections`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  approveJob: (jobId: string, analystId: string, notes = "") =>
    request<{ job_id: string; approved: boolean }>(`/v1/jobs/${jobId}/approve`, {
      method: "POST",
      body: JSON.stringify({ analyst_id: analystId, notes }),
    }),

  exportDownloadUrl: (jobId: string, format: "geojson" | "gpkg" | "shp") =>
    `/v1/jobs/${jobId}/exports/${format}`,
};
