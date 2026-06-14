import { Download, MoreVertical, Share2, ShieldCheck } from "lucide-react";

export function Header({ job, graph, onExport }) {
  const complete = job?.status === "complete";
  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">CS</div>
        <h1>Claim Structurer</h1>
      </div>
      <div className="project-trail">
        <span>Projects</span>
        <span>/</span>
        <button className="project-select">
          {graph?.claim?.id || "New claim ingestion"}
        </button>
      </div>
      <div className={`status-pill ${complete ? "status-complete" : "status-idle"}`}>
        <span className="status-dot" />
        {complete ? "Processing complete" : job ? job.status : "Ready for files"}
      </div>
      <div className="top-actions">
        <button className="action-button" onClick={onExport} disabled={!graph}>
          <Download size={15} /> Export
        </button>
        <button className="action-button" disabled={!graph}>
          <Share2 size={15} /> Share
        </button>
        <button className="validate-button" disabled={!graph}>
          <ShieldCheck size={15} /> Validate
        </button>
        <MoreVertical size={19} className="muted-icon" />
        <div className="avatar">AK</div>
      </div>
    </header>
  );
}

