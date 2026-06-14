export async function createJob(files) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const response = await fetch("/api/jobs", {
    method: "POST",
    body: formData
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Upload failed");
  }
  return response.json();
}

export async function getJob(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`);
  if (!response.ok) throw new Error("Job not found");
  return response.json();
}

export async function getDocuments(jobId) {
  const response = await fetch(`/api/jobs/${jobId}/documents`);
  if (!response.ok) throw new Error("Documents are not ready");
  return response.json();
}

export async function getGraph(jobId) {
  const response = await fetch(`/api/jobs/${jobId}/graph`);
  if (!response.ok) throw new Error("Structured output is not ready");
  return response.json();
}

export async function getSource(documentId, sourceId) {
  const response = await fetch(`/api/documents/${documentId}/source/${sourceId}`);
  if (!response.ok) throw new Error("Source not found");
  return response.json();
}

