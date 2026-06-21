import { useState } from "react";
import type { GeoFeature } from "../types/api";
import { CANOPY_CLASSES, COVER_TYPES, confidenceLabel } from "../lib/colors";

interface SegmentPanelProps {
  feature: GeoFeature | null;
  analystId: string;
  onSubmitOverride: (
    objectId: number,
    coverType: string,
    canopyClass: string,
    reason: string,
  ) => Promise<void>;
}

function metric(value: unknown, suffix = ""): string {
  if (value == null || value === "") return "—";
  if (typeof value === "number") return `${value.toFixed(2)}${suffix}`;
  return String(value);
}

export function SegmentPanel({
  feature,
  analystId,
  onSubmitOverride,
}: SegmentPanelProps) {
  const [coverType, setCoverType] = useState("");
  const [canopyClass, setCanopyClass] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (!feature) {
    return (
      <div
        className="rounded-lg border border-dashed border-slate-300 bg-white p-4"
        data-testid="segment-panel"
      >
        <p className="text-sm text-slate-500">
          Click a stand polygon on the map to inspect attributes and apply corrections.
        </p>
      </div>
    );
  }

  const props = feature.properties;
  const objectId = Number(props.object_id);
  const confidence = Number(props.confidence ?? 0);
  const isOverride = Boolean(props.manual_override);

  async function handleOverride(e: React.FormEvent) {
    e.preventDefault();
    if (!coverType || !canopyClass) return;
    setSubmitting(true);
    setMessage(null);
    try {
      await onSubmitOverride(objectId, coverType, canopyClass, reason);
      setMessage("Correction saved — logged for future model training.");
      setReason("");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save correction");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4" data-testid="segment-panel">
      <div className="mb-3 flex items-start justify-between">
        <h3 className="text-sm font-semibold text-slate-800">
          Stand #{objectId}
        </h3>
        {isOverride && (
          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            Manually corrected
          </span>
        )}
      </div>

      <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-slate-500">Cover type</dt>
        <dd className="font-medium capitalize" data-testid="segment-cover-type">
          {String(props.cover_type ?? "—")}
        </dd>

        <dt className="text-slate-500">Canopy closure</dt>
        <dd className="font-medium capitalize">{String(props.canopy_closure_class ?? "—")}</dd>

        <dt className="text-slate-500">Confidence</dt>
        <dd data-testid="segment-confidence">
          {(confidence * 100).toFixed(1)}% — {confidenceLabel(confidence)}
        </dd>

        <dt className="text-slate-500">Area (m²)</dt>
        <dd>{metric(props.area_m2)}</dd>

        <dt className="text-slate-500">Perimeter (m)</dt>
        <dd>{metric(props.perimeter_m)}</dd>

        <dt className="text-slate-500">Compactness</dt>
        <dd>{metric(props.compactness)}</dd>
      </dl>

      <form onSubmit={handleOverride} className="space-y-3 border-t border-slate-100 pt-3">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Manual override
        </p>

        <div>
          <label htmlFor="override-cover" className="block text-xs text-slate-600">
            Cover type
          </label>
          <select
            id="override-cover"
            value={coverType}
            onChange={(e) => setCoverType(e.target.value)}
            required
            className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            data-testid="override-cover-select"
          >
            <option value="">Select…</option>
            {COVER_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="override-canopy" className="block text-xs text-slate-600">
            Canopy closure
          </label>
          <select
            id="override-canopy"
            value={canopyClass}
            onChange={(e) => setCanopyClass(e.target.value)}
            required
            className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            data-testid="override-canopy-select"
          >
            <option value="">Select…</option>
            {CANOPY_CLASSES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="override-reason" className="block text-xs text-slate-600">
            Reason (optional)
          </label>
          <textarea
            id="override-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            placeholder="e.g. Visible hardwood regeneration in orthophoto"
            className="mt-0.5 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            data-testid="override-reason"
          />
        </div>

        <button
          type="submit"
          disabled={submitting || !analystId}
          className="w-full rounded bg-slate-800 px-3 py-2 text-sm font-medium text-white hover:bg-slate-900 disabled:opacity-50"
          data-testid="override-submit"
        >
          {submitting ? "Saving…" : "Save correction"}
        </button>

        {!analystId && (
          <p className="text-xs text-amber-700">Set your analyst ID in the header to log corrections.</p>
        )}

        {message && (
          <p className="text-xs text-slate-600" data-testid="override-message">
            {message}
          </p>
        )}
      </form>
    </div>
  );
}
