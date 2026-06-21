import { api } from "../api/client";

interface ExportBarProps {
  jobId: string | null;
  jobCompleted: boolean;
  apiKey?: string;
}

const FORMATS = [
  { id: "geojson" as const, label: "GeoJSON" },
  { id: "gpkg" as const, label: "GeoPackage" },
  { id: "shp" as const, label: "Shapefile" },
];

export function ExportBar({ jobId, jobCompleted, apiKey }: ExportBarProps) {
  if (!jobId || !jobCompleted) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white px-4 py-3" data-testid="export-bar">
        <p className="text-sm text-slate-500">
          Exports available after the job completes.
        </p>
      </div>
    );
  }

  function download(format: "geojson" | "gpkg" | "shp") {
    const url = api.exportDownloadUrl(jobId!, format);
    const link = document.createElement("a");
    link.href = url;
    if (apiKey) {
      fetch(url, { headers: { "X-API-Key": apiKey } })
        .then((r) => r.blob())
        .then((blob) => {
          link.href = URL.createObjectURL(blob);
          link.download = `stand_delineation_${jobId}.${format === "shp" ? "zip" : format}`;
          link.click();
        });
      return;
    }
    link.download = `stand_delineation_${jobId}.${format === "shp" ? "zip" : format}`;
    link.click();
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3" data-testid="export-bar">
      <p className="mb-2 text-sm font-medium text-slate-700">Export results</p>
      <div className="flex flex-wrap gap-2">
        {FORMATS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => download(id)}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
            data-testid={`export-${id}`}
          >
            Download {label}
          </button>
        ))}
      </div>
    </div>
  );
}
