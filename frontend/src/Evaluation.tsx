import { lazy, Suspense, useEffect, useState } from "react";
const CandidateDiff = lazy(() => import("./Diff"));
const Comparison = lazy(() => import("./Comparison"));
import { api } from "./types";
import "./evaluation.css";
import { evidenceSummary } from "./evaluationSummary";

type Task = {
  id: string;
  title: string;
  project: string;
  upstream: string;
  issue: string;
  problem: string;
  expected: string;
  base_commit: string;
  spec_hash: string;
  license: string;
  ordinary_scope: string;
};
type Candidate = {
  id: string;
  task_id: string;
  label: string;
  kind: string;
  producer: string;
  provenance: string;
  candidate_hash: string;
  patch: string;
  original: Record<string, string>;
  modified: Record<string, string>;
  actual_response_model?: string;
  token_usage?: unknown;
  generation_record?: unknown;
  experiment_id?: string;
  trial_id?: string;
};
type Check = {
  name: string;
  status: string;
  expected: unknown;
  observed: unknown;
};
type Phase = {
  outcome?: string;
  status: string;
  stdout: string;
  stderr: string;
  exit_code: number;
  duration_ms: number;
  checks?: Check[];
};
type Result = {
  status: string;
  reason?: string;
  ordinary?: Phase;
  independent?: Phase;
  binding?: Record<string, unknown>;
  binding_hash?: string;
};
type Run = {
  id: string;
  task_id: string;
  candidate_id: string;
  status: string;
  created_at: string;
  candidate_hash: string;
  evidence: {
    task: Task;
    candidate: Candidate;
    result?: Result;
    reason?: string;
  };
};
const friendly = (value: string) => value.replaceAll("_", " ");
const format = (value: unknown) => JSON.stringify(value);
function mismatches(check: Check) {
  if (
    check.status === "failed" &&
    check.expected &&
    check.observed &&
    typeof check.expected === "object" &&
    typeof check.observed === "object" &&
    !Array.isArray(check.expected) &&
    !Array.isArray(check.observed)
  ) {
    const wanted = check.expected as Record<string, unknown>,
      actual = check.observed as Record<string, unknown>;
    return Object.keys(wanted)
      .filter((k) => format(wanted[k]) !== format(actual[k]))
      .map(
        (k) =>
          `${friendly(k)}: expected ${format(wanted[k])}; observed ${format(actual[k])}`,
      )
      .join(". ");
  }
  return `Expected ${format(check.expected)}; observed ${format(check.observed)}`;
}

export default function AgentEvaluation() {
  if (new URLSearchParams(location.search).get("comparison") === "m02-v1")
    return (
      <Suspense fallback={<p>Opening controlled comparison…</p>}>
        <Comparison />
      </Suspense>
    );
  return <SingleEvaluation />;
}

function SingleEvaluation() {
  const [tasks, setTasks] = useState<Task[]>([]),
    [candidates, setCandidates] = useState<Candidate[]>([]);
  const [taskId, setTaskId] = useState(""),
    [candidateId, setCandidateId] = useState("");
  const [candidate, setCandidate] = useState<Candidate | null>(null),
    [run, setRun] = useState<Run | null>(null);
  const [history, setHistory] = useState<Run[]>([]),
    [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false),
    [cancelling, setCancelling] = useState(false);
  const task = run?.evidence.task ?? tasks.find((x) => x.id === taskId);
  const shown = run?.evidence.candidate ?? candidate;
  const running = run?.status === "running";
  const refresh = async () => setHistory(await api<Run[]>("/evaluator/runs"));
  async function open(id: string) {
    const value = await api<Run>(`/evaluator/runs/${id}`);
    setTaskId(value.task_id);
    setCandidateId(value.candidate_id);
    setRun(value);
    historyUrl(id);
  }
  function historyUrl(id: string) {
    const url = new URL(location.href);
    url.searchParams.set("evaluation", id);
    window.history.replaceState(null, "", url);
  }
  useEffect(() => {
    let disposed = false;
    Promise.all([
      api<Task[]>("/evaluator/tasks"),
      api<Candidate[]>("/evaluator/candidates"),
    ])
      .then(async ([t, c]) => {
        if (disposed) return;
        setTasks(t);
        setCandidates(c);
        setTaskId(t[0]?.id ?? "");
        setCandidateId(c.find((x) => x.task_id === t[0]?.id)?.id ?? "");
        const id = new URLSearchParams(location.search).get("evaluation");
        if (id) await open(id);
        await refresh();
      })
      .catch((e) => {
        if (!disposed) setError((e as Error).message);
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
    };
  }, []);
  useEffect(() => {
    if (!candidateId) return;
    let disposed = false;
    setCandidate(null);
    api<Candidate>(`/evaluator/candidates/${candidateId}`)
      .then((c) => {
        if (!disposed) setCandidate(c);
      })
      .catch((e) => {
        if (!disposed) setError((e as Error).message);
      });
    return () => {
      disposed = true;
    };
  }, [candidateId]);
  useEffect(() => {
    if (!run || !running) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const value = await api<Run>(`/evaluator/runs/${run.id}`);
        if (disposed) return;
        setRun(value);
        setError("");
        if (value.status === "running") timer = setTimeout(poll, 750);
        else {
          setCancelling(false);
          await refresh();
        }
      } catch (e) {
        if (!disposed) {
          setError(
            `Connection interrupted. Saved evaluation remains available: ${(e as Error).message}`,
          );
          timer = setTimeout(poll, 2000);
        }
      }
    };
    timer = setTimeout(poll, 400);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [run?.id, running]);
  async function start() {
    setBusy(true);
    setError("");
    setCancelling(false);
    try {
      const value = await api<Run>("/evaluator/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidateId }),
      });
      setRun(value);
      historyUrl(value.id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function cancel() {
    setCancelling(true);
    try {
      await api(`/evaluator/runs/${run!.id}/cancel`, { method: "POST" });
    } catch (e) {
      setError((e as Error).message);
      setCancelling(false);
    }
  }
  const result = run?.evidence.result;
  return (
    <main className="evaluation-workspace">
      <nav className="evaluation-nav">
        <a href="/">← Debugging workbench</a>
        <a href="/?workspace=evaluation&comparison=m02-v1">
          Controlled producer comparison →
        </a>
        <span className="local-tag">LOCAL EVALUATOR</span>
      </nav>
      <header className="evaluation-intro">
        <div className="eyebrow">INDEPENDENT CODE VERIFICATION</div>
        <h1>Agent Evaluation</h1>
        <p>Inspect a patch. Execute the checks. Follow the evidence.</p>
      </header>
      {loading && (
        <p role="status">Loading approved tasks and saved evidence…</p>
      )}
      {error && (
        <div role="alert" className="run-error">
          {error}
          <button onClick={() => location.reload()}>Reconnect</button>
        </div>
      )}
      <section
        className="evaluation-selection"
        aria-label="Evaluation selection"
      >
        <label>
          Software task
          <select
            aria-label="Software task"
            value={taskId}
            disabled={running || busy}
            onChange={(e) => {
              const id = e.target.value;
              setTaskId(id);
              setCandidateId(
                candidates.find((x) => x.task_id === id)?.id ?? "",
              );
              setRun(null);
              setError("");
            }}
          >
            {tasks.map((t) => (
              <option key={t.id} value={t.id}>
                {t.project} · {t.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Candidate patch
          <select
            aria-label="Candidate patch"
            value={candidateId}
            disabled={running || busy}
            onChange={(e) => {
              setCandidateId(e.target.value);
              setRun(null);
              setError("");
            }}
          >
            {candidates
              .filter((x) => x.task_id === taskId)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label} ·{" "}
                  {c.kind === "agent" ? "model output" : "authored control"}
                </option>
              ))}
          </select>
        </label>
        <button
          className="primary-button"
          disabled={!shown || running || busy || Boolean(shown.experiment_id)}
          onClick={start}
        >
          {busy ? "Starting…" : "Run evaluation"}
        </button>
        {running && (
          <button
            className="secondary-button"
            disabled={cancelling}
            onClick={cancel}
          >
            {cancelling ? "Stopping…" : "Cancel evaluation"}
          </button>
        )}
      </section>
      {shown?.experiment_id && (
        <p>
          This is a saved controlled trial.{" "}
          <a
            href={`/?workspace=evaluation&comparison=m02-v1&trial=${shown.trial_id}`}
          >
            Open its comparison and generation conditions
          </a>
          .
        </p>
      )}
      {task && (
        <section className="evaluation-panel">
          <div className="evaluation-heading">
            <h2>{task.title}</h2>
            <a href={task.issue} target="_blank" rel="noreferrer">
              Original issue ↗
            </a>
          </div>
          <p>{task.problem}</p>
          <h3>Expected behavior</h3>
          <p>{task.expected}</p>
          <details>
            <summary>Source and task identity</summary>
            <p>
              <a href={task.upstream}>{task.project}</a> · {task.license}
            </p>
            <code>Base: {task.base_commit}</code>
            <br />
            <code>Specification: {task.spec_hash}</code>
            <p>{task.ordinary_scope}</p>
          </details>
        </section>
      )}
      {shown && (
        <section className="evaluation-panel">
          <h2>{shown.label}</h2>
          <p>
            <strong>
              {shown.kind === "agent"
                ? "Genuine model output"
                : "Deliberately authored control"}
            </strong>{" "}
            · {shown.producer}
          </p>
          <p>{shown.provenance}</p>
          <code>Candidate: {shown.candidate_hash}</code>
          {shown.kind === "agent" && !shown.experiment_id && (
            <details>
              <summary>Generation provenance and settings</summary>
              <p>
                Provider response model:{" "}
                {shown.actual_response_model ?? "See generation record"}
              </p>
              <pre>
                {JSON.stringify(shown.generation_record ?? {}, null, 2)}
              </pre>
            </details>
          )}
        </section>
      )}
      {run && (
        <section className="evaluation-panel" aria-label="Evaluation result">
          <div className="evaluation-heading">
            <h2>Evaluation result</h2>
            <strong role="status" className={`evaluation-status ${run.status}`}>
              {friendly(run.status)}
            </strong>
          </div>
          <p>
            {running
              ? "Executing isolated checks. Results will be retained when execution ends."
              : result
                ? evidenceSummary(task?.id ?? "", result)
                : (run.evidence.reason ?? "No completed checks are available.")}
          </p>
          <div className="evaluation-phases">
            <PhaseCard
              title="Ordinary repository checks"
              phase={result?.ordinary}
              description="Existing upstream checks at the pinned base."
            />
            <PhaseCard
              title="Independent behavioral checks"
              phase={result?.independent}
              description="Additional observations compared with the frozen task specification."
            />
          </div>
          {result?.ordinary?.outcome === "failed" && (
            <p className="evaluation-mismatch">
              Ordinary repository checks detected a failure too. The independent
              results provide additional behavioral evidence; they did not
              uniquely discover this failure.
            </p>
          )}
          {result?.ordinary?.outcome === "passed" &&
            result?.independent?.outcome === "failed" && (
              <p className="evaluation-mismatch">
                Ordinary checks passed. Independent behavioral checks found a
                failure.{" "}
                {shown?.kind === "control"
                  ? "This candidate is an authored control; it is not evidence of an AI failure."
                  : "Inspect the observed mismatch below."}
              </p>
            )}
          {result?.independent?.checks && (
            <details className="evaluation-observations">
              <summary>
                Detailed behavioral observations ·{" "}
                {result.independent.checks.length}
              </summary>
              <div className="evaluation-checks">
                {result.independent.checks.map((c) => (
                  <details key={c.name}>
                    <summary>
                      <span className={`evaluation-status ${c.status}`}>
                        {c.status}
                      </span>{" "}
                      {friendly(c.name)}
                    </summary>
                    <p>
                      <code>{mismatches(c)}</code>
                    </p>
                  </details>
                ))}
              </div>
            </details>
          )}
          {!running && (
            <>
              <h3>Reproduce and inspect evidence</h3>
              <p>
                From the repository root, with Docker and the approved evaluator
                image:
              </p>
              <pre>
                uv run --project backend python -m workbench.evaluator.
                {shown?.experiment_id ? "experiment_cli reproduce" : "cli"}{" "}
                {run.candidate_id}
              </pre>
              <p>
                <a href={`/api/evaluator/runs/${run.id}/evidence`}>
                  Download complete evaluation evidence
                </a>{" "}
                ·{" "}
                <button
                  onClick={() =>
                    navigator.clipboard
                      ?.writeText(location.href)
                      .catch(() =>
                        setError(
                          "Could not copy. The saved evaluation URL is in your address bar.",
                        ),
                      )
                  }
                >
                  Copy saved evaluation link
                </button>
              </p>
              <details>
                <summary>Execution identities</summary>
                <pre>{JSON.stringify(result?.binding ?? {}, null, 2)}</pre>
              </details>
            </>
          )}
        </section>
      )}
      {shown && (
        <section className="evaluation-panel">
          <h2>Exact candidate patch</h2>
          {!shown.patch ? (
            <p>The baseline is unmodified upstream source.</p>
          ) : (
            <>
              <pre className="evaluation-patch">{shown.patch}</pre>
              {Object.keys(shown.modified ?? {}).map((path) => (
                <details key={path}>
                  <summary>Open code comparison · {path}</summary>
                  <Suspense fallback={<p>Opening code comparison…</p>}>
                    <CandidateDiff
                      original={shown.original[path]}
                      modified={shown.modified[path]}
                      language="python"
                    />
                  </Suspense>
                </details>
              ))}
            </>
          )}
        </section>
      )}
      <section className="evaluation-panel">
        <div className="evaluation-heading">
          <h2>Evaluation history</h2>
          <button
            onClick={() =>
              refresh().catch((e) => setError((e as Error).message))
            }
          >
            Refresh history
          </button>
        </div>
        {history.length === 0 ? (
          <p>Run an evaluation to retain evidence here.</p>
        ) : (
          <ul className="evaluation-history">
            {history.map((h) => (
              <li key={h.id}>
                <button
                  disabled={running || busy}
                  onClick={() =>
                    open(h.id).catch((e) => setError((e as Error).message))
                  }
                >
                  <strong>{h.candidate_id}</strong>
                  <span>
                    {new Date(h.created_at).toLocaleString()} ·{" "}
                    {friendly(h.status)}
                  </span>
                  <code>{h.candidate_hash.slice(0, 16)}</code>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <footer>
        Finite checks on approved public historical tasks. These results do not
        establish broad agent quality or uncontaminated benchmark performance.
      </footer>
    </main>
  );
}

function PhaseCard({
  title,
  phase,
  description,
}: {
  title: string;
  phase?: Phase;
  description: string;
}) {
  return (
    <article>
      <h3>{title}</h3>
      <p>{description}</p>
      <strong
        className={`evaluation-status ${phase?.outcome ?? phase?.status ?? "pending"}`}
      >
        {friendly(phase?.outcome ?? phase?.status ?? "No completed evidence")}
      </strong>
      {phase && (
        <>
          <p>
            Exit {phase.exit_code} · {(phase.duration_ms / 1000).toFixed(2)}{" "}
            seconds
          </p>
          <details>
            <summary>Execution logs</summary>
            <pre>{phase.stdout}</pre>
            {phase.stderr && <pre>{phase.stderr}</pre>}
          </details>
        </>
      )}
    </article>
  );
}
