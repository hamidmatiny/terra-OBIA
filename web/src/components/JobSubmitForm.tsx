import { useState } from "react";
import { api } from "../api/client";
import type { ModelSummary } from "../types/api";

interface JobSubmitFormProps {
  models: ModelSummary[];
  onJobSubmitted: (jobId: string) => void;
}

export function JobSubmitForm({ models, onJobSubmitted }: JobSubmitFormProps) {
  const [sourceUri, setSourceUri] = useState("");
  const [modelId, setModelId] = useState(models[0]?.model_id ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.submitJob({
        source_uri: sourceUri,
        model_id: modelId,
      });
      onJobSubmitted(result.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="source-uri" className="block text-sm font-medium text-slate-700">
          Source imagery URI
        </label>
        <input
          id="source-uri"
          type="text"
          required
          value={sourceUri}
          onChange={(e) => setSourceUri(e.target.value)}
          placeholder="/path/to/imagery.tif or s3://bucket/scene.tif"
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-forest-600 focus:outline-none focus:ring-1 focus:ring-forest-600"
        />
      </div>

      <div>
        <label htmlFor="model-id" className="block text-sm font-medium text-slate-700">
          Classification model
        </label>
        <select
          id="model-id"
          value={modelId}
          onChange={(e) => setModelId(e.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-forest-600 focus:outline-none focus:ring-1 focus:ring-forest-600"
        >
          {models.map((m) => (
            <option key={m.model_id} value={m.model_id}>
              {m.model_id}
              {m.overall_accuracy != null
                ? ` (${(m.overall_accuracy * 100).toFixed(1)}% acc.)`
                : ""}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting || !sourceUri || !modelId}
        className="w-full rounded-md bg-forest-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-forest-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? "Submitting…" : "Run analysis job"}
      </button>
    </form>
  );
}
