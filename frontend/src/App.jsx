import { useEffect, useMemo, useState } from "react";
import { createJob, getDocuments, getGraph, getJob } from "./api.js";
import { DocumentList } from "./components/DocumentList.jsx";
import { DropZone } from "./components/DropZone.jsx";
import { Header } from "./components/Header.jsx";
import { Inspector } from "./components/Inspector.jsx";
import { SideRail } from "./components/SideRail.jsx";
import { StructuredOutput } from "./components/StructuredOutput.jsx";

export default function App() {
  const [job, setJob] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [graph, setGraph] = useState(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState(null);
  const [selectedSourceId, setSelectedSourceId] = useState(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

  async function hydrateJob(jobId) {
    const nextJob = await getJob(jobId);
    setJob(nextJob);
    setDocuments(nextJob.files || []);
    if (!selectedDocumentId && nextJob.files?.length) {
      setSelectedDocumentId(nextJob.files[0].id);
    }
    if (nextJob.status === "complete") {
      const [nextDocuments, nextGraph] = await Promise.all([getDocuments(jobId), getGraph(jobId)]);
      setDocuments(nextDocuments);
      setGraph(nextGraph);
      setSelectedSourceId(nextGraph.sources?.[0]?.id || null);
    }
    if (nextJob.status === "failed") {
      setError(nextJob.error || "Processing failed");
    }
  }

  async function handleFiles(files) {
    setError("");
    setUploading(true);
    setGraph(null);
    setDocuments([]);
    setSelectedSourceId(null);
    try {
      const created = await createJob(files);
      setJob(created);
      window.history.replaceState(null, "", `?job=${created.job_id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  useEffect(() => {
    const jobId = new URLSearchParams(window.location.search).get("job");
    if (!jobId) return;
    hydrateJob(jobId).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!job?.job_id || job.status === "complete" || job.status === "failed") return;
    const timer = window.setInterval(async () => {
      try {
        const nextJob = await getJob(job.job_id);
        setJob(nextJob);
        setDocuments(nextJob.files || []);
        if (!selectedDocumentId && nextJob.files?.length) {
          setSelectedDocumentId(nextJob.files[0].id);
        }
        if (nextJob.status === "complete") {
          const [nextDocuments, nextGraph] = await Promise.all([getDocuments(job.job_id), getGraph(job.job_id)]);
          setDocuments(nextDocuments);
          setGraph(nextGraph);
          setSelectedSourceId(nextGraph.sources?.[0]?.id || null);
          window.clearInterval(timer);
        }
        if (nextJob.status === "failed") {
          setError(nextJob.error || "Processing failed");
          window.clearInterval(timer);
        }
      } catch (err) {
        setError(err.message);
        window.clearInterval(timer);
      }
    }, 900);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status, selectedDocumentId]);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId),
    [documents, selectedDocumentId]
  );

  function exportJson() {
    if (!graph) return;
    const blob = new Blob([JSON.stringify(graph, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${graph.claim.id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <SideRail />
      <div className="main-shell">
        <Header job={job} graph={graph} onExport={exportJson} />
        {error ? <div className="error-banner">{error}</div> : null}
        <div className="workspace">
          <aside className="left-pane">
            <DropZone onFiles={handleFiles} disabled={uploading || job?.status === "processing"} />
            <DocumentList
              documents={documents}
              selectedDocumentId={selectedDocumentId}
              onSelect={setSelectedDocumentId}
            />
            {selectedDocument ? (
              <div className="selected-document">
                <strong>{selectedDocument.filename}</strong>
                <span>{selectedDocument.summary}</span>
              </div>
            ) : null}
          </aside>
          <StructuredOutput graph={graph} job={job} onSelectSource={setSelectedSourceId} />
          <Inspector graph={graph} selectedSourceId={selectedSourceId} />
        </div>
      </div>
    </div>
  );
}
