const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export interface Citation {
  document_key: string;
  title: string;
  version: string;
  effective_from: string;
  effective_to: string | null;
  chunk_index: number;
  similarity: number;
  quoted_text: string;
}

export interface AnswerResponse {
  question: string;
  as_of: string;
  answer: string | null;
  answer_type?: string;
  message?: string;
  citations: Citation[];
}

export async function askQuestion(payload: {
  question: string;
  document_key?: string;
  as_of: string;
  top_k: number;
}): Promise<AnswerResponse> {
  const response = await fetch(`${API_URL}/documents/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail ?? `Request failed (${response.status})`);
  }

  return response.json();
}

export interface UploadResponse {
  document_id: number;
  document_key: string;
  version_id: number;
  version_label: string;
  effective_from: string;
  status: string;
  filename: string;
  characters_extracted: number;
  chunks_created: number;
  message: string;
}

export async function uploadDocument(formData: FormData): Promise<UploadResponse> {
  const response = await fetch(`${API_URL}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail ?? `Upload failed (${response.status})`);
  }

  return response.json();
}

export interface DocumentVersion {
  version_label: string;
  effective_from: string;
  effective_to: string | null;
  status: string;
  source_filename: string;
}

export interface VersionHistoryResponse {
  document_key: string;
  title: string;
  versions: DocumentVersion[];
}

export interface VersionComparisonResponse {
  document_key: string;
  title: string;
  from_version: {
    version: string;
    effective_from: string;
  };
  to_version: {
    version: string;
    effective_from: string;
  };
  total_changes: number;
  changes: {
    change_type: "modified" | "added" | "removed";
    old_text: string;
    new_text: string;
  }[];
  fact_changes: {
    concept: string;
    change_type: "increased" | "decreased" | "added" | "removed";
    old_value: number | null;
    new_value: number | null;
    unit: string;
    old_evidence: string | null;
    new_evidence: string | null;
  }[];
}

export async function getVersionHistory(
  documentKey: string,
): Promise<VersionHistoryResponse> {
  const response = await fetch(
    `${API_URL}/documents/${encodeURIComponent(documentKey)}/versions`,
  );

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail ?? `History request failed (${response.status})`);
  }

  return response.json();
}

export async function compareVersions(
  documentKey: string,
  fromVersion: string,
  toVersion: string,
): Promise<VersionComparisonResponse> {
  const params = new URLSearchParams({
    from_version: fromVersion,
    to_version: toVersion,
  });

  const response = await fetch(
    `${API_URL}/documents/${encodeURIComponent(documentKey)}/compare?${params}`,
  );

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail ?? `Comparison failed (${response.status})`);
  }

  return response.json();
}


export interface DocumentItem {
  document_key: string;
  title: string;
  created_at: string | null;
  versions: {
    version_label: string;
    effective_from: string;
    effective_to: string | null;
    status: "draft" | "published";
    source_filename: string;
  }[];
}

export async function getDocuments(): Promise<{
  documents: DocumentItem[];
}> {
  const response = await fetch(`${API_URL}/documents`);

  if (!response.ok) {
    throw new Error(`Failed to load documents (${response.status})`);
  }

  return response.json();
}

export async function publishVersion(
  documentKey: string,
  versionLabel: string,
): Promise<{ status: string; message: string }> {
  const response = await fetch(
    `${API_URL}/documents/${encodeURIComponent(documentKey)}/versions/${encodeURIComponent(versionLabel)}/publish`,
    { method: "POST" },
  );

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail ?? `Publish failed (${response.status})`);
  }

  return response.json();
}
