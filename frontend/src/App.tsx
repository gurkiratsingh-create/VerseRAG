import { useEffect, useState, type FormEvent } from "react";

import {
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  FileSearch,
  GitCompare,
  LoaderCircle,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { askQuestion, type AnswerResponse } from "./api/client";
import "./App.css";
import UploadPanel from "./components/UploadPanel";
import VersionHistoryPanel from "./components/VersionHistory";
import DocumentsPage, { THEMES, type ThemeId } from "./components/DocumentsPage";

type Page = "ask" | "documents" | "arena";

const NAV: { id: Page; label: string; jp: string; icon: typeof Search }[] = [
  { id: "ask", label: "Ask questions", jp: "質問する", icon: Search },
  { id: "documents", label: "Documents", jp: "ドキュメント", icon: FileSearch },
  { id: "arena", label: "Version arena", jp: "バージョン比較", icon: GitCompare },
];

function localDate(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset();
  return new Date(now.getTime() - offset * 60_000).toISOString().slice(0, 10);
}

/** Visual-novel style reveal for the answer text. */
function useTypewriter(text: string) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setN(text.length);
      return;
    }
    setN(0);
    const id = window.setInterval(() => {
      setN((c) => {
        if (c >= text.length) {
          window.clearInterval(id);
          return c;
        }
        return c + 2;
      });
    }, 16);
    return () => window.clearInterval(id);
  }, [text]);
  return text.slice(0, n);
}

function Hero({
  arc,
  l1,
  l2,
  sub,
  kanji,
  sfx,
}: {
  arc: string;
  l1: string;
  l2: string;
  sub: string;
  kanji: string;
  sfx: string;
}) {
  return (
    <header className="vx-hero">
      <div className="vx-hero-rays" aria-hidden="true" />
      <div className="vx-hero-copy">
        <p className="vx-arc">
          <span>{arc}</span>
        </p>
        <h1 data-t={l1}>{l1}</h1>
        <h1 style={{ marginBottom: '24px' }}data-t={l2} className="vx-h1-second">
          {l2}
        </h1>
        
        <p className="vx-hero-sub">{sub}</p>
      </div>
      <div className="vx-hero-art" aria-hidden="true">
        <div className="vx-ring vx-ring-a" />
        <div className="vx-ring vx-ring-b" />
        <span className="vx-hero-kanji">{kanji}</span>
        <span className="vx-sfx">{sfx}</span>
      </div>
    </header>
  );
}

function App() {
  const [activePage, setActivePage] = useState<Page>("ask");
  const [themeId, setThemeId] = useState<ThemeId>(() => {
    try {
      const saved = localStorage.getItem("verserag-theme");
      return THEMES.some((t) => t.id === saved) ? (saved as ThemeId) : "sorcerer";
    } catch {
      return "sorcerer";
    }
  });
  const theme = THEMES.find((t) => t.id === themeId) ?? THEMES[2];

  const [question, setQuestion] = useState(
    "How many days of annual leave are available to full-time employees?",
  );
  const [documentKey, setDocumentKey] = useState("leave123");
  const [asOf, setAsOf] = useState("2026-06-01");
  const [topK, setTopK] = useState("5");

  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const typed = useTypewriter(result?.answer ?? "");

  function pickTheme(id: ThemeId) {
    setThemeId(id);
    try {
      localStorage.setItem("verserag-theme", id);
    } catch {
      /* storage unavailable: theme just won't persist */
    }
  }

  function go(page: Page) {
    setActivePage(page);
    setError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await askQuestion({
        question: question.trim(),
        document_key: documentKey.trim() || undefined,
        as_of: asOf,
        top_k: Number(topK),
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  const crumb = NAV.find((n) => n.id === activePage)?.label ?? "";

  return (
    <div className="app-shell" data-theme={themeId}>
      {/* the world behind everything */}
      <div className="vx-bg" aria-hidden="true">
        <span key={themeId} className="vx-bg-kanji">
          {theme.kanji}
        </span>
      </div>
      <div key={`wipe-${themeId}`} className="vx-wipe" aria-hidden="true" />

      <aside className="sidebar">
        <a
          className="brand"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            go("ask");
          }}
        >
          <span className="brand-mark">
            <BookOpen size={24} />
          </span>
          <span className="brand-text">
            Verse<span className="brand-accent">RAG</span>
            <small>アーカイブ</small>
          </span>
        </a>

        <nav className="nav-list" aria-label="Main">
          {NAV.map(({ id, label, jp, icon: Icon }) => (
            <button
              key={id}
              type="button"
              className={`nav-item ${activePage === id ? "active" : ""}`}
              aria-current={activePage === id ? "page" : undefined}
              onClick={() => go(id)}
            >
              <Icon size={20} />
              <span>
                {label}
                <small>{jp}</small>
              </span>
            </button>
          ))}
        </nav>

        <div className="sidebar-worlds">
          <span className="workspace-label">CHOOSE YOUR WORLD</span>
          <div className="ax-seals" role="radiogroup" aria-label="Choose world">
            {THEMES.map((t) => (
              <button
                key={t.id}
                type="button"
                role="radio"
                aria-checked={t.id === themeId}
                className={`vx-seal${t.id === themeId ? " is-on" : ""}`}
                onClick={() => pickTheme(t.id)}
                title={t.label}
              >
                <b>{t.kanji}</b>
                <small>{t.label}</small>
              </button>
            ))}
          </div>
        </div>

        <div className="sidebar-bottom">
          <p className="sidebar-vertical" aria-hidden="true">
            知識は時間を超えて生きる。
          </p>
          <div>
            <strong>
              <ShieldCheck size={14} /> Evidence-first AI
            </strong>
            <p>Answers tied to source versions</p>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <div className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> {crumb}
          </div>
          <div className="status-pill">
            <span className="status-dot" />
            API workspace
          </div>
        </div>

        {activePage === "documents" && (
          <>
            <DocumentsPage themeId={themeId} onTheme={pickTheme} />
            <section className="ax-dock">
              <h2>Add to the archive</h2>
              <UploadPanel />
            </section>
          </>
        )}

        {activePage === "arena" && (
          <div className="ax-page">
            <Hero
              arc={`${theme.arc} / Compare`}
              l1="VERSION"
              l2="ARENA"
              sub="Pick a document, pit two versions against each other, and see exactly what changed."
              kanji="闘"
              sfx="ガキーン!"
            />
            <VersionHistoryPanel />
          </div>
        )}

        {activePage === "ask" && (
          <div className="ax-page">
            <Hero
              arc={`${theme.arc} / Ask`}
              l1="ASK THE"
              l2="ARCHIVE"
              sub="Get evidence-backed answers from the document version that was valid on your chosen date."
              kanji="問"
              sfx={theme.sfx}
            />

            <section className="ax-console">
              <span className="ax-tab">YOUR QUESTION</span>
              <form onSubmit={handleSubmit}>
                <label className="field-label ax-sr" htmlFor="question">
                  Your question
                </label>
                <textarea
                  id="question"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Ask a question about your documents..."
                  required
                  minLength={3}
                  rows={3}
                />

                <div className="filters-grid">
                  <div className="field">
                    <label className="field-label" htmlFor="documentKey">
                      Document key <span className="optional">(optional)</span>
                    </label>
                    <input
                      id="documentKey"
                      value={documentKey}
                      onChange={(event) => setDocumentKey(event.target.value)}
                      placeholder="e.g. leave123"
                    />
                  </div>

                  <div className="field">
                    <label className="field-label" htmlFor="asOf">
                      <CalendarDays size={14} />
                      Valid as of
                    </label>
                    <input
                      id="asOf"
                      type="date"
                      value={asOf}
                      max={localDate()}
                      onChange={(event) => setAsOf(event.target.value)}
                      required
                    />
                  </div>

                  <div className="field">
                    <label className="field-label" htmlFor="topK">
                      Sources to retrieve
                    </label>
                    <div className="select-wrap">
                      <select
                        id="topK"
                        value={topK}
                        onChange={(event) => setTopK(event.target.value)}
                      >
                        <option value="3">3 sources</option>
                        <option value="5">5 sources</option>
                        <option value="10">10 sources</option>
                      </select>
                      <ChevronDown size={15} />
                    </div>
                  </div>
                </div>

                <div className="form-footer">
                  <span className="hint">
                    <ShieldCheck size={15} />
                    Retrieved evidence includes version metadata
                  </span>

                  <button className="submit-button" type="submit" disabled={loading}>
                    {loading ? (
                      <>
                        <LoaderCircle className="spin" size={18} />
                        SCANNING…
                      </>
                    ) : (
                      <>
                        <Search size={18} />
                        FIND ANSWER
                      </>
                    )}
                  </button>
                </div>
              </form>
            </section>

            {error && (
              <div className="error-panel" role="alert">
                <strong>Couldn't complete the request</strong>
                <p>{error}</p>
                {error.toLowerCase().includes("fetch") && (
                  <p>
                    Check that FastAPI is running and that the frontend origin is
                    allowed by its CORS settings.
                  </p>
                )}
              </div>
            )}

            {loading && (
              <div className="ax-loading" role="status">
                <i aria-hidden="true" />
                <strong>Scanning the archive…</strong>
              </div>
            )}

            {result && (
              <section className="results-section">
                <div className="ax-section-head">
                  <h2>Answer &amp; evidence</h2>
                  <span className="date-badge">
                    <CalendarDays size={14} />
                    As of {result.as_of}
                  </span>
                </div>

                <article className="ax-dialogue">
                  <span className="ax-name">
                    <Sparkles size={14} /> ARCHIVE
                  </span>
                  {result.answer && <span className="extractive-badge">Extractive</span>}

                  {result.answer ? (
                    <p className="ax-dialogue-text">
                      <span className="ax-sr">{result.answer}</span>
                      <span aria-hidden="true">
                        {typed}
                        {typed.length < result.answer.length && <b className="ax-caret" />}
                      </span>
                    </p>
                  ) : (
                    <p className="ax-dialogue-text">
                      {result.message ?? "No relevant published evidence was found."}
                    </p>
                  )}
                </article>

                <div className="ax-section-head ax-sub">
                  <h3>
                    <BookOpen size={20} /> Source citations
                  </h3>
                  <span>{result.citations.length} found</span>
                </div>

                {result.citations.length === 0 ? (
                  <div className="empty-sources">No citations are available for this query.</div>
                ) : (
                  <div className="citation-list">
                    {result.citations.map((citation, index) => (
                      <article
                        className={`citation-card ax-tone-${index % 3}`}
                        key={`${citation.document_key}-${citation.version}-${citation.chunk_index}`}
                        style={{ animationDelay: `${index * 90}ms` }}
                      >
                        <div className="citation-topline">
                          <span className="source-number">{String(index + 1).padStart(2, "0")}</span>
                          <div className="ax-power-wrap">
                            <span className="similarity">
                              {(citation.similarity * 100).toFixed(1)}% match
                            </span>
                            <div className="ax-power" aria-hidden="true">
                              <i style={{ width: `${Math.max(0, Math.min(100, citation.similarity * 100))}%` }} />
                            </div>
                          </div>
                        </div>

                        <h4>{citation.title}</h4>

                        <div className="metadata-row">
                          <span className="version-badge">{citation.version}</span>
                          <span>{citation.document_key}</span>
                          <span>Chunk {citation.chunk_index}</span>
                        </div>

                        <blockquote>{citation.quoted_text}</blockquote>

                        <div className="citation-footer">
                          <span>Valid from {new Date(citation.effective_from).toLocaleDateString()}</span>
                          <span>
                            {citation.effective_to
                              ? `Until ${new Date(citation.effective_to).toLocaleDateString()}`
                              : "No recorded end date"}
                          </span>
                          <span className="verified">
                            <CheckCircle2 size={14} />
                            Source linked
                          </span>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            )}

            {!result && !error && !loading && (
              <div className="empty-state">
                <div className="empty-state-icon">
                  <FileSearch size={26} />
                </div>
                <h3>Your evidence will appear here</h3>
                <p>Ask a question to retrieve the relevant passage and its historical version.</p>
              </div>
            )}
          </div>
        )}

        <footer className="page-footer">
          VerseRAG <span>✦</span> Version-aware retrieval with source provenance
        </footer>
      </main>
    </div>
  );
}

export default App;