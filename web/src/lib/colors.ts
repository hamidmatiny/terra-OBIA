/** Color stand polygons by cover type and confidence for map styling. */

const COVER_COLORS: Record<string, string> = {
  conifer: "#2d6a4f",
  deciduous: "#bc6c25",
  mixed: "#457b9d",
  default: "#6c757d",
};

export function coverColor(coverType: string, confidence: number): string {
  const base = COVER_COLORS[coverType.toLowerCase()] ?? COVER_COLORS.default;
  if (confidence >= 0.8) return base;
  if (confidence >= 0.5) return `${base}cc`;
  return `${base}88`;
}

export function confidenceLabel(confidence: number): string {
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.5) return "Moderate";
  return "Low — review recommended";
}

export const COVER_TYPES = ["conifer", "deciduous", "mixed"] as const;
export const CANOPY_CLASSES = ["open", "sparse", "moderate", "dense"] as const;

export const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  ingest: "Ingesting imagery",
  segment: "Segmenting stands",
  merge: "Merging tile boundaries",
  classify: "Classifying attributes",
  export: "Exporting GIS files",
  done: "Complete",
};
