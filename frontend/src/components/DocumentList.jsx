import { FileImage, FileSpreadsheet, FileText, Filter } from "lucide-react";
import { groupDocuments } from "../graphUtils.js";

function iconFor(document) {
  if (document.file_type === "image") return FileImage;
  if (document.file_type === "xlsx") return FileSpreadsheet;
  return FileText;
}

export function DocumentList({ documents, selectedDocumentId, onSelect }) {
  const groups = groupDocuments(documents);
  const total = documents.length;
  return (
    <section className="documents-section">
      <div className="section-head">
        <div>
          <h2>Sorted documents</h2>
          <span className="count-pill">{total}</span>
        </div>
        <Filter size={16} className="muted-icon" />
      </div>
      <div className="document-table-head">
        <span>Type</span>
        <span>File name</span>
        <span>Pages</span>
        <span>Status</span>
      </div>
      <div className="document-list">
        {total === 0 ? (
          <div className="empty-state">Uploaded claim files will be classified here.</div>
        ) : (
          Object.entries(groups).map(([group, groupDocuments]) => (
            <div className="document-group" key={group}>
              <div className="group-label">
                <span>{group}</span>
                <span className="count-pill small">{groupDocuments.length}</span>
              </div>
              {groupDocuments.map((document) => {
                const Icon = iconFor(document);
                return (
                  <button
                    className={`document-row ${selectedDocumentId === document.id ? "selected" : ""}`}
                    key={document.id}
                    type="button"
                    onClick={() => onSelect(document.id)}
                  >
                    <Icon size={16} />
                    <span className="document-name">{document.filename}</span>
                    <span>{document.pages || "-"}</span>
                    <span className={`row-status ${document.status}`}>{document.status}</span>
                  </button>
                );
              })}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
