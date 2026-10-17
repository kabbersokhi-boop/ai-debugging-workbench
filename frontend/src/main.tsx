import { StrictMode, useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import * as Tabs from "@radix-ui/react-tabs";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Box,
  Braces,
  Check,
  CheckCheck,
  ChevronRight,
  Circle,
  CircleAlert,
  Code2,
  ExternalLink,
  FileJson,
  Fingerprint,
  FlaskConical,
  FolderGit2,
  GitBranch,
  History,
  Image,
  Layers3,
  LoaderCircle,
  Maximize2,
  Monitor,
  PanelLeftClose,
  Play,
  RotateCcw,
  ShieldCheck,
  Search,
  Square,
  Terminal,
  Workflow,
  X,
} from "lucide-react";
import {
  active,
  api,
  money,
  statusLabel,
  type Bug,
  type Run,
  type RunSummary,
} from "./types";
import "./styles.css";
import { InvestigationWorkspace } from "./Investigation";
import AgentEvaluation from "./Evaluation";
import PatchAudit from "./PatchAudit";
import RecordedExplorer from "./Recorded";
import FullWorkflow from "./Workflow";
import { captureDescription, pricingNote } from "./evidence";

const time = (value: string) =>
  new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
const artifactUrl = (id: string, name: string) =>
  `/api/runs/${id}/artifacts/${name}`;

function App() {
  const [bugs, setBugs] = useState<Bug[]>([]);
  const [bug, setBug] = useState<Bug | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [healthy, setHealthy] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [, setWorkflowStage] = useState("ready");
  const [stages, setStages] = useState({diagnosis:"Needs reproduction", patch:"Needs diagnosis", verification:"Needs candidate"});
  const [workflowSelection, setWorkflowSelection] = useState(0);
  const [workflowRevision, setWorkflowRevision] = useState(0);
  const [tab, setTab] = useState("evidence");
  const [view, setView] = useState("capture");
  const [capture, setCapture] = useState("after.png");
  const [expanded, setExpanded] = useState(false);
  const [sidebar, setSidebar] = useState(false);
  const [liveKey, setLiveKey] = useState(0);
  const selection = useRef(0);
  const idempotency = useRef<string | null>(null);
  const running = active(run?.status);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await api<RunSummary[]>("/runs"));
    } catch {
      /* Preserve current investigation. */
    }
  }, []);

  const connect = useCallback(async () => {
    setError("");
    try {
      const [bugs] = await Promise.all([api<Bug[]>("/bugs"), api("/health")]);
      setBugs(bugs); setBug(bugs[0]);
      setHealthy(true);
      await loadHistory();
    } catch (err) {
      setHealthy(false);
      setError((err as Error).message);
    }
  }, [loadHistory]);

  useEffect(() => {
    void connect();
  }, [connect]);

  useEffect(() => {
    if (!run || !active(run.status)) return;
    const selected = selection.current;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await api<Run>(`/runs/${run.id}`);
        if (disposed || selected !== selection.current) return;
        setRun(next);
        setError("");
        if (active(next.status)) timer = setTimeout(poll, 650);
        else void loadHistory();
      } catch (err) {
        if (!disposed) {
          setError(`Connection interrupted: ${(err as Error).message}`);
          timer = setTimeout(poll, 2000);
        }
      }
    };
    timer = setTimeout(poll, 400);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [run?.id, run?.status, loadHistory]);

  useEffect(() => {
    let disposed = false; let timer: ReturnType<typeof setTimeout>;
    setStages({diagnosis:run?.result ? "Ready to investigate" : "Needs reproduction",patch:"Needs diagnosis",verification:"Needs candidate"});
    if (!run?.result) return;
    const refresh = async () => {
      try {
        const rows = await api<{id:string;status:string}[]>(`/runs/${run.id}/investigations`);
        const investigation = rows[0];
        let patch = "Needs diagnosis", verification = "Needs candidate";
        if (investigation?.status === "completed") {
          const repairs = await api<{status:string;state:{attempt_count:number}}[]>(`/investigations/${investigation.id}/repairs`);
          const repair = repairs[0];
          patch = repair ? repair.state.attempt_count ? "Candidate proposed" : repair.status.replaceAll("_", " ") : "Ready to propose";
          verification = repair ? repair.status === "verified" ? "Named checks passed" : repair.status.replaceAll("_", " ") : "Needs candidate";
        }
        if (!disposed) setStages({diagnosis:investigation ? investigation.status === "completed" ? "Diagnosis proposed" : investigation.status.replaceAll("_", " ") : "Ready to investigate",patch,verification});
      } catch { /* Detailed errors appear in the selected stage. */ }
      if (!disposed) timer = setTimeout(refresh, 2000);
    };
    void refresh();
    return () => {disposed = true; clearTimeout(timer);};
  }, [run?.id, run?.status]);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [expanded]);

  async function start() {
    if (!bug || busy) return;
    setBusy(true);
    setError("");
    idempotency.current ??= crypto.randomUUID();
    try {
      const next = await api<Run>("/runs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotency.current,
        },
        body: JSON.stringify({ bug_id: bug.id }),
      });
      selection.current++;
      setRun(next);
      setTab("evidence");
      setView("capture");
      setCapture("after.png");
      idempotency.current = null;
      await loadHistory();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function selectRun(id: string) {
    setWorkflowSelection(n => n + 1);
    const request = ++selection.current;
    try {
      const next = await api<Run>(`/runs/${id}`);
      if (request !== selection.current) return;
      setRun(next);
      setBug(bugs.find(b => b.id === next.bug_id) ?? null);
      setError("");
      setView("capture");
      setTab("evidence");
      setCapture("after.png");
      setSidebar(false);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function cancel() {
    if (!run) return;
    setBusy(true);
    try {
      setRun(await api<Run>(`/runs/${run.id}/cancel`, { method: "POST" }));
      await loadHistory();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const captures =
    run?.events
      .filter((event) => event.kind === "screenshot")
      .map((event) => String(event.data.artifact)) ?? [];
  const shownCapture = captures.includes(capture) ? capture : captures.at(-1);
  const result = run?.result;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">
        Skip to investigation
      </a>
      <aside className={`sidebar ${sidebar ? "mobile-open" : ""}`}>
        <a href="/" className="brand">
          <div className="brand-icon">
            <Braces size={22} />
          </div>
          <div>
            debugging<span>WORKBENCH</span>
          </div>
        </a>
        <div className="project-switch">
          <div className="project-icon">
            <FolderGit2 size={17} />
          </div>
          <div>
            Retail application<span>Local workspace</span>
          </div>
          <ChevronRight size={14} />
        </div>
        <div className="side-label">WORKSPACE</div>
        <button
          className="side-nav selected"
          onClick={() => {
            setTab("evidence");
            setSidebar(false);
          }}
        >
          <Workflow size={17} />
          Investigations<span className="count">1</span>
        </button>
        <div className="side-label bug-label">SUPPORTED SCENARIOS</div>
        <label className="scenario-label" htmlFor="scenario">Choose a retail defect</label>
        <select id="scenario" value={bug?.id ?? ""} disabled={running || busy} onChange={e => {
          selection.current++; setRun(null); setBug(bugs.find(b => b.id === e.target.value) ?? null);
          idempotency.current = null; setError(""); setTab("evidence");
        }}>{bugs.map(b => <option key={b.id} value={b.id}>{b.title}</option>)}</select>
        <button
          className="bug-select"
          onClick={() => {
            setTab("report");
            setSidebar(false);
          }}
        >
          <span className="bug-marker" />
          <div>
            <span className="mono issue-code">{bug?.id ?? "RETAIL"}</span>
            <strong>{bug?.title ?? "Select a scenario"}</strong>
            <span>Checkout · Pricing</span>
          </div>
          <ChevronRight size={12} />
        </button>
        <div className="side-label history-label">
          RECENT RUNS
          <button onClick={loadHistory} aria-label="Refresh run history">
            <RotateCcw size={12} />
          </button>
        </div>
        <div className="history-list">
          {history.length === 0 ? (
            <p className="history-empty">Your browser runs will appear here.</p>
          ) : (
            history.map((item) => (
              <button
                key={item.id}
                className={`history-item ${run?.id === item.id ? "current" : ""}`}
                onClick={() => selectRun(item.id)}
              >
                <span className={`history-dot ${item.status}`} />
                <div>
                  <span>{statusLabel(item.status)}</span>
                  <small>
                    {time(item.created_at)}{" "}
                    <span className="mono">{item.id.slice(0, 6)}</span>
                  </small>
                </div>
              </button>
            ))
          )}
        </div>
        <div className="sidebar-bottom">
          <div className="foundation-badge">
            <Box size={14} />
            Release candidate<span>M4</span>
          </div>
          <p>
            Live reproduction. Real evidence.
            <br />
            Diagnosis and candidate repair are available in Investigation.
          </p>
          <div className="repo-label">
            <GitBranch size={13} />
            <span>milestone/04</span>
            <span className="private">Private</span>
          </div>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-toggle icon-button"
              onClick={() => setSidebar(!sidebar)}
              aria-label="Toggle navigation"
            >
              <PanelLeftClose size={18} />
            </button>
            <FolderGit2 size={15} />
            <span>retail-application</span>
            <ChevronRight size={13} />
            <strong>Investigations</strong>
          </div>
          <div className="connection">
            <span className={healthy ? "online-dot" : "offline-dot"} />
            {healthy ? "Local services connected" : "Connecting to services"}
            <span className="local-tag">LOCAL</span>
          </div>
        </header>
        <main id="workspace" className="workspace">
          <div className="page-intro">
            <div>
              <div className="eyebrow">
                <span />
                EVIDENCE-FIRST DEBUGGING
              </div>
              <h1>From bug report to browser proof.</h1>
              <p>
                Reproduce the problem. Inspect the evidence. Know what actually
                happened.
              </p>
            </div>
            <a className="secondary-button" href="/?workspace=evaluation">Agent Evaluation</a>
            <a className="secondary-button" href="/recorded/">Explore recorded runs</a>
            <a
              href={bug && bug.id !== "cart-quantity" ? `/scenarios/${bug.id}/retail/` : "/retail/"}
              target="_blank"
              rel="noreferrer"
              className="secondary-button storefront-link"
            >
              <ExternalLink size={14} />
              Explore test app
            </a>
          </div>
          <section className="case-header" aria-label="Selected bug">
            <div className="case-icon">
              <CircleAlert size={21} />
            </div>
            <div className="case-copy">
              <div className="case-meta">
                <span className="mono">{bug?.id ?? "RETAIL"}</span>
                <span className="severity">
                  <span />
                  High priority
                </span>
                <span className="fixture-tag">Synthetic defect</span>
              </div>
              <h2>{bug?.title ?? "Loading the supported defect…"}</h2>
              <p>
                {bug?.summary ??
                  "Checking the API, database, and browser runner."}
              </p>
            </div>
            <div className="run-actions">
              {running ? (
                <button
                  className="secondary-button"
                  disabled={busy}
                  onClick={cancel}
                >
                  <Square size={13} />
                  Cancel run
                </button>
              ) : (
                <button
                  className="primary-button"
                  disabled={!bug || !healthy || busy}
                  onClick={start}
                >
                  {busy ? (
                    <LoaderCircle size={15} className="spin" />
                  ) : (
                    <Play size={15} fill="currentColor" />
                  )}
                  {run ? "Run again" : "Reproduce bug"}
                  <span>↵</span>
                </button>
              )}
              <span className="run-hint">
                <ShieldCheck size={11} />
                Fresh Chromium session · ~5 seconds
              </span>
            </div>
          </section>
          {bug && healthy && <FullWorkflow key={`${bug.id}-${workflowSelection}`} bug={bug} onRun={next => {selection.current++; setRun(next); void loadHistory();}} onStage={stage => {
            setWorkflowStage(stage); setWorkflowRevision(n => n + 1);
            if (["diagnosis", "repair", "finished"].includes(stage)) setTab("investigation");
          }} />}
          <div className="pipeline" aria-label="Latest saved workflow stages">
            <div className="pipeline-step available">
              <span className={`step-number ${running ? "working" : ""}`}>
                {result ? <Check size={13} /> : "01"}
              </span>
              <div>
                <strong>Reproduce</strong>
                <span>
                  {running
                    ? "Browser running"
                    : result
                      ? "Evidence captured"
                      : "Ready to run"}
                </span>
              </div>
              <span className="live-pill">LIVE</span>
            </div>
            <ChevronRight size={15} />
            {[
              {
                name: "Investigate",
                sub: "Repository retrieval",
                icon: Layers3,
              },
              {
                name: "Propose a patch",
                sub: "Bounded code changes",
                icon: Code2,
              },
              {
                name: "Verify the fix",
                sub: "Independent checks",
                icon: ShieldCheck,
              },
            ].map((phase, index) => (
              <div className="future-phase" key={phase.name}>
                <div className={`pipeline-step ${result ? "available" : "future"}`}>
                  <span className="step-number">0{index + 2}</span>
                  <div>
                    <strong>{phase.name}</strong>
                    <span>{[stages.diagnosis, stages.patch, stages.verification][index]}</span>
                  </div>
                </div>
                {index < 2 && <ChevronRight size={15} />}
              </div>
            ))}
          </div>
          {error && (
            <div role="alert" className="error-banner">
              <CircleAlert size={16} />
              <span>{error}</span>
              <button onClick={connect}>Reconnect</button>
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={16} />
              </button>
            </div>
          )}
          <Tabs.Root
            value={tab}
            onValueChange={setTab}
            className="investigation-tabs"
          >
            <div className="tabbar">
              <Tabs.List aria-label="Investigation views">
                <Tabs.Trigger value="evidence">
                  <Monitor size={15} />
                  Browser evidence
                </Tabs.Trigger>
                <Tabs.Trigger value="investigation">
                  <Search size={15} />
                  Investigation
                </Tabs.Trigger>
                <Tabs.Trigger value="report">
                  <FileJson size={15} />
                  Bug report
                </Tabs.Trigger>
                <Tabs.Trigger value="data">
                  <Terminal size={15} />
                  Run details{result && <span className="tab-dot" />}
                </Tabs.Trigger>
              </Tabs.List>
              <span
                className={`run-status ${run?.status ?? ""}`}
                aria-live="polite"
              >
                {running ? (
                  <LoaderCircle size={12} className="spin" />
                ) : result ? (
                  <span className="status-dot" />
                ) : (
                  <Circle size={10} />
                )}
                {statusLabel(run?.status)}
              </span>
            </div>
            <Tabs.Content value="evidence">
              <div className="evidence-layout">
                <div className="evidence-main">
                  <section
                    className={`browser-panel ${expanded ? "expanded" : ""}`}
                    aria-label="Browser evidence viewer"
                  >
                    <div className="browser-toolbar">
                      <div className="window-dots">
                        <i />
                        <i />
                        <i />
                      </div>
                      <div className="browser-address">
                        <ShieldCheck size={11} />
                        <span>fieldwork-supply.local</span>
                        <span className="address-path">/ bag</span>
                      </div>
                      <button
                        className="icon-button"
                        onClick={() => setExpanded(!expanded)}
                        aria-label={
                          expanded ? "Close expanded browser" : "Expand browser"
                        }
                      >
                        {expanded ? <X size={15} /> : <Maximize2 size={14} />}
                      </button>
                    </div>
                    <div className="viewer-controls">
                      <div className="segmented" aria-label="Browser view">
                        <button
                          aria-pressed={view === "capture"}
                          onClick={() => setView("capture")}
                        >
                          <Image size={12} />
                          Captured evidence
                        </button>
                        <button
                          aria-pressed={view === "live"}
                          onClick={() => setView("live")}
                        >
                          <Monitor size={12} />
                          Interactive storefront
                        </button>
                      </div>
                      {view === "capture" && captures.length > 0 && (
                        <div
                          className="capture-toggle"
                          aria-label="Captured state"
                        >
                          <button
                            aria-pressed={shownCapture === "before.png"}
                            disabled={!captures.includes("before.png")}
                            onClick={() => setCapture("before.png")}
                          >
                            Baseline
                          </button>
                          <ArrowRight size={12} />
                          <button
                            aria-pressed={shownCapture === "after.png"}
                            disabled={!captures.includes("after.png")}
                            onClick={() => setCapture("after.png")}
                          >
                            {run?.status === "not_reproduced"
                              ? "After"
                              : "Defect"}
                          </button>
                        </div>
                      )}
                      {view === "live" && (
                        <button
                          className="icon-button"
                          aria-label="Reset storefront"
                          onClick={() => setLiveKey((value) => value + 1)}
                        >
                          <RotateCcw size={14} />
                        </button>
                      )}
                    </div>
                    <div className="browser-viewport">
                      {view === "live" ? (
                        <iframe
                          key={liveKey}
                          title="Interactive synthetic retail storefront"
                          src={bug?.id && bug.id !== "cart-quantity" ? `/scenarios/${bug.id}/retail/` : "/retail/"}
                          sandbox="allow-scripts allow-same-origin"
                        />
                      ) : shownCapture && run ? (
                        <img
                          src={artifactUrl(run.id, shownCapture)}
                          alt={captureDescription(run, shownCapture)}
                        />
                      ) : (
                        <div className="empty-evidence">
                          <div className="empty-browser">
                            <div>
                              <i />
                              <i />
                              <i />
                            </div>
                            <div className="empty-browser-body">
                              <div className="illustration-product">
                                <span />
                              </div>
                              <div className="illustration-lines">
                                <i />
                                <i />
                                <i />
                                <b />
                              </div>
                            </div>
                            <span className="play-orbit">
                              {running ? (
                                <LoaderCircle size={21} className="spin" />
                              ) : (
                                <Monitor size={21} />
                              )}
                            </span>
                          </div>
                          <span className="empty-kicker">
                            A REAL BROWSER. AN OBSERVABLE BUG.
                          </span>
                          <h3>
                            {running
                              ? "Chromium is reproducing the report…"
                              : "Let’s put this bug under the microscope."}
                          </h3>
                          <p>
                            {running
                              ? "Screenshots appear here as each browser step completes."
                              : "Run the reproduction to capture the exact moment checkout totals drift from the cart."}
                          </p>
                          {!running && (
                            <button
                              className="text-button"
                              disabled={!healthy || busy}
                              onClick={start}
                            >
                              Start browser reproduction{" "}
                              <ArrowRight size={14} />
                            </button>
                          )}
                          <div className="empty-facts">
                            <span>
                              <CheckCheck size={13} />
                              Fixed test recipe
                            </span>
                            <span>
                              <Fingerprint size={13} />
                              Fresh session
                            </span>
                            <span>
                              <Image size={13} />
                              Actual screenshots
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="browser-footer">
                      <span>
                        <span
                          className={running ? "pulse-dot" : "neutral-dot"}
                        />
                        {view === "live"
                          ? "Interactive fixture · Separate from the automated session"
                          : shownCapture
                            ? `Captured by Playwright · ${shownCapture === "before.png" ? "Baseline state" : bug?.id === "cart-quantity" ? "Quantity changed to 3" : "Reported scenario action"}`
                            : "Waiting for browser evidence"}
                      </span>
                      <span>
                        {view === "live"
                          ? "Your browser · Responsive viewport"
                          : "Chromium / 1200 × 820"}
                      </span>
                    </div>
                  </section>
                  <section className="assertions-card">
                    <div className="section-heading">
                      <div>
                        <FlaskConical size={16} />
                        <h3>Pricing assertions</h3>
                        <span className="small-tag">
                          Trusted reproduction contract
                        </span>
                      </div>
                      {result && (
                        <span className="assertion-summary">
                          {
                            result.checks.filter((check) => !check.passed)
                              .length
                          }{" "}
                          mismatches found
                        </span>
                      )}
                    </div>
                    {result ? (
                      <div className="assertion-grid">
                        {result.checks.map((check) => (
                          <div
                            key={check.name}
                            className={`assertion ${check.passed ? "pass" : "fail"}`}
                          >
                            <div>
                              <span>{check.name}</span>
                              {check.passed ? (
                                <Check size={13} />
                              ) : (
                                <CircleAlert size={13} />
                              )}
                            </div>
                            <strong>{money(check.observed_cents)}</strong>
                            <span className="expected">
                              Expected {money(check.expected_cents)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="assertion-placeholder">
                        {bug?.id === "cart-quantity" ? <>
                        <div>
                          <span>Subtotal</span>
                          <strong>$192.00</strong>
                        </div>
                        <div>
                          <span>Shipping</span>
                          <strong>Free</strong>
                        </div>
                        <div>
                          <span>Order total</span>
                          <strong>$192.00</strong>
                        </div>
                        <p>
                          Expected after changing quantity to 3.
                          <br />
                          Observed values appear after reproduction.
                        </p>
                        </> : <p>{bug?.expected}<br/>Run this scenario to capture actual quantities, prices and named behavior checks.</p>}
                      </div>
                    )}
                    <div className="contract-note">
                      <ShieldCheck size={13} />
                      <span>{pricingNote(run)}</span>
                    </div>
                  </section>
                </div>
                <aside
                  className="execution-panel"
                  aria-label="Reproduction execution"
                >
                  <div className="execution-heading">
                    <div>
                      <Workflow size={16} />
                      <h3>Execution trail</h3>
                    </div>
                    <span className="small-tag">
                      {run ? `${run.events.length} events` : "LIVE"}
                    </span>
                  </div>
                  <div className="execution-meta">
                    <span>
                      <span className={running ? "pulse-dot" : "neutral-dot"} />
                      {running
                        ? "RUNNING"
                        : run
                          ? "RUN COMPLETE"
                          : "AWAITING RUN"}
                    </span>
                    <span className="mono">
                      {result
                        ? `${(result.duration_ms / 1000).toFixed(1)}s`
                        : run
                          ? run.id.slice(0, 8)
                          : "—"}
                    </span>
                  </div>
                  {run ? (
                    <ol className="timeline" aria-live="polite">
                      {run.events.map((event) => (
                        <li key={event.sequence} className={event.kind}>
                          <span className="timeline-marker">
                            {event.kind === "error" ? (
                              <X size={11} />
                            ) : event.kind === "result" ? (
                              <CircleAlert size={12} />
                            ) : (
                              <Check size={11} />
                            )}
                          </span>
                          <div>
                            <div className="timeline-title">
                              <strong>{event.title}</strong>
                              <time>{time(event.created_at)}</time>
                            </div>
                            <p>{event.detail}</p>
                            {event.kind === "screenshot" && (
                              <button
                                className="event-artifact"
                                onClick={() => {
                                  setCapture(String(event.data.artifact));
                                  setView("capture");
                                }}
                              >
                                <Image size={12} />
                                {String(event.data.artifact)}
                                <ArrowUpRight size={11} />
                              </button>
                            )}
                          </div>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <div className="pending-timeline">
                      {[
                        "Start a fresh browser",
                        "Establish passing baseline",
                        "Follow the reported steps",
                        "Capture the defect",
                        "Compare pricing assertions",
                      ].map((step, index) => (
                        <div key={step}>
                          <span>{index + 1}</span>
                          <div>
                            {step}
                            <small>
                              {
                                [
                                  "Empty cookies and storage",
                                  "Confirm one-item pricing",
                                  "Increase quantity to three",
                                  "Screenshots + Playwright trace",
                                  "Expected versus observed",
                                ][index]
                              }
                            </small>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {running && (
                    <div className="runner-working">
                      <LoaderCircle size={13} className="spin" />
                      Browser is working…
                    </div>
                  )}
                  {run?.error && (
                    <div className="run-error">
                      <CircleAlert size={15} />
                      {run.error}
                    </div>
                  )}
                  {result && (
                    <div className="outcome-note">
                      <span className="eyebrow">REPRODUCTION OUTCOME</span>
                      <h4>{statusLabel(run?.status)}</h4>
                      <p>
                        {result.status === "reproduced"
                          ? "The report matches the observed browser behavior. Evidence is ready to inspect."
                          : "All pricing assertions passed in this run. The reported defect was not observed."}
                      </p>
                      <a href={artifactUrl(run!.id, "result.json")} download>
                        <ArrowDownToLine size={13} />
                        Download result
                      </a>
                    </div>
                  )}
                  <div className="trust-note">
                    <ShieldCheck size={18} />
                    <div>
                      <strong>Evidence, before conclusions.</strong>
                      <p>
                        This trail records the fixed browser recipe. NVIDIA
                        diagnosis has a separate investigation trail.
                      </p>
                    </div>
                  </div>
                </aside>
              </div>
            </Tabs.Content>
            <Tabs.Content value="investigation">
              <InvestigationWorkspace key={`${run?.id}-${workflowRevision}`} run={run} report={bug?.report ?? ""} />
            </Tabs.Content>
            <Tabs.Content value="report">
              <section className="report-panel">
                <div className="section-heading">
                  <div>
                    <FileJson size={18} />
                    <h3>The reported defect</h3>
                  </div>
                  <span className="small-tag">
                    SUPPORTED RECIPE · RETAIL-001
                  </span>
                </div>
                <div className="report-columns">
                  <div>
                    <span className="eyebrow">CUSTOMER REPORT · SYNTHETIC</span>
                    <blockquote>{bug?.report}</blockquote>
                    <div className="expected-box">
                      <CheckCheck size={18} />
                      <div>
                        <strong>Expected behavior</strong>
                        <p>{bug?.expected}</p>
                      </div>
                    </div>
                  </div>
                  <div>
                    <span className="eyebrow">REPRODUCTION PROCEDURE</span>
                    <ol className="report-steps">
                      {bug?.steps.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                    <a
                      className="text-button"
                      href="/retail/"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Try the steps yourself <ArrowUpRight size={14} />
                    </a>
                  </div>
                </div>
                <div className="report-scope">
                  <Box size={15} />
                  Four versioned development scenarios are supported. NVIDIA proposes bounded patches; trusted browser checks independently verify each candidate.
                </div>
              </section>
            </Tabs.Content>
            <Tabs.Content value="data">
              <section className="report-panel">
                <div className="section-heading">
                  <div>
                    <Terminal size={17} />
                    <h3>Run details & artifacts</h3>
                  </div>
                  {run && <span className="mono run-id">{run.id}</span>}
                </div>
                {!run ? (
                  <div className="data-empty">
                    <History size={27} />
                    <h3>No run selected yet</h3>
                    <p>
                      Start a reproduction or select a previous run to inspect
                      its evidence.
                    </p>
                  </div>
                ) : (
                  <>
                    <dl className="details-grid">
                      <div>
                        <dt>Outcome</dt>
                        <dd>{statusLabel(run.status)}</dd>
                      </div>
                      <div>
                        <dt>Started</dt>
                        <dd>{new Date(run.created_at).toLocaleString()}</dd>
                      </div>
                      <div>
                        <dt>Browser</dt>
                        <dd>
                          {result
                            ? `Chromium ${result.browser_version}`
                            : "Pending evidence"}
                        </dd>
                      </div>
                      <div>
                        <dt>Duration</dt>
                        <dd>
                          {result ? `${result.duration_ms} ms` : "Incomplete"}
                        </dd>
                      </div>
                      <div className="hash-detail">
                        <dt>Fixture SHA-256</dt>
                        <dd className="mono">
                          {result?.fixture_sha256 ??
                            "Available after completed reproduction"}
                        </dd>
                      </div>
                    </dl>
                    <div className="artifact-list">
                      {result?.artifacts.map((item) => (
                        <a
                          key={item.name}
                          href={artifactUrl(run.id, item.name)}
                          download
                        >
                          <div className="artifact-icon">
                            {item.media_type === "image/png" ? (
                              <Image size={18} />
                            ) : (
                              <FileJson size={18} />
                            )}
                          </div>
                          <div>
                            <strong>{item.label}</strong>
                            <span className="mono">{item.name}</span>
                          </div>
                          <ArrowDownToLine size={16} />
                        </a>
                      ))}
                    </div>
                    {result && (
                      <p className="trace-help">
                        Open a downloaded trace locally with{" "}
                        <code>
                          uv run playwright show-trace ../artifacts/{run.id}
                          /trace.zip
                        </code>
                        . It contains browser snapshots, network activity, and
                        actions.
                      </p>
                    )}
                    <details className="raw-data">
                      <summary>Inspect raw persisted run JSON</summary>
                      <pre>{JSON.stringify(run, null, 2)}</pre>
                    </details>
                  </>
                )}
              </section>
            </Tabs.Content>
          </Tabs.Root>
          <footer className="workspace-footer">
            <span>
              <Braces size={13} />
              AI debugging workbench<span className="footer-divider">/</span>
              Grounded diagnosis
            </span>
            <span>
              Private live execution · independent finite checks · recorded explorer available.
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}

function Entry() {
  const [mode, setMode] = useState<string | null>(null);
  useEffect(() => { api<{mode: string}>("/mode").then(x => setMode(x.mode)).catch(() => setMode("unavailable")); }, []);
  if (!mode) return <p role="status">Opening the workbench…</p>;
  if (mode === "unavailable") return <main className="workspace"><h1>Workbench unavailable</h1><p role="alert">The application could not confirm its execution mode. No live or recorded run has started.</p><button className="primary-button" onClick={() => location.reload()}>Retry connection</button></main>;
  if (mode === "private_live" && new URLSearchParams(location.search).get("workspace") === "evaluation") return <AgentEvaluation />;
  const recorded = mode === "recorded" || location.pathname.startsWith("/recorded");
  if (new URLSearchParams(location.search).get("workspace") === "debugger") return recorded ? <RecordedExplorer /> : <App />;
  return <PatchAudit recorded={recorded} />;
}
createRoot(document.getElementById("root")!).render(<StrictMode><Entry /></StrictMode>);
