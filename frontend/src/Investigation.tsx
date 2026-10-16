import { useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  CircleAlert,
  LoaderCircle,
  Search,
  ShieldCheck,
  Square,
} from "lucide-react";
import { api, type Run } from "./types";

type Chunk = {
  source_id: string;
  path: string;
  start_line: number;
  end_line: number;
  symbol: string;
  content: string;
};
type Candidate = Chunk & {
  lexical_rank: number | null;
  dense_rank: number | null;
  fusion_score: number;
  rerank_score: number | null;
  selected: boolean;
  selection_reason: string;
};
type Citation = {
  source_id: string;
  path: string;
  start_line: number;
  end_line: number;
  snapshot_id: string;
  source_commit: string;
};
type Investigation = {
  id: string;
  status: string;
  created_at: string;
  report: string;
  error: string | null;
  error_code: string | null;
  snapshot_id: string;
  model_input: Record<string, unknown> | null;
  retrieval: {
    query: string;
    snapshot_id: string;
    source_commit: string;
    candidates: Candidate[];
    supplied_context: Chunk[];
    context_budget: number;
    context_cost: number;
    budget_unit: string;
    latency_ms: number;
    embedding_model: string;
    rerank_model: string;
    rerank_status: string;
  } | null;
  diagnosis: {
    outcome: string;
    diagnosis: string;
    citations: Citation[];
    observations: string[];
    uncertainty: string[];
    next_check: string;
    citation_validity: string;
  } | null;
  events: {
    sequence: number;
    title: string;
    detail: string;
    created_at: string;
  }[];
  provider_calls: {
    workload: string;
    model: string;
    status?: number;
    latency_ms: number;
    usage?: {
      prompt_tokens?: number;
      completion_tokens?: number;
      total_tokens?: number;
    };
  }[];
};
const active = (status?: string) =>
  ["queued", "indexing", "retrieving", "diagnosing"].includes(status ?? "");
const label = (status?: string) =>
  ({
    completed: "Diagnosis proposed",
    insufficient_evidence: "Insufficient evidence",
    provider_error: "Provider error",
    invalid_output: "Invalid model output",
    cancelled: "Cancelled",
    interrupted: "Interrupted",
    error: "Execution error",
  })[status ?? ""] ??
  status ??
  "Ready";

export function InvestigationWorkspace({
  run,
  report,
}: {
  run: Run | null;
  report: string;
}) {
  const [current, setCurrent] = useState<Investigation | null>(null);
  const [history, setHistory] = useState<Investigation[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sourceId, setSourceId] = useState("");
  const [customReport, setCustomReport] = useState(report);
  useEffect(() => {
    setCustomReport(report);
  }, [report]);
  useEffect(() => {
    let disposed = false;
    setCurrent(null);
    setHistory([]);
    setError("");
    setSourceId("");
    if (run)
      void api<Investigation[]>(`/runs/${run.id}/investigations`)
        .then((rows) => {
          if (!disposed) {
            setHistory(rows);
            setCurrent(rows[0] ?? null);
          }
        })
        .catch((err) => {
          if (!disposed) setError((err as Error).message);
        });
    return () => {
      disposed = true;
    };
  }, [run?.id]);
  useEffect(() => {
    if (!current || !active(current.status)) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await api<Investigation>(`/investigations/${current.id}`);
        if (disposed) return;
        setCurrent(next);
        setError("");
        if (active(next.status)) timer = setTimeout(poll, 800);
        else
          setHistory((rows) => [
            next,
            ...rows.filter((row) => row.id !== next.id),
          ]);
      } catch (err) {
        if (!disposed) {
          setError(`Connection interrupted: ${(err as Error).message}`);
          timer = setTimeout(poll, 2000);
        }
      }
    };
    timer = setTimeout(poll, 300);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [current?.id, current?.status]);
  async function start() {
    if (!run) return;
    setBusy(true);
    setError("");
    setSourceId("");
    try {
      const next = await api<Investigation>(`/runs/${run.id}/investigations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report: customReport }),
      });
      setCurrent(next);
      setHistory((rows) => [next, ...rows.filter((row) => row.id !== next.id)]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function cancel() {
    if (!current) return;
    setBusy(true);
    try {
      setCurrent(
        await api<Investigation>(`/investigations/${current.id}/cancel`, {
          method: "POST",
        }),
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const trace = current?.retrieval;
  const diagnosis = current?.diagnosis;
  const selected =
    trace?.candidates.find((chunk) => chunk.source_id === sourceId) ??
    trace?.candidates.find(
      (chunk) => chunk.source_id === diagnosis?.citations[0]?.source_id,
    ) ??
    trace?.candidates[0];
  function cite(id: string) {
    setSourceId(id);
    document
      .getElementById("retrieval-inspector")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  const ready =
    !!run?.result && ["reproduced", "not_reproduced"].includes(run.status);
  return (
    <div className="diagnosis-workspace">
      <section className="report-panel diagnosis-intro">
        <div>
          <span className="eyebrow">MILESTONE 02 · GROUNDED DIAGNOSIS</span>
          <h2>Investigate the evidence.</h2>
          <p>
            A real NVIDIA model reads the report, browser observations, and
            selected repository context. Every source and input is inspectable.
          </p>
        </div>
        {active(current?.status) ? (
          <button className="secondary-button" onClick={cancel} disabled={busy}>
            <Square size={13} />
            Cancel investigation
          </button>
        ) : (
          <button
            className="primary-button"
            onClick={start}
            disabled={!ready || busy}
          >
            {busy ? (
              <LoaderCircle size={14} className="spin" />
            ) : (
              <Search size={14} />
            )}
            Investigate with NVIDIA
            <ArrowRight size={13} />
          </button>
        )}
      </section>
      {!ready && (
        <p className="investigation-notice">
          Complete a browser reproduction before starting an investigation.
        </p>
      )}
      <details className="investigation-report">
        <summary>Report supplied to the investigator</summary>
        <label htmlFor="investigation-report">Supported retail report</label>
        <textarea
          id="investigation-report"
          value={customReport}
          onChange={(event) => setCustomReport(event.target.value)}
          maxLength={4000}
          disabled={active(current?.status)}
        />
      </details>
      {error && (
        <div role="alert" className="error-banner">
          <CircleAlert size={16} />
          {error}
        </div>
      )}
      {history.length > 0 && (
        <div className="investigation-history">
          <label htmlFor="saved-investigations">Saved investigations</label>
          <select
            id="saved-investigations"
            value={current?.id ?? ""}
            onChange={(event) => {
              setCurrent(
                history.find((row) => row.id === event.target.value) ?? null,
              );
              setSourceId("");
            }}
          >
            {history.map((row) => (
              <option key={row.id} value={row.id}>
                {new Date(row.created_at).toLocaleTimeString()} ·{" "}
                {label(row.status)} · {row.id.slice(0, 8)}
              </option>
            ))}
          </select>
          <span className="run-status" aria-live="polite">
            {active(current?.status) && (
              <LoaderCircle size={12} className="spin" />
            )}
            {label(current?.status)}
          </span>
        </div>
      )}
      {current && (
        <section
          className="report-panel investigation-events"
          aria-label="Investigation execution"
        >
          <h3>Investigation events</h3>
          <ol>
            {current.events.map((event) => (
              <li key={event.sequence}>
                <Check size={13} />
                <div>
                  <strong>{event.title}</strong>
                  <p>{event.detail}</p>
                </div>
              </li>
            ))}
          </ol>
          {current.error && (
            <div className="error-banner" role="alert">
              <CircleAlert size={15} />
              <span>{current.error}</span>
              <code>{current.error_code}</code>
            </div>
          )}
        </section>
      )}
      {diagnosis && (
        <section className="report-panel diagnosis-result">
          <span className="eyebrow">
            {diagnosis.outcome === "diagnosis"
              ? "MODEL PROPOSAL"
              : "EVIDENCE GAP"}
          </span>
          <h2>{label(current?.status)}</h2>
          <p className="diagnosis-text">{diagnosis.diagnosis}</p>
          <div
            className="citation-links"
            aria-label="Diagnosis source citations"
          >
            {diagnosis.citations.map((citation, i) => (
              <button key={i} onClick={() => cite(citation.source_id)}>
                <BookOpen size={13} />
                {citation.path}:{citation.start_line}–{citation.end_line}
              </button>
            ))}
          </div>
          <div className="diagnosis-columns">
            <div>
              <h3>Supporting observations</h3>
              <ul>
                {diagnosis.observations.map((observation, i) => (
                  <li key={i}>{observation}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Remaining uncertainty</h3>
              <ul>
                {diagnosis.uncertainty.map((uncertainty, i) => (
                  <li key={i}>{uncertainty}</li>
                ))}
              </ul>
            </div>
          </div>
          <div className="next-check">
            <ShieldCheck size={17} />
            <div>
              <strong>Suggested next check</strong>
              <p>{diagnosis.next_check}</p>
            </div>
          </div>
          <p className="citation-validity">
            {diagnosis.citation_validity} No patch was generated or verified.
          </p>
        </section>
      )}
      {trace && (
        <section
          id="retrieval-inspector"
          className="report-panel retrieval-inspector"
        >
          <div className="section-heading">
            <div>
              <Search size={16} />
              <h3>Retrieval Inspector</h3>
            </div>
            <span className="small-tag">
              {trace.supplied_context.length} SUPPLIED /{" "}
              {trace.candidates.length} CANDIDATES
            </span>
          </div>
          <dl className="snapshot-identity">
            <div>
              <dt>Frozen source commit</dt>
              <dd className="mono">{trace.source_commit}</dd>
            </div>
            <div>
              <dt>Snapshot identity</dt>
              <dd className="mono">{trace.snapshot_id}</dd>
            </div>
            <div>
              <dt>Retrieval pipeline</dt>
              <dd>
                PostgreSQL full-text + NVIDIA embeddings → rank fusion → NVIDIA
                reranker
              </dd>
            </div>
            <div>
              <dt>Context selection</dt>
              <dd>
                {trace.context_cost} / {trace.context_budget}{" "}
                {trace.budget_unit}
              </dd>
            </div>
          </dl>
          <details open className="query-details">
            <summary>Actual retrieval query</summary>
            <pre>{trace.query}</pre>
          </details>
          <div className="retrieval-columns">
            <div className="candidate-list" aria-label="Retrieved candidates">
              {trace.candidates.map((chunk, i) => (
                <button
                  key={chunk.source_id}
                  className={
                    selected?.source_id === chunk.source_id
                      ? "active-candidate"
                      : ""
                  }
                  onClick={() => setSourceId(chunk.source_id)}
                >
                  <div>
                    <strong>
                      #{i + 1} {chunk.symbol.slice(0, 50)}
                    </strong>
                    <span
                      className={
                        chunk.selected ? "supplied-badge" : "candidate-badge"
                      }
                    >
                      {chunk.selected ? "Supplied to model" : "Candidate only"}
                    </span>
                  </div>
                  <span>
                    {chunk.path}:{chunk.start_line}–{chunk.end_line}
                  </span>
                  <small>
                    Lexical {chunk.lexical_rank ?? "—"} · Dense{" "}
                    {chunk.dense_rank ?? "—"} · RRF{" "}
                    {chunk.fusion_score.toFixed(4)} · Rerank{" "}
                    {chunk.rerank_score?.toFixed(3) ?? "—"}
                  </small>
                </button>
              ))}
            </div>
            {selected && (
              <div
                className="source-snippet"
                aria-label="Frozen source snippet"
              >
                <div>
                  <strong>
                    {selected.path}:{selected.start_line}–{selected.end_line}
                  </strong>
                  <span>{selected.selection_reason}</span>
                  <small>
                    Source {selected.source_id} · commit{" "}
                    {trace.source_commit.slice(0, 12)}
                  </small>
                </div>
                <pre>
                  <code>
                    {selected.content
                      .split("\n")
                      .map((line, i) => `${selected.start_line + i}  ${line}`)
                      .join("\n")}
                  </code>
                </pre>
              </div>
            )}
          </div>
          <details className="raw-data">
            <summary>Exact selected context and model inputs</summary>
            <pre>
              {JSON.stringify(
                {
                  supplied_context: trace.supplied_context,
                  model_input: current.model_input,
                },
                null,
                2,
              )}
            </pre>
          </details>
          <details className="raw-data">
            <summary>Provider calls and measured usage</summary>
            <p>
              Token usage is provider-reported where available. Pricing is
              unavailable; no dollar cost is inferred.
            </p>
            <pre>{JSON.stringify(current.provider_calls, null, 2)}</pre>
          </details>
        </section>
      )}
      {!current && (
        <div className="data-empty">
          <Search size={27} />
          <h3>Source-grounded investigation starts here.</h3>
          <p>
            Reproduce the supported report, then ask NVIDIA to investigate.
            Saved context and citations remain tied to their original snapshot.
          </p>
        </div>
      )}
    </div>
  );
}
