
import { useState } from "react";
import { GitCompareArrows, History, LoaderCircle, RefreshCw } from "lucide-react";
import {
  compareVersions,
  getVersionHistory,
  type VersionHistoryResponse,
  type VersionComparisonResponse,
} from "../api/client";

function VersionHistoryPanel() {
  const [documentKey, setDocumentKey] = useState("leave123");
  const [history, setHistory] = useState<VersionHistoryResponse | null>(null);
  const [fromVersion, setFromVersion] = useState("");
  const [toVersion, setToVersion] = useState("");
  const [comparison, setComparison] = useState<VersionComparisonResponse | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingComparison, setLoadingComparison] = useState(false);
  const [error, setError] = useState("");

  async function loadHistory() {
    if (!documentKey.trim()) {
      setError("Enter a document key.");
      return;
    }

    setLoadingHistory(true);
    setError("");
    setHistory(null);
    setComparison(null);

    try {
      const data = await getVersionHistory(documentKey.trim());
      setHistory(data);
      const published = data.versions.filter((version) => version.status === "published");
      setFromVersion(published[0]?.version_label ?? "");
      setToVersion(published[1]?.version_label ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load version history.");
    } finally {
      setLoadingHistory(false);
    }
  }

  async function runComparison() {
    if (!fromVersion || !toVersion) {
      setError("Choose two published versions to compare.");
      return;
    }

    setLoadingComparison(true);
    setError("");
    setComparison(null);

    try {
      const data = await compareVersions(
        documentKey.trim(),
        fromVersion,
        toVersion,
      );
      setComparison(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed.");
    } finally {
      setLoadingComparison(false);
    }
  }

  return (
    <section className="history-panel">
      <div className="upload-heading">
        <span className="upload-icon"><History size={19} /></span>
        <div>
          <h2>Version history</h2>
          <p>Inspect document timelines and compare published versions.</p>
        </div>
      </div>

      <form
        className="history-search"
        onSubmit={(event) => {
          event.preventDefault();
          void loadHistory();
        }}
      >
        <div className="field">
          <label className="field-label" htmlFor="historyKey">Document key</label>
          <input
            id="historyKey"
            value={documentKey}
            onChange={(event) => setDocumentKey(event.target.value)}
            required
          />
        </div>
        <button className="submit-button" type="submit" disabled={loadingHistory}>
          {loadingHistory ? <LoaderCircle className="spin" size={17} /> : <RefreshCw size={16} />}
          Load history
        </button>
      </form>

      {history && (
        <>
          <div className="history-title">
            <div>
              <h3>{history.title}</h3>
              <p>{history.document_key} · {history.versions.length} versions</p>
            </div>
          </div>

          <div className="version-list">
            {history.versions.map((version) => (
              <article className="version-row" key={version.version_label}>
                <div className="version-timeline-dot" />
                <div className="version-row-content">
                  <div className="version-row-title">
                    <strong>{version.version_label}</strong>
                    <span className={`status-tag ${version.status === "published" ? "published" : "draft"}`}>
                      {version.status}
                    </span>
                  </div>
                  <p>{version.source_filename}</p>
                  <span className="version-date">
                    Effective {new Date(version.effective_from).toLocaleDateString()}
                    {version.effective_to
                      ? ` · Until ${new Date(version.effective_to).toLocaleDateString()}`
                      : ""}
                  </span>
                </div>
              </article>
            ))}
          </div>

          <div className="compare-box">
            <h3><GitCompareArrows size={17} /> Compare versions</h3>
            <div className="compare-fields">
              <div className="field">
                <label className="field-label" htmlFor="fromVersion">From version</label>
                <select
                  id="fromVersion"
                  value={fromVersion}
                  onChange={(event) => setFromVersion(event.target.value)}
                >
                  <option value="">Choose version</option>
                  {history.versions
                    .filter((version) => version.status === "published")
                    .map((version) => (
                      <option key={version.version_label} value={version.version_label}>
                        {version.version_label}
                      </option>
                    ))}
                </select>
              </div>

              <div className="field">
                <label className="field-label" htmlFor="toVersion">To version</label>
                <select
                  id="toVersion"
                  value={toVersion}
                  onChange={(event) => setToVersion(event.target.value)}
                >
                  <option value="">Choose version</option>
                  {history.versions
                    .filter((version) => version.status === "published")
                    .map((version) => (
                      <option key={version.version_label} value={version.version_label}>
                        {version.version_label}
                      </option>
                    ))}
                </select>
              </div>
            </div>
            <button
              className="submit-button compare-button"
              type="button"
              disabled={loadingComparison}
              onClick={() => void runComparison()}
            >
              {loadingComparison ? (
                <><LoaderCircle className="spin" size={17} /> Comparing...</>
              ) : (
                <><GitCompareArrows size={17} /> Compare versions</>
              )}
            </button>
          </div>
        </>
      )}

      {error && <div className="error-panel"><strong>Request failed</strong><p>{error}</p></div>}

      {comparison && (
        <div className="comparison-results">
          <div className="comparison-summary">
            <span className="eyebrow">COMPARISON RESULTS</span>
            <h3>{comparison.from_version.version} → {comparison.to_version.version}</h3>
            <p>{comparison.total_changes} text differences detected</p>
          </div>

          {comparison.fact_changes?.length > 0 && (
            <div className="fact-change-list">
              <h4>Numerical policy changes</h4>
              {comparison.fact_changes.map((change, index) => (
                <article className="fact-change-card" key={`${change.concept}-${index}`}>
                  <div className="fact-change-heading">
                    <strong>{change.concept}</strong>
                    <span className={`change-tag ${change.change_type}`}>
                      {change.change_type}
                    </span>
                  </div>
                  <div className="fact-values">
                    <div>
                      <span>Previous</span>
                      <strong>{change.old_value ?? "—"} {change.old_value !== null ? change.unit : ""}</strong>
                      {change.old_evidence && <p>{change.old_evidence}</p>}
                    </div>
                    <div>
                      <span>Updated</span>
                      <strong>{change.new_value ?? "—"} {change.new_value !== null ? change.unit : ""}</strong>
                      {change.new_evidence && <p>{change.new_evidence}</p>}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}

          <div className="text-change-list">
            <h4>Text differences</h4>
            {comparison.changes.length === 0 ? (
              <p>No sentence-level differences were detected.</p>
            ) : (
              comparison.changes.map((change, index) => (
                <article className="text-change-card" key={index}>
                  <span className={`change-tag ${change.change_type}`}>
                    {change.change_type}
                  </span>
                  {change.old_text && (
                    <div className="old-text">
                      <strong>Previous</strong>
                      <p>{change.old_text}</p>
                    </div>
                  )}
                  {change.new_text && (
                    <div className="new-text">
                      <strong>Updated</strong>
                      <p>{change.new_text}</p>
                    </div>
                  )}
                </article>
              ))
            )}
          </div>
        </div>
      )}
    </section>
  );
}

export default VersionHistoryPanel;
