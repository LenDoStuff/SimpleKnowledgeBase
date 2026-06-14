import { UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

export function DropZone({ onFiles, disabled }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  function handleFiles(fileList) {
    const files = Array.from(fileList || []);
    if (files.length) onFiles(files);
  }

  return (
    <section className="drop-section">
      <div className="panel-title">Drop claim files</div>
      <button
        type="button"
        className={`drop-zone ${dragging ? "is-dragging" : ""}`}
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          handleFiles(event.dataTransfer.files);
        }}
      >
        <UploadCloud size={42} />
        <strong>Drag & drop files here</strong>
        <span>or click to browse</span>
        <small>PDF, DOCX, XLSX, PNG up to 200 MB per file</small>
      </button>
      <input
        ref={inputRef}
        className="file-input"
        type="file"
        multiple
        accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx,.doc,.xls"
        onChange={(event) => handleFiles(event.target.files)}
      />
    </section>
  );
}

