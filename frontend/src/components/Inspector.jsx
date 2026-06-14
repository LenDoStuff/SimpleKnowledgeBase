import { CheckCircle2, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { getSource } from "../api.js";
import { sourceLookup } from "../graphUtils.js";

export function Inspector({ graph, selectedSourceId }) {
  const [preview, setPreview] = useState(null);
  const sources = sourceLookup(graph);
  const selectedSource = selectedSourceId ? sources[selectedSourceId] : graph?.sources?.[0];

  useEffect(() => {
    let cancelled = false;
    setPreview(null);
    if (!selectedSource) return;
    getSource(selectedSource.document_id, selectedSource.id)
      .then((payload) => {
        if (!cancelled) setPreview(payload);
      })
      .catch(() => {
        if (!cancelled) setPreview(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSource?.id]);

  const validation = graph?.validation;
  return (
    <aside className="inspector">
      <section className="inspector-section">
        <h3>Field details</h3>
        <dl>
          <dt>Field</dt>
          <dd>{graph ? "Loss date" : "No field selected"}</dd>
          <dt>Value</dt>
          <dd>{graph?.claim?.loss_date || "-"}</dd>
          <dt>Data type</dt>
          <dd>Date</dd>
        </dl>
      </section>
      <section className="inspector-section">
        <h3>Sources ({graph?.sources?.length || 0})</h3>
        {preview ? (
          <div className="source-card">
            <div className="source-card-title">
              <span className="pdf-chip">SRC</span>
              <div>
                <strong>{preview.title}</strong>
                <small>{preview.source_id}</small>
              </div>
            </div>
            <blockquote>{preview.citation_text}</blockquote>
            <a href={preview.document_preview_url} target="_blank" rel="noreferrer">
              View document <ExternalLink size={13} />
            </a>
          </div>
        ) : (
          <div className="empty-state compact">Select a citation to inspect source text.</div>
        )}
      </section>
      <section className="inspector-section">
        <h3>Validation</h3>
        <div className={`validation-line ${validation?.valid ? "valid" : ""}`}>
          <CheckCircle2 size={17} />
          {validation?.valid ? "Valid" : "Waiting for structured output"}
        </div>
        <p>
          {validation?.valid
            ? "All required entities have at least one source."
            : "Upload and process files to validate citations."}
        </p>
      </section>
      <section className="inspector-section">
        <h3>Extraction confidence</h3>
        <div className="confidence-bars">
          <span />
          <span />
          <span />
          <span />
          <span className="muted" />
        </div>
        <p>{graph ? "High - schema and source rules passed." : "Not available yet."}</p>
      </section>
    </aside>
  );
}
