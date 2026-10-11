
import { useState, type FormEvent } from "react";
import { FileUp, CheckCircle2, LoaderCircle, AlertCircle } from "lucide-react";
import { uploadDocument, type UploadResponse } from "../api/client";

function UploadPanel() {
  const [title, setTitle] = useState("leave-policy");
  const [documentKey, setDocumentKey] = useState("leave123");
  const [versionLabel, setVersionLabel] = useState("v3");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<UploadResponse | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    if (!file) {
      setError("Choose a PDF or TXT file first.");
      setLoading(false);
      return;
    }

    const formData = new FormData();
    formData.append("title", title.trim());
    formData.append("document_key", documentKey.trim());
    formData.append("version_label", versionLabel.trim());
    formData.append("effective_from", effectiveFrom);
    formData.append("file", file);

    try {
      const response = await uploadDocument(formData);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="upload-panel">
      <div className="upload-heading">
        <span className="upload-icon"><FileUp size={19} /></span>
        <div>
          <h2>Upload a document version</h2>
          <p>Ingest a PDF or text file for version-aware retrieval.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="upload-fields">
          <div className="field">
            <label className="field-label" htmlFor="uploadTitle">Document title</label>
            <input
              id="uploadTitle"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={255}
            />
          </div>

          <div className="field">
            <label className="field-label" htmlFor="uploadKey">Document key</label>
            <input
              id="uploadKey"
              value={documentKey}
              onChange={(e) => setDocumentKey(e.target.value)}
              required
              maxLength={255}
            />
          </div>

          <div className="field">
            <label className="field-label" htmlFor="uploadVersion">Version label</label>
            <input
              id="uploadVersion"
              value={versionLabel}
              onChange={(e) => setVersionLabel(e.target.value)}
              required
              maxLength={100}
              placeholder="e.g. v3"
            />
          </div>

          <div className="field">
            <label className="field-label" htmlFor="uploadDate">Effective from</label>
            <input
              id="uploadDate"
              type="date"
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="file-picker">
          <label className="field-label" htmlFor="documentFile">Source file</label>
          <input
            id="documentFile"
            type="file"
            accept=".pdf,.txt,application/pdf,text/plain"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            required
          />
          <p>PDF or TXT · Maximum 10 MB · Scanned PDFs need OCR before upload.</p>
        </div>

        <button className="submit-button" type="submit" disabled={loading}>
          {loading ? (
            <><LoaderCircle className="spin" size={17} /> Processing document...</>
          ) : (
            <><FileUp size={17} /> Upload and process</>
          )}
        </button>
      </form>

      {error && (
        <div className="upload-feedback upload-error">
          <AlertCircle size={18} />
          <div><strong>Upload failed</strong><p>{error}</p></div>
        </div>
      )}

      {result && (
        <div className="upload-feedback upload-success">
          <CheckCircle2 size={19} />
          <div>
            <strong>Document ingested successfully</strong>
            <p>
              {result.filename} · Version {result.version_label} ·
              {" "}{result.chunks_created} chunks created
            </p>
            <p>
              {result.characters_extracted.toLocaleString()} characters extracted.
              Status: {result.status}.
            </p>
            <p className="upload-note">
              The new version is a draft. Publish it before it can appear in
              date-aware search.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

export default UploadPanel;
