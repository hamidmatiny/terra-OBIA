export type JobStatus = "queued" | "running" | "completed" | "failed";

export interface JobProgress {
  percent: number;
  stage: string;
  detail: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  workflow: string;
  created_at: string;
  updated_at: string;
  progress: JobProgress | null;
  error: string | null;
}

export interface ModelSummary {
  model_id: string;
  workflow: string;
  training_date: string;
  training_data_description: string;
  overall_accuracy: number | null;
  mean_iou: number | null;
}

export interface JobCreatePayload {
  source_uri: string;
  model_id: string;
  workflow?: string;
  segmentation?: {
    backend?: string;
    n_segments?: number;
    compactness?: number;
    tile_size?: number;
    overlap?: number;
  };
}

export interface ExportInfo {
  format: "geojson" | "gpkg" | "shp";
  path: string;
  crs: string | null;
}

export interface JobResultsResponse {
  job_id: string;
  status: JobStatus;
  object_count: number;
  model_id: string;
  exports: ExportInfo[];
  summary: Record<string, unknown>;
}

export interface GeoFeature {
  type: "Feature";
  geometry: GeoJSON.Geometry;
  properties: Record<string, unknown>;
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: GeoFeature[];
}

export interface CorrectionPayload {
  object_id: number;
  cover_type: string;
  canopy_closure_class: string;
  analyst_id: string;
  reason?: string;
}

export interface CorrectionResponse {
  object_id: number;
  cover_type: string;
  canopy_closure_class: string;
  confidence: number;
  manual_override: boolean;
  corrected_by: string;
  corrected_at: string;
}
