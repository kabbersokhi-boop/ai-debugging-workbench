import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { api } from "./types";
import IndependentPlan, { type IndependentApproval } from "./IndependentPlan";
import RepositoryCampaign from "./RepositoryCampaign";
import { AuditIntro, AuditSteps } from "./AuditGuide";
import GithubPreview from "./GithubPreview";
const Diff = lazy(() => import("./Diff"));
type Source = {
  id: string;
  repository: string;
  base_commit: string;
  git_tree: string;
  source_tree_hash: string;
  file_hashes: Record<string, string>;
  eligible_paths?: string[];
  source_bytes?: number;
  file_count?: number;
  metadata: { license?: { spdx_id: string }; attribution_files: string[] };
  license_texts?: Record<string, string>;
};
type Candidate = {
  id: string;
  snapshot_id: string;
  candidate_hash: string;
  patch: string;
  affected_files: string[];
  original: Record<string, string>;
  modified: Record<string, string>;
  provenance: { author_label: string; limitations: string };
};
type Runtime = { runtime: string; image_id?: string; available: boolean };
type Plan = {
  version: string;
  snapshot_id: string;
  candidate_hash: string;
  runtime: string;
  image_id: string;
  working_directory: string;
  setup: string[][];
  tests: string[];
  test_description: string;
  timeout_seconds: number;
  policy_hash?: string;
};
type Command = {
  phase: string;
  argv: string[];
  status: string;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  duration_ms: number;
  output_truncated: boolean;
};
type Requirement = {
  id: string;
  statement: string;
  expected_behavior: string;
  input_domain: string;
  assumptions: string[];
  provenance: {
    origin: string;
    reference: string;
    excerpt: string;
    justification: string;
  };
};
type Check = {
  id: string;
  requirement_id: string;
  status: string;
  input?: unknown;
  expected?: unknown;
  observed?: unknown;
  error?: string;
};
type Result = {
  version?: string;
  status: string;
  reason?: string;
  ordinary: Result | null;
  independent: { status: string; checks?: Check[]; execution?: Result };
  commands?: Command[];
  duration_ms?: number;
  container_id?: string;
  runtime?: unknown;
};
type Audit = {
  id: string;
  candidate_id: string;
  plan_id: string;
  status: string;
  evidence: {
    snapshot: Source;
    candidate: Candidate;
    plan: Plan;
    result?: Result;
    reason?: string;
    verification?: { id: string; requirements: Requirement[] };
  };
};
type Saved = {
  id: string;
  repository: string;
  status: string;
  created_at: string;
};
const words = (s: string) => s.replaceAll("_", " ");
function link(id: string, campaign: boolean | string = false) {
  const u = new URL(location.href);
  u.search = new URLSearchParams({
    source: "external",
    repositoryAudit: id,
    ...(campaign
      ? { campaign: campaign === true ? "g3" : String(campaign) }
      : {}),
  }).toString();
  history.replaceState(null, "", u);
}
function checked(a: Audit, id?: string, c?: Candidate) {
  if (
    (id && a.id !== id) ||
    a.candidate_id !== a.evidence.candidate.id ||
    (c && a.candidate_id !== c.id) ||
    a.evidence.candidate.candidate_hash !== a.evidence.plan.candidate_hash
  )
    throw Error("Audit identity mismatch; no result displayed.");
  return a;
}

export default function RepositoryAudit() {
  const [repo, setRepo] = useState(""),
    [commit, setCommit] = useState("");
  const [source, setSource] = useState<Source | null>(null),
    [candidate, setCandidate] = useState<Candidate | null>(null);
  const [patch, setPatch] = useState(""),
    [scope, setScope] = useState<string[]>([]);
  const [runtime, setRuntime] = useState("python312"),
    [runtimes, setRuntimes] = useState<Runtime[]>([]);
  const [tests, setTests] = useState('["python", "-m", "pytest", "-q"]'),
    [setup, setSetup] = useState("[]"),
    [cwd, setCwd] = useState("."),
    [description, setDescription] = useState(
      "Selected existing repository tests",
    ),
    [timeout, setTimeoutValue] = useState(45);
  const [plan, setPlan] = useState<{ id: string; plan: Plan } | null>(null),
    [audit, setAudit] = useState<Audit | null>(null);
  const [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [saved, setSaved] = useState<Saved[]>([]);
  const epoch = useRef(0);
  const [retained, setRetained] = useState<boolean | string>(false);
  const [independentEnabled, setIndependentEnabled] = useState(false),
    [independentApproval, setIndependentApproval] =
      useState<IndependentApproval | null>(null),
    [independentBusy, setIndependentBusy] = useState(false);
  const running = audit?.status === "running" || independentBusy,
    result = audit?.evidence.result;
  const layered = result?.version === "repository-independent-result-v1",
    ordinary = layered ? result.ordinary : result;
  const independentResult = result?.independent;
  const selectedRuntime = runtimes.find(
    (r) => r.runtime === runtime && r.available && r.image_id,
  );
  function invalidate(clearCandidate = false) {
    epoch.current++;
    setRetained(false);
    setIndependentApproval(null);
    setAudit(null);
    setPlan(null);
    setConfirmed(false);
    setError("");
    setBusy(false);
    if (clearCandidate) setCandidate(null);
  }
  async function refresh() {
    setSaved(await api<Saved[]>("/repository-audits/runs"));
  }
  async function operation(action: (token: number) => Promise<void>) {
    const token = epoch.current;
    setBusy(true);
    setError("");
    try {
      await action(token);
    } catch (e) {
      if (token === epoch.current) setError(String(e));
    } finally {
      if (token === epoch.current) setBusy(false);
    }
  }
  async function open(id: string, campaign: boolean | string = false) {
    invalidate(true);
    await operation(async (token) => {
      const a = checked(
        await api<Audit>(
          `/repository-audits/${campaign ? `campaigns/${campaign === true ? "g3" : campaign}/runs` : "runs"}/${id}`,
        ),
        id,
      );
      if (token !== epoch.current) return;
      setRetained(campaign);
      setAudit(a);
      setSource(a.evidence.snapshot);
      setRepo(a.evidence.snapshot.repository);
      setCommit(a.evidence.snapshot.base_commit);
      setCandidate(a.evidence.candidate);
      setPlan({ id: a.plan_id, plan: a.evidence.plan });
      setRuntime(a.evidence.plan.runtime);
      setTests(JSON.stringify(a.evidence.plan.tests));
      setSetup(JSON.stringify(a.evidence.plan.setup));
      setCwd(a.evidence.plan.working_directory);
      setDescription(a.evidence.plan.test_description);
      setTimeoutValue(a.evidence.plan.timeout_seconds);
      link(a.id, campaign);
    });
  }
  useEffect(() => {
    let disposed = false;
    const initialSelection = epoch.current;
    (async () => {
      const [rs, hs] = await Promise.all([
        api<Runtime[]>("/repository-audits/runtimes"),
        api<Saved[]>("/repository-audits/runs"),
      ]);
      if (disposed) return;
      setRuntimes(rs);
      setSaved(hs);
      const params = new URLSearchParams(location.search),
        id = params.get("repositoryAudit");
      if (id && initialSelection === epoch.current)
        await open(
          id,
          params.get("campaign") === "g3-node-compatibility"
            ? "g3-node-compatibility"
            : params.get("campaign") === "g3",
        );
    })().catch((e) => {
      if (!disposed) setError(String(e));
    });
    return () => {
      disposed = true;
      epoch.current++;
    };
  }, []);
  useEffect(() => {
    if (!audit || !running) return;
    let disposed = false;
    const id = audit.id,
      c = audit.evidence.candidate,
      token = epoch.current;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const a = checked(
          await api<Audit>(`/repository-audits/runs/${id}`),
          id,
          c,
        );
        if (disposed || token !== epoch.current) return;
        setAudit(a);
        if (a.status !== "running") {
          await refresh();
          return;
        }
      } catch (e) {
        if (!disposed && token === epoch.current) setError(String(e));
      }
      if (!disposed && token === epoch.current) timer = setTimeout(poll, 700);
    }
    timer = setTimeout(poll, 700);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [audit?.id, running]);
  useEffect(() => {
    if (!audit?.id) return;
    const summary = document.getElementById("repository-evidence");
    summary?.focus({ preventScroll: true });
    summary?.scrollIntoView({ block: "start" });
  }, [audit?.id]);
  async function fetchSource() {
    invalidate(true);
    setSource(null);
    setScope([]);
    await operation(async (token) => {
      const s = await api<Source>("/repository-audits/sources", {
        method: "POST",
        body: JSON.stringify({ repository: repo, base_commit: commit }),
      });
      if (token === epoch.current) setSource(s);
    });
  }
  async function importPatch() {
    invalidate(true);
    if (!source) return;
    await operation(async (token) => {
      const c = await api<Candidate>("/repository-audits/candidates", {
        method: "POST",
        body: JSON.stringify({
          snapshot_id: source.id,
          patch,
          approved_paths: scope,
        }),
      });
      if (token === epoch.current) setCandidate(c);
    });
  }
  async function prepare() {
    invalidate();
    if (!source || !candidate) return;
    await operation(async (token) => {
      const image = runtimes.find((r) => r.runtime === runtime && r.available);
      if (!image?.image_id)
        throw Error(
          "Build the selected local runtime before preparing a plan.",
        );
      const p = await api<{ id: string; plan: Plan }>(
        "/repository-audits/plans",
        {
          method: "POST",
          body: JSON.stringify({
            snapshot_id: source.id,
            candidate_hash: candidate.candidate_hash,
            runtime,
            image_id: image.image_id,
            working_directory: cwd,
            setup: JSON.parse(setup),
            tests: JSON.parse(tests),
            test_description: description,
            timeout_seconds: timeout,
          }),
        },
      );
      if (token === epoch.current) setPlan(p);
    });
  }
  async function start() {
    if (
      !plan ||
      !candidate ||
      !confirmed ||
      (independentEnabled && !independentApproval)
    )
      return;
    const c = candidate;
    await operation(async (token) => {
      const a = checked(
        await api<Audit>("/repository-audits/runs", {
          method: "POST",
          body: JSON.stringify({
            candidate_id: c.id,
            plan_id: plan.id,
            approve_exact_plan: true,
            confirm_local_execution: true,
            ...(independentEnabled ? independentApproval : {}),
          }),
        }),
        undefined,
        c,
      );
      if (token !== epoch.current) return;
      setAudit(a);
      setConfirmed(false);
      link(a.id);
      await refresh();
    });
  }
  return (
    <main className="evaluation-workspace patch-audit-workspace">
      <AuditIntro repository />
      <AuditSteps
        step={
          audit ? 5 : confirmed ? 4 : plan ? 3 : candidate ? 2 : source ? 1 : 0
        }
      />
      <div id="audit-content" tabIndex={-1} className="local-boundary">
        <strong>Private local evaluation</strong>
        <p>
          Docker and a trusted local owner are required. Intake is read-only;
          only your exact approval starts restricted execution. Keep this
          privileged development service private.
        </p>
      </div>
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      {audit && (
        <section
          id="repository-evidence"
          tabIndex={-1}
          className="evaluation-panel audit-result"
          aria-label="External audit result"
        >
          <div className="evaluation-heading">
            <h2>{source?.repository}</h2>
            <strong
              role="status"
              className={`evaluation-status ${audit.status}`}
            >
              {words(audit.status)}
            </strong>
          </div>
          <p className="audit-summary">
            {running
              ? "Execution in progress. No completed conclusion yet."
              : ordinary?.status === "tests_failed"
                ? independentResult?.status === "assertions_failed"
                  ? "Existing tests and independent behavioral checks failed. Review both outcomes below."
                  : "Existing tests failed. A passing conclusion is not supported."
                : independentResult?.status === "assertions_failed"
                  ? ordinary?.status === "tests_passed"
                    ? "Selected existing tests passed; an independent behavioral check failed. Review the requirement and observations below."
                    : "An independent behavioral check failed. No complete passing conclusion is available."
                  : audit.status === "completed" &&
                      ordinary?.status === "tests_passed" &&
                      independentResult?.status === "checks_passed"
                    ? "Passed the declared checks. This conclusion applies only to the approved requirements and environment."
                    : audit.status === "tests_passed"
                      ? "The selected existing tests passed. Independent checks not configured."
                      : audit.status === "validation_passed"
                        ? "Checker controls passed. This validation run did not score the candidate."
                        : (result?.reason ??
                          audit.evidence.reason ??
                          `Audit ${words(audit.status)}. No complete passing conclusion is available.`)}
          </p>
          <dl className="audit-facts">
            <div>
              <dt>Repository / source revision</dt>
              <dd>
                {source?.repository}
                <br />
                <code>{source?.base_commit}</code>
              </dd>
            </div>
            <div>
              <dt>Admitted patch identity</dt>
              <dd>
                <code>{candidate?.candidate_hash}</code>
              </dd>
            </div>
            <div>
              <dt>Language / runtime</dt>
              <dd>
                {audit.evidence.plan.runtime === "python312"
                  ? "Python 3.12"
                  : "Node.js 22"}{" "}
                · {audit.evidence.plan.runtime}
              </dd>
            </div>
            <div>
              <dt>Selected existing tests</dt>
              <dd>
                {audit.evidence.plan.test_description}
                <br />
                <code>{JSON.stringify(audit.evidence.plan.tests)}</code>
              </dd>
            </div>
          </dl>
          <div className="evaluation-phases">
            <article>
              <span className="eyebrow">01 · EXISTING TESTS</span>
              <h3>Ordinary repository tests</h3>
              <strong className={`evaluation-status ${ordinary?.status}`}>
                {ordinary ? words(ordinary.status) : "No completed evidence"}
              </strong>
              <p>
                Test counts: unknown. Exact command output is retained below; an
                exit status alone is not a test count.
              </p>
            </article>
            <article>
              <span className="eyebrow">02 · DECLARED REQUIREMENTS</span>
              <h3>Independent behavioral verification</h3>
              <strong
                className={`evaluation-status ${independentResult?.status}`}
              >
                {independentResult &&
                independentResult.status !== "not_configured"
                  ? words(independentResult.status)
                  : "Independent checks not configured"}
              </strong>
              <p>
                Only named, approved requirements are evaluated. A pass does not
                establish complete correctness or security.
              </p>
            </article>
          </div>
          {ordinary?.status === "tests_passed" &&
            independentResult?.status === "assertions_failed" && (
              <p className="evaluation-mismatch">
                This check adds evidence beyond the selected existing tests.
                Multiple failed assertions can describe the same defect; they
                are not a count of unique bugs.
              </p>
            )}
          {retained && (
            <p>
              {retained === "g3-node-compatibility"
                ? "Saved G3 Node compatibility addendum evidence"
                : "Saved G3 campaign evidence"}{" "}
              · no new execution on reopening.
            </p>
          )}
          <p>
            <a
              href={
                retained
                  ? `/api/repository-audits/campaigns/${retained === true ? "g3" : retained}/runs/${audit.id}`
                  : `/api/repository-audits/runs/${audit.id}/evidence`
              }
              download
            >
              Download repository evidence
            </a>
            {" · "}
            <button
              onClick={() =>
                navigator.clipboard
                  .writeText(location.href)
                  .catch((e) => setError(String(e)))
              }
            >
              Copy saved audit link
            </button>
          </p>
          <details>
            <summary>Candidate provenance and exact admitted patch</summary>
            <pre>{JSON.stringify(candidate, null, 2)}</pre>
          </details>
          {running && (
            <button
              onClick={() =>
                api(`/repository-audits/runs/${audit.id}/cancel`, {
                  method: "POST",
                }).catch((e) => setError(String(e)))
              }
            >
              Cancel repository audit
            </button>
          )}
          {[
            ...(ordinary?.commands ?? []),
            ...(independentResult?.execution?.commands ?? []),
          ].map((c, i) => (
            <details key={i}>
              <summary>
                {c.phase}:{" "}
                {c.exit_code === null ? words(c.status) : `exit ${c.exit_code}`}{" "}
                · {JSON.stringify(c.argv)}
              </summary>
              <p>
                {(c.duration_ms / 1000).toFixed(2)} seconds
                {c.output_truncated &&
                  " · output limit reached; retained output is incomplete"}
              </p>
              <pre>{c.stdout || "No stdout"}</pre>
              <pre>{c.stderr || "No stderr"}</pre>
            </details>
          ))}
          {independentResult?.checks && (
            <section aria-label="Independent assertion observations">
              <h3>Expected versus observed</h3>
              {independentResult.checks.map((c) => {
                const requirement =
                  audit.evidence.verification?.requirements.find(
                    (r) => r.id === c.requirement_id,
                  );
                return (
                  <article key={c.id}>
                    <h4>
                      {c.id} · {words(c.status)}
                    </h4>
                    {requirement && (
                      <p>
                        <strong>{requirement.statement}</strong>
                      </p>
                    )}
                    <p>
                      Requirement <code>{c.requirement_id}</code>
                    </p>
                    <dl className="observation-pair">
                      <div>
                        <dt>Expected</dt>
                        <dd>
                          <pre>{JSON.stringify(c.expected, null, 2)}</pre>
                        </dd>
                      </div>
                      <div>
                        <dt>Observed</dt>
                        <dd>
                          <pre>
                            {JSON.stringify(c.observed, null, 2) ??
                              "No valid observation"}
                          </pre>
                        </dd>
                      </div>
                    </dl>
                    <details>
                      <summary>Input and observation details</summary>
                      <pre>
                        {JSON.stringify(
                          { input: c.input, error: c.error },
                          null,
                          2,
                        )}
                      </pre>
                    </details>
                    {requirement && (
                      <details>
                        <summary>
                          Requirement provenance and assumptions
                        </summary>
                        <p>
                          Expected behavior: {requirement.expected_behavior}
                        </p>
                        <p>
                          Source ({words(requirement.provenance.origin)}):{" "}
                          {requirement.provenance.reference}
                        </p>
                        <blockquote>
                          {requirement.provenance.excerpt}
                        </blockquote>
                        <p>{requirement.provenance.justification}</p>
                        <p>Supported domain: {requirement.input_domain}</p>
                        <pre>
                          {JSON.stringify(requirement.assumptions, null, 2)}
                        </pre>
                      </details>
                    )}
                  </article>
                );
              })}
            </section>
          )}
          <details>
            <summary>
              Approved requirement provenance and independent evidence
            </summary>
            <pre>{JSON.stringify(audit.evidence, null, 2)}</pre>
          </details>
          <details>
            <summary>Source, plan, runtime and execution identities</summary>
            <pre>
              {JSON.stringify(
                {
                  audit_id: audit.id,
                  candidate_id: audit.candidate_id,
                  plan_id: audit.plan_id,
                  source_tree_hash: source?.source_tree_hash,
                  runtime: ordinary?.runtime,
                  container_id: ordinary?.container_id,
                  independent_runtime: independentResult?.execution?.runtime,
                  independent_container_id:
                    independentResult?.execution?.container_id,
                  verification_id: audit.evidence.verification?.id,
                },
                null,
                2,
              )}
            </pre>
          </details>
        </section>
      )}
      <section id="repository-source" className="evaluation-panel audit-import">
        <h2>1. Pin the upstream source</h2>
        <p>
          Public GitHub repositories only. Supply a full 40-character commit
          SHA. Intake reads source bytes and does not execute project code.
        </p>
        <GithubPreview key={repo + ":" + commit} disabled={running || busy} />
        <h3>Manual immutable source intake</h3>
        <label>
          GitHub owner/repository
          <input
            aria-label="GitHub owner/repository"
            placeholder="owner/repository"
            value={repo}
            disabled={running || busy}
            onChange={(e) => {
              invalidate(true);
              setSource(null);
              setRepo(e.target.value);
            }}
          />
        </label>
        <label>
          Immutable base commit
          <input
            aria-label="Immutable base commit"
            value={commit}
            placeholder="Full 40-character SHA"
            disabled={running || busy}
            onChange={(e) => {
              invalidate(true);
              setSource(null);
              setCommit(e.target.value);
            }}
          />
        </label>
        <button
          className="primary-button"
          disabled={!repo || !/^[a-f0-9]{40}$/.test(commit) || busy || running}
          onClick={fetchSource}
        >
          {busy && !source
            ? "Fetching bounded source…"
            : "Fetch source for review"}
        </button>
        {source && (
          <div>
            <p>
              <strong>{source.repository}</strong> ·{" "}
              {source.metadata.license?.spdx_id ?? "License not identified"}
            </p>
            <p>
              Base <code>{source.base_commit}</code>
            </p>
            <p>
              Git tree <code>{source.git_tree}</code>
            </p>
            <p>
              {source.file_count ?? Object.keys(source.file_hashes).length}{" "}
              files
              {source.source_bytes !== undefined &&
                ` · ${source.source_bytes.toLocaleString()} source bytes`}
            </p>
            <details>
              <summary>Source identities and upstream attribution</summary>
              <pre>{JSON.stringify(source, null, 2)}</pre>
            </details>
          </div>
        )}
      </section>
      {source && (
        <section
          id="repository-patch"
          className="evaluation-panel audit-import"
        >
          <h2>2. Import a production patch</h2>
          <p>
            Exact UTF-8/LF unified diff, up to 64 KiB and four existing files.
            Explicitly select the permitted scope. Changes to tests, setup,
            configuration, file modes and new/deleted files are unsupported.
          </p>
          <label>
            Approved production file scope
            <select
              aria-label="Approved production file scope"
              multiple
              size={Math.min(8, source.eligible_paths?.length ?? 4)}
              value={scope}
              disabled={running || busy}
              onChange={(e) => {
                invalidate(true);
                setScope(Array.from(e.target.selectedOptions, (o) => o.value));
              }}
            >
              {(source.eligible_paths ?? Object.keys(source.file_hashes)).map(
                (p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ),
              )}
            </select>
          </label>
          <label>
            External patch file
            <input
              aria-label="External patch file"
              type="file"
              accept=".patch,.diff"
              disabled={running || busy}
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                invalidate(true);
                const token = epoch.current;
                try {
                  if (f.size > 65536) throw Error("Patch exceeds 64 KiB");
                  const value = new TextDecoder("utf-8", {
                    fatal: true,
                    ignoreBOM: true,
                  }).decode(await f.arrayBuffer());
                  if (token === epoch.current) setPatch(value);
                } catch (e) {
                  if (token === epoch.current) setError(String(e));
                }
              }}
            />
          </label>
          <label>
            External unified diff
            <textarea
              aria-label="External unified diff"
              rows={8}
              value={patch}
              disabled={running || busy}
              onChange={(e) => {
                invalidate(true);
                setPatch(e.target.value);
              }}
            />
          </label>
          <button
            className="primary-button"
            disabled={!patch || !scope.length || running || busy}
            onClick={importPatch}
          >
            Admit patch for review
          </button>
          {candidate && (
            <section aria-label="External candidate review">
              <h3>Exact submitted patch</h3>
              <p>{candidate.provenance.limitations}</p>
              <p>Affected files: {candidate.affected_files.join(", ")}</p>
              <pre>{candidate.patch}</pre>
              {candidate.affected_files.map((p) => (
                <details key={p}>
                  <summary>Compare {p}</summary>
                  <Suspense fallback={<p>Opening diff…</p>}>
                    <Diff
                      original={candidate.original[p]}
                      modified={candidate.modified[p]}
                      language={
                        runtime === "python312" ? "python" : "javascript"
                      }
                    />
                  </Suspense>
                </details>
              ))}
              <a
                href={`/api/repository-audits/candidates/${candidate.id}/patch`}
                download
              >
                Download exact repository patch
              </a>
            </section>
          )}
        </section>
      )}
      {candidate && (
        <section
          id="repository-tests"
          className="evaluation-panel audit-import"
        >
          <h2>3. Review an ordinary-test plan</h2>
          <p>
            Commands below are your instructions. README files, package scripts
            and inferred conventions are untrusted. All dependency setup and
            lifecycle hooks run inside the same restricted environment. Network
            access is disabled; unavailable dependencies fail the audit.
          </p>
          <label>
            Runtime preset
            <select
              aria-label="Runtime preset"
              value={runtime}
              disabled={running || busy}
              onChange={(e) => {
                invalidate();
                setRuntime(e.target.value);
                setTests(
                  e.target.value === "python312"
                    ? '["python", "-m", "pytest", "-q"]'
                    : '["node", "--test"]',
                );
              }}
            >
              <option value="python312">Python 3.12 · pytest 8.3.5</option>
              <option value="node22">
                Node 22 · built-in tests / pinned Mocha
              </option>
              <option value="node22_compat">
                Node 22 · pinned Mocha + read-only array-flatten 1.0.0
              </option>
            </select>
          </label>
          {runtime === "node22" && (
            <p>
              For Mocha suites, use{" "}
              <code>
                ["node", "/opt/test-tools/node_modules/mocha/bin/mocha.js",
                "test/index.js"]
              </code>
              . The preset includes Mocha 11.7.5; other project dependencies
              must be available offline.
            </p>
          )}
          <p>
            Source stays read-only during setup and testing. Use{" "}
            <code>/work</code> for scratch output and <code>/work/deps</code>{" "}
            for offline Python packages. Projects that must rewrite their source
            tree need a different preparation plan and are unsupported in G1.
          </p>
          <label>
            Working directory
            <input
              aria-label="Working directory"
              value={cwd}
              disabled={running || busy}
              onChange={(e) => {
                invalidate();
                setCwd(e.target.value);
              }}
            />
          </label>
          <label>
            Dependency setup argument vectors (JSON)
            <textarea
              aria-label="Dependency setup argument vectors"
              rows={2}
              value={setup}
              disabled={running || busy}
              onChange={(e) => {
                invalidate();
                setSetup(e.target.value);
              }}
            />
          </label>
          <label>
            Test command arguments (JSON)
            <textarea
              aria-label="Test command arguments"
              rows={2}
              value={tests}
              disabled={running || busy}
              onChange={(e) => {
                invalidate();
                setTests(e.target.value);
              }}
            />
          </label>
          <label>
            Selected test scope
            <input
              aria-label="Selected test scope"
              value={description}
              disabled={running || busy}
              onChange={(e) => {
                invalidate();
                setDescription(e.target.value);
              }}
            />
          </label>
          <label>
            Total command timeout (seconds)
            <input
              aria-label="Total command timeout"
              type="number"
              min={1}
              max={120}
              value={timeout}
              disabled={running || busy}
              onChange={(e) => {
                invalidate();
                setTimeoutValue(Number(e.target.value));
              }}
            />
          </label>
          {!runtimes.length && (
            <p role="status">Loading local runtime identities…</p>
          )}
          {runtimes.length > 0 && !selectedRuntime && (
            <p>
              The selected runtime is unavailable. Build the local runtime image
              and reload before preparing a plan.
            </p>
          )}
          <button
            className="primary-button"
            disabled={running || busy || !selectedRuntime}
            onClick={prepare}
          >
            Prepare exact plan for approval
          </button>
          {plan && (
            <>
              <div id="repository-requirements" className="requirement-choice">
                <h3>4. Define the independent scope</h3>
                <p>
                  What behavior should this patch preserve, and what trustworthy
                  source justifies it? If you have no independent specification,
                  continue with existing tests only.
                </p>
                <label>
                  <input
                    type="checkbox"
                    aria-label="Add independent verification"
                    checked={independentEnabled}
                    disabled={running || busy}
                    onChange={(e) => {
                      setIndependentEnabled(e.target.checked);
                      setIndependentApproval(null);
                      setConfirmed(false);
                    }}
                  />
                  Add independently specified behavioral verification
                </label>
                {!independentEnabled && (
                  <p className="evaluation-mismatch">
                    Independent checks not configured. An ordinary-test pass
                    will not be presented as independent verification.
                  </p>
                )}
              </div>
              {independentEnabled && (
                <IndependentPlan
                  key={candidate.id + plan.id}
                  snapshotId={source!.id}
                  candidateId={candidate.id}
                  candidateHash={candidate.candidate_hash}
                  ordinaryPlanId={plan.id}
                  runtime={plan.plan.runtime}
                  imageId={plan.plan.image_id}
                  disabled={busy || audit?.status === "running"}
                  onChange={(value) => {
                    setIndependentApproval(value);
                    setConfirmed(false);
                    if (!value) setAudit(null);
                  }}
                  onBusy={setIndependentBusy}
                />
              )}
              <div id="repository-approval" className="audit-confirm">
                <h3>5. Approve local execution</h3>
                <p>
                  Working directory: <code>{plan.plan.working_directory}</code>
                </p>
                <p>
                  Offline setup commands:{" "}
                  <code>{JSON.stringify(plan.plan.setup)}</code>
                </p>
                <dl className="audit-facts">
                  <div>
                    <dt>Approved command</dt>
                    <dd>
                      <code>{JSON.stringify(plan.plan.tests)}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>Execution budget</dt>
                    <dd>
                      {plan.plan.timeout_seconds}s · {plan.plan.runtime}
                    </dd>
                  </div>
                  <div>
                    <dt>Independent scope</dt>
                    <dd>
                      {independentEnabled
                        ? independentApproval
                          ? "Validated and explicitly approved"
                          : "Awaiting validation and approval"
                        : "Not configured"}
                    </dd>
                  </div>
                </dl>
                <details>
                  <summary>Exact ordinary plan and runtime identity</summary>
                  <pre>{JSON.stringify(plan.plan, null, 2)}</pre>
                </details>
                <p>
                  No network, credentials, Docker socket or unrelated host
                  mounts. Non-root execution, read-only inputs, 1 CPU, 512 MiB
                  memory, 64 processes and bounded temporary storage/output.
                  Containers share the host kernel and are not a complete
                  defense against malicious code. Use an isolated disposable VM
                  for adversarial repositories. Keep this service private.
                </p>
                <label>
                  <input
                    type="checkbox"
                    checked={confirmed}
                    disabled={running || busy}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  I reviewed this exact source, patch and plan, and approve
                  local execution.
                </label>
                <button
                  className="primary-button"
                  disabled={
                    !confirmed ||
                    running ||
                    busy ||
                    (independentEnabled && !independentApproval)
                  }
                  onClick={start}
                >
                  {independentEnabled
                    ? "Run ordinary and independent checks"
                    : "Run approved repository tests"}
                </button>
              </div>
            </>
          )}
        </section>
      )}
      <section id="repository-history" className="evaluation-panel">
        <h2>Saved repository audit history</h2>
        <button
          disabled={busy}
          onClick={() => refresh().catch((e) => setError(String(e)))}
        >
          Refresh repository history
        </button>
        <p>
          Reopen an audit to inspect the saved result; reopening never
          re-executes it.
        </p>
        {!saved.length && (
          <p>
            No saved repository audits yet. Admit a patch and approve a plan to
            create one.
          </p>
        )}
        <ul className="evaluation-history">
          {saved.slice(0, historyExpanded ? saved.length : 10).map((h) => (
            <li key={h.id}>
              <button disabled={running || busy} onClick={() => open(h.id)}>
                {h.repository} · {words(h.status)} ·{" "}
                {new Date(h.created_at).toLocaleString()}
                <br />
                <code>{h.id}</code>
              </button>
            </li>
          ))}
        </ul>
        {saved.length > 10 && (
          <button onClick={() => setHistoryExpanded(!historyExpanded)}>
            {historyExpanded ? "Show recent audits" : "Show all saved audits"}
          </button>
        )}
      </section>
      <section id="research-evidence" aria-label="Historical research evidence">
        <h2>Inspect the research behind the tool</h2>
        <p>
          Historical developer patches, authored controls and compatibility
          evidence remain separate. The G3 campaign found zero additional
          independent defects; it does not estimate broad detection accuracy.
        </p>{" "}
        <RepositoryCampaign
          disabled={busy || running}
          onSelect={() => invalidate(true)}
          onOpen={(id) => open(id, true)}
        />
        <RepositoryCampaign
          campaignId="g3-node-compatibility"
          selectedRunId={
            retained === "g3-node-compatibility" ? audit?.id : undefined
          }
          disabled={busy || running}
          onSelect={() => invalidate(true)}
          onOpen={(id) => open(id, "g3-node-compatibility")}
        />
      </section>
    </main>
  );
}
