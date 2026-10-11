import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
  type ReactNode,
} from "react";
import {
  ArrowDownUp,
  CheckCircle2,
  Clock3,
  Eye,
  FileText,
  Filter,
  Layers3,
  LoaderCircle,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import {
  getDocuments,
  publishVersion,
  type DocumentItem,
} from "../api/client";
import "./documents-anime.css";

type FilterMode = "all" | "published" | "draft";
type SortMode = "recent" | "name" | "versions";

const HOLD_MS = 700;

export const THEMES = [
  { id: "shinobi", kanji: "忍", label: "SHINOBI", arc: "Ninja arc", sfx: "ドン!" },
  { id: "slayer", kanji: "鬼", label: "SLAYER", arc: "Demon arc", sfx: "ズバッ!" },
  { id: "sorcerer", kanji: "呪", label: "SORCERER", arc: "Curse arc", sfx: "ゴゴゴ!" },
  { id: "pirate", kanji: "海", label: "PIRATE", arc: "Sea arc", sfx: "ババーン!" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

const TICKER =
  "SAME KNOWLEDGE ✦ DIFFERENT TIMELINES ✦ FIND WHAT CHANGED ✦ 真実を探せ ✦ ";

function useCountUp(target: number) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / 800, 1);
      setValue(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return value;
}

function Stat({
  icon,
  label,
  value,
  kind,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  kind: string;
}) {
  const shown = useCountUp(value);
  return (
    <div className={`vx-stat vx-stat-${kind}`}>
      <div className="vx-stat-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{String(shown).padStart(2, "0")}</strong>
      </div>
    </div>
  );
}

/** Arcade-style publish: hold the button to charge it, release early to cancel. */
function HoldPublish({
  busy,
  disabled,
  onConfirm,
}: {
  busy: boolean;
  disabled: boolean;
  onConfirm: () => void;
}) {
  const [charging, setCharging] = useState(false);
  const timer = useRef<number | null>(null);

  const cancel = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    setCharging(false);
  }, []);

  const start = () => {
    if (disabled || busy || timer.current !== null) return;
    setCharging(true);
    timer.current = window.setTimeout(() => {
      timer.current = null;
      setCharging(false);
      onConfirm();
    }, HOLD_MS);
  };

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    },
    [],
  );

  return (
    <button
      type="button"
      className={`vx-hold${charging ? " is-charging" : ""}${busy ? " is-busy" : ""}`}
      style={{ "--hold": `${HOLD_MS}ms` } as CSSProperties}
      disabled={disabled || busy}
      onPointerDown={start}
      onPointerUp={cancel}
      onPointerLeave={cancel}
      onPointerCancel={cancel}
      onBlur={cancel}
      onContextMenu={(e) => e.preventDefault()}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !e.repeat) {
          e.preventDefault();
          start();
        }
      }}
      onKeyUp={cancel}
      aria-label="Hold to publish this version"
    >
      <span className="vx-hold-fill" aria-hidden="true" />
      <span className="vx-hold-label">
        {busy ? (
          <LoaderCircle size={14} className="vx-spin" />
        ) : (
          <Sparkles size={14} />
        )}
        {busy ? "SENDING…" : charging ? "CHARGING…" : "HOLD TO PUBLISH"}
      </span>
    </button>
  );
}

export default function DocumentsPage({
  themeId,
}: {
  themeId: ThemeId;
  onTheme: (id: ThemeId) => void;
}) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterMode>("all");
  const [sort, setSort] = useState<SortMode>("recent");
  const [expanded, setExpanded] = useState<string[]>([]);
  const searchRef = useRef<HTMLInputElement>(null);
  const theme = THEMES.find((t) => t.id === themeId) ?? THEMES[2];

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getDocuments();
      setDocuments(result.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load documents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  // "/" jumps to search, like a game menu hotkey.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (e.key === "/" && tag !== "INPUT" && tag !== "SELECT" && tag !== "TEXTAREA") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Toasts fade on their own.
  useEffect(() => {
    if (!notice && !error) return;
    const id = window.setTimeout(() => {
      setNotice("");
      setError("");
    }, 5000);
    return () => window.clearTimeout(id);
  }, [notice, error]);

  async function handlePublish(documentKey: string, versionLabel: string) {
    const actionKey = `${documentKey}:${versionLabel}`;
    setBusy(actionKey);
    setError("");
    setNotice("");
    try {
      await publishVersion(documentKey, versionLabel);
      setNotice(`${documentKey} · ${versionLabel} is now published.`);
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not publish version.");
    } finally {
      setBusy("");
    }
  }

  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();

    const latestOf = (doc: DocumentItem) =>
      doc.versions.reduce(
        (latest, v) => (v.effective_from > latest ? v.effective_from : latest),
        "",
      );

    return documents
      .filter((doc) => {
        const matchesSearch =
          !query ||
          doc.title.toLowerCase().includes(query) ||
          doc.document_key.toLowerCase().includes(query) ||
          doc.versions.some((v) => v.source_filename.toLowerCase().includes(query));
        const matchesFilter =
          filter === "all" || doc.versions.some((v) => v.status === filter);
        return matchesSearch && matchesFilter;
      })
      .sort((a, b) => {
        if (sort === "name") return a.title.localeCompare(b.title);
        if (sort === "versions") return b.versions.length - a.versions.length;
        return latestOf(b).localeCompare(latestOf(a));
      });
  }, [documents, search, filter, sort]);

  const stats = useMemo(() => {
    const versions = documents.flatMap((d) => d.versions);
    const published = versions.filter((v) => v.status === "published").length;
    return {
      documents: documents.length,
      published,
      drafts: versions.filter((v) => v.status === "draft").length,
      total: versions.length,
      rate: versions.length ? Math.round((published / versions.length) * 100) : 0,
    };
  }, [documents]);

  function toggleExpanded(key: string) {
    setExpanded((cur) =>
      cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key],
    );
  }

  function tilt(e: MouseEvent<HTMLElement>) {
    const el = e.currentTarget;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    const y = (e.clientY - r.top) / r.height;
    el.style.setProperty("--mx", `${x * 100}%`);
    el.style.setProperty("--my", `${y * 100}%`);
    el.style.setProperty("--ry", `${(x - 0.5) * 4}deg`);
    el.style.setProperty("--rx", `${(0.5 - y) * 3}deg`);
  }

  function untilt(e: MouseEvent<HTMLElement>) {
    const el = e.currentTarget;
    el.style.setProperty("--ry", "0deg");
    el.style.setProperty("--rx", "0deg");
  }

  return (
    <section className="vx-page" data-theme={themeId}>
      {/* HERO */}
      <header className="vx-hero">
        <div className="vx-hero-rays" aria-hidden="true" />
        <div className="vx-hero-copy">
          <p className="vx-arc">
            <span>{theme.arc}</span> / Documents
          </p>
          <h1 data-t="DOCU">DOCU</h1>
          <h1 style={{ marginBottom: '24px' }}data-t="MENTS" className="vx-h1-second">
            MENTS
          </h1>
          <p className="vx-hero-sub">
            Every document has a history. Open a file, read its timeline, publish the
            version that counts.
          </p>
        
        </div>

        <div className="vx-hero-art" aria-hidden="true">
          <div className="vx-ring vx-ring-a" />
          <div className="vx-ring vx-ring-b" />
          <span key={themeId} className="vx-hero-kanji">
            {theme.kanji}
          </span>
          <span className="vx-sfx">{theme.sfx}</span>
        </div>

        <button
          type="button"
          className="vx-refresh"
          onClick={() => void loadDocuments()}
          disabled={loading}
        >
          {loading ? (
            <LoaderCircle size={17} className="vx-spin" />
          ) : (
            <RefreshCw size={17} />
          )}
          REFRESH
        </button>
      </header>

      <div className="vx-ticker" aria-hidden="true">
        <div className="vx-ticker-track">
          <span>{TICKER.repeat(6)}</span>
          <span>{TICKER.repeat(6)}</span>
        </div>
      </div>

      {/* STATS: cream paper strip with a power gauge */}
      <div className="vx-stats" aria-label="Archive statistics">
        <Stat kind="docs" icon={<FileText size={20} />} label="Documents" value={stats.documents} />
        <Stat kind="pub" icon={<CheckCircle2 size={20} />} label="Published" value={stats.published} />
        <Stat kind="draft" icon={<Clock3 size={20} />} label="Drafts" value={stats.drafts} />
        <Stat kind="all" icon={<Layers3 size={20} />} label="All versions" value={stats.total} />
        <div className="vx-gauge">
          <span>PUBLISH POWER</span>
          <div className="vx-gauge-bar">
            <i style={{ width: `${stats.rate}%` }} />
          </div>
          <strong>{stats.rate}%</strong>
        </div>
      </div>

      {/* SEARCH / CONTROLS */}
      <div className="vx-toolbar">
        <label className="vx-search">
          <Search size={19} />
          <input
            ref={searchRef}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Scan the archive: title, key, filename…"
            aria-label="Search documents"
          />
          {search ? (
            <button
              type="button"
              className="vx-clear"
              onClick={() => setSearch("")}
              aria-label="Clear search"
            >
              <X size={16} />
            </button>
          ) : (
            <kbd>/</kbd>
          )}
          <i className="vx-scan" aria-hidden="true" />
        </label>

        <label className="vx-select">
          <ArrowDownUp size={15} />
          <span className="vx-sr">Sort documents</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as SortMode)}>
            <option value="recent">Newest timeline</option>
            <option value="name">Name A–Z</option>
            <option value="versions">Most versions</option>
          </select>
        </label>

        <label className="vx-select">
          <Filter size={15} />
          <span className="vx-sr">Filter documents</span>
          <select value={filter} onChange={(e) => setFilter(e.target.value as FilterMode)}>
            <option value="all">All documents</option>
            <option value="published">Has published version</option>
            <option value="draft">Has draft version</option>
          </select>
        </label>
      </div>

      {/* TOASTS */}
      {(error || notice) && (
        <div
          className={`vx-toast ${error ? "vx-toast-error" : "vx-toast-ok"}`}
          role={error ? "alert" : "status"}
        >
          <b>{error ? "ミス!" : theme.sfx}</b>
          <span>{error || notice}</span>
          <button
            type="button"
            onClick={() => {
              setError("");
              setNotice("");
            }}
            aria-label="Dismiss"
          >
            <X size={15} />
          </button>
        </div>
      )}

      <div className="vx-section-head">
        <h2>The Collection</h2>
        <span>
          {filteredDocuments.length} RECORD{filteredDocuments.length === 1 ? "" : "S"}
        </span>
      </div>

      {/* LIST */}
      {loading && documents.length === 0 ? (
        <div className="vx-empty">
          <LoaderCircle className="vx-spin" size={28} />
          <strong>Opening the archive…</strong>
          <p>Retrieving your document records.</p>
        </div>
      ) : filteredDocuments.length === 0 ? (
        <div className="vx-empty">
          <FileText size={30} />
          <strong>{documents.length === 0 ? "The archive is empty." : "No records found."}</strong>
          <p>
            {documents.length === 0
              ? "Upload a PDF or TXT file to start your first timeline."
              : "Try another search term or change the filter."}
          </p>
          {search && (
            <button type="button" className="vx-refresh vx-inline" onClick={() => setSearch("")}>
              CLEAR SEARCH
            </button>
          )}
        </div>
      ) : (
        <div className="vx-grid">
          {filteredDocuments.map((doc, index) => {
            const isOpen = expanded.includes(doc.document_key);
            const published = doc.versions.filter((v) => v.status === "published").length;
            const drafts = doc.versions.filter((v) => v.status === "draft").length;
            const ext = (doc.versions[0]?.source_filename.split(".").pop() ?? "FILE")
              .toUpperCase()
              .slice(0, 4);
            const timeline = [...doc.versions].sort((a, b) =>
              b.effective_from.localeCompare(a.effective_from),
            );

            return (
              <article
                key={doc.document_key}
                className={`vx-card vx-tone-${index % 3}${isOpen ? " is-open" : ""}`}
                onMouseMove={tilt}
                onMouseLeave={untilt}
              >
                <div className="vx-card-cover">
                  <span className="vx-card-no">{String(index + 1).padStart(2, "0")}</span>
                  <span className="vx-card-ext">{ext}</span>
                  <span className="vx-card-jp">記録</span>
                </div>

                <div className="vx-card-body">
                  <div className="vx-card-title">
                    <h3>{doc.title}</h3>
                    <span className="vx-key">{doc.document_key}</span>
                  </div>

                  <div className="vx-card-meta">
                    <span className="vx-m-pub">
                      <CheckCircle2 size={13} /> {published} published
                    </span>
                    <span className="vx-m-draft">
                      <Clock3 size={13} /> {drafts} draft{drafts === 1 ? "" : "s"}
                    </span>
                    <span className="vx-m-total">{doc.versions.length}V</span>
                  </div>

                  <button
                    type="button"
                    className="vx-expand"
                    aria-expanded={isOpen}
                    onClick={() => toggleExpanded(doc.document_key)}
                  >
                    {isOpen ? "Close the timeline" : "Open the timeline"}
                    <span className="vx-expand-icon" aria-hidden="true" />
                  </button>
                </div>

                {isOpen && (
                  <ol className="vx-timeline">
                    {timeline.map((v, i) => {
                      const actionKey = `${doc.document_key}:${v.version_label}`;
                      return (
                        <li
                          key={v.version_label}
                          className={`vx-node vx-node-${v.status}`}
                          style={{ "--i": i } as CSSProperties}
                        >
                          <span className="vx-node-dot" aria-hidden="true">
                            {v.status === "published" ? (
                              <CheckCircle2 size={14} />
                            ) : (
                              <Clock3 size={14} />
                            )}
                          </span>
                          <div className="vx-node-info">
                            <div className="vx-node-name">
                              <strong>{v.version_label}</strong>
                              <em>{v.status}</em>
                            </div>
                            <span>
                              {v.effective_from} — {v.effective_to ?? "Present"}
                            </span>
                            <span className="vx-file">
                              <Eye size={11} /> {v.source_filename}
                            </span>
                          </div>
                          {v.status === "draft" && (
                            <HoldPublish
                              busy={busy === actionKey}
                              disabled={busy !== ""}
                              onConfirm={() => void handlePublish(doc.document_key, v.version_label)}
                            />
                          )}
                        </li>
                      );
                    })}
                  </ol>
                )}
              </article>
            );
          })}
        </div>
      )}

      <footer className="vx-footer">VERSIONED KNOWLEDGE. TRACEABLE EVIDENCE. 知識の記録</footer>
    </section>
  );
}