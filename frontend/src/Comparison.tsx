import { lazy, Suspense, useEffect, useState } from "react";
import { api } from "./types";
import { evidenceSummary } from "./evaluationSummary";
import "./evaluation.css";
const CandidateDiff = lazy(() => import("./Diff"));
const endpoint = "/evaluator/comparisons/m02-v1";
const friendly = (s: string) => s.replaceAll("_", " ");
const labels: Record<string, string> = {
  both_passed: "Both passed",
  ordinary_failed: "Ordinary failed",
  additional_independent_failure: "Additional independent failure",
  no_usable_candidate: "No submitted candidate",
  infrastructure_or_provider_failure: "Provider / infrastructure failure",
  awaiting_evaluation: "Awaiting evaluation",
};
type Task = {
  id: string;
  title: string;
  project: string;
  problem: string;
  expected: string;
  base_commit: string;
  issue: string;
  ordinary: string[];
  ordinary_scope: string;
};
type Configuration = {
  id: string;
  label: string;
  model: string;
  source_access: string;
  ordinary_access: string;
  unavailable_metadata: string[];
};
type Coordinate = {
  id: string;
  task_id: string;
  configuration_id: string;
  trial: number;
  order: number;
};
type TrialRow = {
  id: string;
  coordinate: Coordinate;
  outcome: string;
  generation_status: string;
  evaluation_id?: string;
};
type Group = {
  id: string;
  configuration: Configuration;
  attempted: number;
  scheduled: number;
  completed: number;
  awaiting_evaluation: number;
  outcomes: Record<string, number>;
  incremental_numerator: number;
  incremental_denominator: number;
  requests: number;
  reported_total_tokens: number;
  usage_missing_requests: number;
  monetary_cost: null;
  generation_wall_ms: number;
  ordinary_tool_ms: number;
  evaluation_ms: number;
};
type Control = {
  id: string;
  task_id: string;
  kind: string;
  ordinary: string;
  independent: string;
};
type Summary = {
  complete: boolean;
  attempted: number;
  scheduled: number;
  freeze_hash: string;
  groups: Group[];
  trials: TrialRow[];
  tasks: Task[];
  controls: Control[];
  limitations: string[];
  historical_m1: string;
  procedure: {
    body: {
      frozen_at: string;
      budget: Record<string, number>;
      order_seed: number;
      image_id: string;
      configurations: Record<string, Configuration>;
    };
    hash: string;
  };
};
type Phase = {
  status: string;
  outcome?: string;
  exit_code: number;
  duration_ms: number;
  stdout: string;
  stderr: string;
  checks?: {
    name: string;
    status: string;
    expected: unknown;
    observed: unknown;
  }[];
};
type Result = {
  status: string;
  reason?: string;
  ordinary?: Phase | null;
  independent?: Phase | null;
  binding?: unknown;
};
type Candidate = {
  id: string;
  label: string;
  task_id: string;
  kind: string;
  candidate_hash: string;
  patch: string;
  original: Record<string, string>;
  modified: Record<string, string>;
};
type Event = {
  sequence: number;
  at: string;
  kind: string;
  hash: string;
  payload: Record<string, unknown>;
};
type Trial = {
  generation: {
    id: string;
    coordinate: Coordinate;
    generation_status: string;
    requests: number;
    counts: Record<string, number>;
    generation_wall_ms: number;
    ordinary_tool_ms: number;
    error?: unknown;
    provider_calls: unknown[];
    events_head: string;
  };
  events: Event[];
  candidate?: Candidate | null;
  result?: Result | null;
  evaluation_id?: string;
  scoring?: unknown;
};
type ControlDetail = Control & {
  candidate: Candidate;
  result: Result;
  task: Task;
};

function incompleteExplanation(status: string) {
  if (status === "provider_failure" || status === "infrastructure_failure")
    return "A provider or infrastructure failure ended this trial before final submission. No candidate code defect is inferred.";
  if (status === "invalid_output")
    return "The provider response was truncated or unusable. No final candidate was submitted.";
  return `The frozen ${friendly(status)} limit ended generation without a final submission. Intermediate edits and ordinary-tool transcripts remain available; no final score is inferred.`;
}
function seconds(ms: number) {
  return `${(ms / 1000).toFixed(1)} s`;
}

export default function Comparison() {
  const [data, setData] = useState<Summary | null>(null);
  const [trial, setTrial] = useState<Trial | null>(null);
  const [control, setControl] = useState<ControlDetail | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  function query(kind?: string, id?: string) {
    const url = new URL(location.href);
    url.searchParams.delete("trial");
    url.searchParams.delete("control");
    if (kind && id) url.searchParams.set(kind, id);
    window.history.replaceState(null, "", url);
  }
  async function open(kind: "trials" | "controls", id: string) {
    setBusy(true);
    setError("");
    setTrial(null);
    setControl(null);
    query(kind === "trials" ? "trial" : "control", id);
    try {
      if (kind === "trials")
        setTrial(await api<Trial>(`${endpoint}/trials/${id}`));
      else setControl(await api<ControlDetail>(`${endpoint}/controls/${id}`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    api<Summary>(endpoint)
      .then(setData)
      .catch((e) => setError((e as Error).message));
    const params = new URLSearchParams(location.search);
    if (params.get("trial")) void open("trials", params.get("trial")!);
    else if (params.get("control"))
      void open("controls", params.get("control")!);
  }, []);
  const numerator =
    data?.groups.reduce((n, g) => n + g.incremental_numerator, 0) ?? 0;
  const denominator =
    data?.groups.reduce((n, g) => n + g.incremental_denominator, 0) ?? 0;
  const completed = data?.groups.reduce((n, g) => n + g.completed, 0) ?? 0;
  const unusable =
    data?.groups.reduce((n, g) => n + g.outcomes.no_usable_candidate, 0) ?? 0;
  const failures =
    data?.groups.reduce(
      (n, g) => n + g.outcomes.infrastructure_or_provider_failure,
      0,
    ) ?? 0;
  const tie =
    data &&
    data.groups.length > 1 &&
    data.groups.every(
      (g) =>
        JSON.stringify(g.outcomes) === JSON.stringify(data.groups[0].outcomes),
    );
  const shownCandidate = trial?.candidate ?? control?.candidate;
  const shownResult = trial?.result ?? control?.result;
  const shownTask = data?.tasks.find(
    (t) => t.id === (trial?.generation.coordinate.task_id ?? control?.task_id),
  );
  return (
    <main className="evaluation-workspace comparison-workspace">
      <nav className="evaluation-nav">
        <a href="/?workspace=evaluation">← Single patch evaluation</a>
        <span className="local-tag">LOCAL · RETAINED EXPERIMENT</span>
      </nav>
      <header className="evaluation-intro">
        <div className="eyebrow">AGENT EVALUATION · MILESTONE 2</div>
        <h1>Controlled producer comparison</h1>
        <p>
          Four public tasks. Two model/harness configurations. Three fresh
          trials per pairing.
        </p>
      </header>
      {error && (
        <p role="alert" className="run-error">
          {error}
          <button onClick={() => location.reload()}>Reload evidence</button>
        </p>
      )}
      {!data && !error && (
        <p role="status">Validating saved comparison evidence…</p>
      )}
      {data && (
        <>
          <section
            className="evaluation-panel comparison-conclusion"
            aria-label="Comparison conclusion"
          >
            <h2>
              {data.complete
                ? "What independent evaluation added"
                : "Comparison evidence is incomplete"}
            </h2>
            <p className="comparison-primary">
              {!data.complete && "Currently retained (provisional): "}
              <strong>
                {numerator}/{denominator}
              </strong>{" "}
              genuine ordinary-passing candidates failed independent checks.
            </p>
            {denominator === 0 && (
              <p>
                No ordinary-passing final candidates with completed independent
                evaluation are available. An incremental rate is unknown.
              </p>
            )}
            <p>
              <strong>
                {completed}/{data.scheduled}
              </strong>{" "}
              trials completed final evaluation. {unusable} had no submitted
              candidate; {failures} ended in provider or infrastructure failure.
            </p>
            <p>
              All attempted trials: {data.attempted}/{data.scheduled}.
              Completed-trial results cover {completed} submissions. Authored
              controls are excluded.
            </p>
            {tie && (
              <p>
                Observed outcome counts tie. This small case study cannot
                establish equal model capability.
              </p>
            )}
            <p>
              {completed < data.scheduled
                ? "Completion limits make this comparison inconclusive about coding quality. The evidence does not yet support release polish or broader product investment."
                : "These finite results are a small case study, not a population or vendor ranking."}
            </p>
            <p className="comparison-history-note">
              {data.historical_m1}{" "}
              <a href="/?workspace=evaluation">
                Inspect historical M1 evidence
              </a>
              .
            </p>
          </section>
          <div className="evaluation-phases comparison-groups">
            {data.groups.map((g) => (
              <section
                className="evaluation-panel"
                key={g.id}
                aria-label={g.configuration.label}
              >
                <h2>{g.configuration.label}</h2>
                <p>
                  <code>{g.configuration.model}</code>
                </p>
                <p>
                  Completed:{" "}
                  <strong>
                    {g.completed}/{g.attempted}
                  </strong>{" "}
                  attempted trials. Independent additions:{" "}
                  <strong>
                    {g.incremental_numerator}/{g.incremental_denominator}
                  </strong>{" "}
                  ordinary-passing finals.
                </p>
                {g.awaiting_evaluation > 0 && (
                  <p>
                    {g.awaiting_evaluation} submitted trials await final
                    evaluation.
                  </p>
                )}
                <dl className="comparison-counts">
                  {Object.entries(g.outcomes).map(([key, value]) => (
                    <div key={key}>
                      <dt>{labels[key]}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
                <details>
                  <summary>Measured usage and timing</summary>
                  <p>
                    {g.requests} requests ·{" "}
                    {g.reported_total_tokens.toLocaleString()} reported tokens ·
                    usage unknown for {g.usage_missing_requests} requests.
                  </p>
                  <p>
                    Generation wall: {seconds(g.generation_wall_ms)}. Ordinary
                    tools within that wall: {seconds(g.ordinary_tool_ms)}.
                    Separate final evaluation: {seconds(g.evaluation_ms)}.
                  </p>
                  <p>
                    Monetary cost: unknown. Timings include provider load and
                    container overhead. Raw evidence retains CPU/memory samples;
                    short runs may have no sample.
                  </p>
                </details>
              </section>
            ))}
          </div>
          <section className="evaluation-panel" aria-label="Trials by task">
            <div className="evaluation-heading">
              <h2>Every task and trial</h2>
              <label>
                Filter by task{" "}
                <select
                  aria-label="Filter by task"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="">All four tasks</option>
                  {data.tasks.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.project} · {t.title}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="comparison-table-wrap">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>Approved task</th>
                    {data.groups.map((g) => (
                      <th key={g.id}>{g.configuration.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.tasks
                    .filter((t) => !filter || filter === t.id)
                    .map((t) => (
                      <tr key={t.id}>
                        <th>
                          <span>{t.project}</span>
                          <br />
                          {t.title}
                          <details>
                            <summary>Task and provenance</summary>
                            <p>{t.problem}</p>
                            <p>{t.expected}</p>
                            <code>{t.base_commit}</code>
                            <p>{t.ordinary_scope}</p>
                            <code>{t.ordinary.join(" ")}</code>
                            <p>
                              <a href={t.issue}>
                                Upstream issue / correction context ↗
                              </a>
                            </p>
                          </details>
                        </th>
                        {data.groups.map((g) => (
                          <td key={g.id}>
                            {data.trials
                              .filter(
                                (r) =>
                                  r.coordinate.task_id === t.id &&
                                  r.coordinate.configuration_id === g.id,
                              )
                              .sort(
                                (a, b) =>
                                  a.coordinate.trial - b.coordinate.trial,
                              )
                              .map((r) => (
                                <button
                                  key={r.id}
                                  disabled={busy}
                                  className={`comparison-trial ${r.outcome}`}
                                  aria-label={`${t.id} ${g.id} trial ${r.coordinate.trial}`}
                                  onClick={() => void open("trials", r.id)}
                                >
                                  <strong>Trial {r.coordinate.trial}</strong>
                                  <span>
                                    {labels[r.outcome] ?? friendly(r.outcome)}
                                  </span>
                                </button>
                              ))}
                          </td>
                        ))}
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>
          <details className="evaluation-panel">
            <summary>Frozen conditions, budgets, and limitations</summary>
            <p>
              Freeze: <code>{data.freeze_hash}</code>
            </p>
            <p>
              {data.procedure.body.frozen_at} · order seed{" "}
              {data.procedure.body.order_seed}. All generation finished before
              independent scoring. No automatic retries or budget replenishment.
            </p>
            <pre>{JSON.stringify(data.procedure.body.budget, null, 2)}</pre>
            {data.groups.map((g) => (
              <div key={g.id}>
                <h3>{g.configuration.label}</h3>
                <p>{g.configuration.source_access}</p>
                <p>{g.configuration.ordinary_access}</p>
                <p>
                  Unavailable: {g.configuration.unavailable_metadata.join(", ")}
                  .
                </p>
              </div>
            ))}
            <ul>
              {data.limitations.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
            <details>
              <summary>Complete frozen procedure</summary>
              <pre>{JSON.stringify(data.procedure, null, 2)}</pre>
            </details>
          </details>
          <details className="evaluation-panel comparison-controls">
            <summary>
              Authored validation controls · excluded from producer results
            </summary>
            <p>
              Sixteen controls validate the evaluator. They are deliberately
              authored and contribute zero trials to the genuine-producer
              denominators.
            </p>
            <ul className="evaluation-history">
              {data.controls.map((c) => (
                <li key={c.id}>
                  <button
                    disabled={busy}
                    onClick={() => void open("controls", c.id)}
                  >
                    <strong>{c.id}</strong>
                    <span>
                      Ordinary {c.ordinary} · independent {c.independent}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </details>
        </>
      )}
      {busy && <p role="status">Opening the exact retained evidence…</p>}
      {(trial || control) && (
        <section
          id="comparison-detail"
          className="evaluation-panel"
          aria-label="Trial evidence"
        >
          <div className="evaluation-heading">
            <h2>
              {trial
                ? `Trial ${trial.generation.coordinate.trial} · ${shownTask?.title ?? trial.generation.coordinate.task_id}`
                : `Authored control · ${control?.id}`}
            </h2>
            <button
              onClick={() => {
                setTrial(null);
                setControl(null);
                query();
              }}
            >
              Close evidence
            </button>
          </div>
          <p>
            <strong>
              {trial
                ? "Genuine controlled producer trial"
                : "Authored control — excluded from all agent metrics"}
            </strong>
          </p>
          {trial && (
            <>
              <code>{trial.generation.id}</code>
              <p className="comparison-trial-explanation">
                {shownResult
                  ? evidenceSummary(shownTask?.id ?? "", shownResult)
                  : incompleteExplanation(trial.generation.generation_status)}
              </p>
              <p>
                Generation: {friendly(trial.generation.generation_status)} ·{" "}
                {trial.generation.requests} requests ·{" "}
                {trial.generation.counts.revisions} revisions ·{" "}
                {trial.generation.counts.ordinary_runs} ordinary runs.
              </p>
              <p>
                Returned model identities:{" "}
                {[
                  ...new Set(
                    trial.events
                      .filter((e) => e.kind === "response")
                      .map((e) => String(e.payload.model ?? "unknown")),
                  ),
                ].join(", ") || "unknown (no successful response)"}
                .
              </p>
              <p>
                <a
                  href={`/api${endpoint}/trials/${trial.generation.id}/evidence`}
                >
                  Download complete trial evidence
                </a>
                {trial.evaluation_id && (
                  <>
                    {" "}
                    ·{" "}
                    <a
                      href={`/?workspace=evaluation&evaluation=${trial.evaluation_id}`}
                    >
                      Open saved evaluation
                    </a>
                  </>
                )}
              </p>
              <details>
                <summary>
                  Source context, model decisions, and tool transcript ·{" "}
                  {trial.events.length} events
                </summary>
                <p>
                  Events include every request intent, response, invalid action,
                  intermediate edit, ordinary-test transcript, and terminal
                  outcome.
                </p>
                {trial.events.map((e) => (
                  <details key={e.sequence}>
                    <summary>
                      {e.sequence} · {friendly(e.kind)} · {e.at}
                    </summary>
                    <pre>{JSON.stringify(e.payload, null, 2)}</pre>
                    <code>{e.hash}</code>
                  </details>
                ))}
              </details>
              <details>
                <summary>Provider accounting and terminal error</summary>
                <pre>
                  {JSON.stringify(
                    {
                      error: trial.generation.error,
                      calls: trial.generation.provider_calls,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
            </>
          )}
          {control && (
            <p className="comparison-trial-explanation">
              {evidenceSummary(control.task_id, control.result)}
            </p>
          )}
          {shownResult && <CheckEvidence result={shownResult} />}
          {shownCandidate ? (
            <>
              <h3>
                Exact{" "}
                {shownCandidate.kind === "control"
                  ? "control"
                  : "submitted candidate"}{" "}
                patch
              </h3>
              <code>{shownCandidate.candidate_hash}</code>
              <pre>
                {shownCandidate.patch || "Unmodified upstream baseline."}
              </pre>
              {Object.keys(shownCandidate.modified).map((path) => (
                <details key={path}>
                  <summary>Open code comparison · {path}</summary>
                  <Suspense fallback={<p>Opening code comparison…</p>}>
                    <CandidateDiff
                      original={shownCandidate.original[path]}
                      modified={shownCandidate.modified[path]}
                      language="python"
                    />
                  </Suspense>
                </details>
              ))}
              <h3>Reproduce without inference</h3>
              <pre>
                uv run --project backend python -m workbench.evaluator.
                {control &&
                ["more-bucket", "boltons-addlist"].includes(control.task_id)
                  ? "cli"
                  : "experiment_cli reproduce"}{" "}
                {shownCandidate.id}
              </pre>
              <p>
                Uses the approved local Docker image. New execution records its
                actual runtime identity; original identities remain in the saved
                evidence.
              </p>
            </>
          ) : (
            <p>
              No submitted final patch exists. Exact intermediate edits and
              their source hashes are retained in the tool transcript.
            </p>
          )}
        </section>
      )}
      <footer>
        Local approved library environments. In-process Python observations are
        not a complete anti-tampering boundary against malicious candidates. No
        public execution is enabled.
      </footer>
    </main>
  );
}

function CheckEvidence({ result }: { result: Result }) {
  return (
    <div aria-label="Saved check results">
      <div className="evaluation-phases">
        {(["ordinary", "independent"] as const).map((name) => {
          const phase = result[name];
          return (
            <article key={name}>
              <h3>
                {name === "ordinary"
                  ? "Ordinary repository checks"
                  : "Independent behavioral checks"}
              </h3>
              <strong
                className={`evaluation-status ${phase?.outcome ?? phase?.status ?? "pending"}`}
              >
                {phase?.outcome ?? phase?.status ?? "No completed evidence"}
              </strong>
              {phase && (
                <>
                  <p>
                    Exit {phase.exit_code} · {seconds(phase.duration_ms)}
                  </p>
                  <details>
                    <summary>Execution transcript</summary>
                    <pre>{phase.stdout}</pre>
                    {phase.stderr && <pre>{phase.stderr}</pre>}
                  </details>
                </>
              )}
            </article>
          );
        })}
      </div>
      {result.ordinary?.outcome === "failed" && (
        <p>
          Ordinary tests detected this failure too; independent observations add
          behavioral detail.
        </p>
      )}
      {result.ordinary?.outcome === "passed" &&
        result.independent?.outcome === "failed" && (
          <p>
            Ordinary checks passed; the independent observations failed.
            Authored controls remain outside genuine-producer counts.
          </p>
        )}
      <details>
        <summary>Detailed independent observations</summary>
        <pre>{JSON.stringify(result.independent?.checks ?? [], null, 2)}</pre>
      </details>
      <details>
        <summary>Execution identity</summary>
        <pre>{JSON.stringify(result.binding ?? {}, null, 2)}</pre>
      </details>
    </div>
  );
}
