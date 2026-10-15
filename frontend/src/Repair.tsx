import { lazy, Suspense, useEffect, useState } from "react";
import { ArrowRight, Download, LoaderCircle, ShieldCheck, Square, Wrench } from "lucide-react";
import { api } from "./types";
import type { Investigation } from "./Investigation";

const CandidateDiff = lazy(() => import("./Diff"));
type Verification = {
  candidate_hash: string; verifier_version: string; status: string; scope: string;
  checks: { name: string; passed: boolean; quantity: number; expected: Record<string, string>;
    observed: Record<string, string> }[];
};
type Attempt = {
  number: number; status: string; rejection: string | null;
  proposal: { explanation: string };
  candidate: { candidate_hash: string; patch_hash: string; original: string; content: string; diff: string } | null;
  verification: Verification | null;
};
type Repair = {
  id: string; status: string; created_at: string; error: string | null; error_code: string | null;
  state: { attempt_count: number; request_remaining: number; output_budget_remaining: number;
    snapshot_id: string; deadline: string; candidate_hash: string | null;
    attempts: Attempt[]; original_verification: Verification | null;
    model_records: unknown[]; mcp_events: unknown[]; source_reads: unknown[]; provider_calls: unknown[];
  };
  events: { sequence: number; title: string; detail: string }[];
};
const active = (s?: string) => ["queued", "inspecting", "proposing", "validating", "candidate_created", "verifying"].includes(s ?? "");
const label = (s?: string) => ({ verified: "Verified for the supported checks", verification_failed: "Verification failed",
  patch_rejected: "Patch rejected", invalid_output: "Invalid model output", candidate_created: "Candidate created",
  insufficient_evidence: "Insufficient evidence", provider_error: "Provider error", error: "Execution error",
  cancelled: "Cancelled", interrupted: "Interrupted", verifying: "Verification running", proposing: "Patch proposal requested" })[s ?? ""] ?? s ?? "Ready";

export function RepairWorkspace({ investigation }: { investigation: Investigation }) {
  const [rows, setRows] = useState<Repair[]>([]);
  const [current, setCurrent] = useState<Repair | null>(null);
  const [selected, setSelected] = useState(0);
  const [preview, setPreview] = useState("");
  const [reset, setReset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let disposed = false;
    setCurrent(null); setRows([]); setPreview(""); setSelected(0); setError("");
    api<Repair[]>(`/investigations/${investigation.id}/repairs`).then((next) => {
      if (!disposed) { setRows(next); setCurrent(next[0] ?? null); }
    }).catch((e) => { if (!disposed) setError((e as Error).message); });
    return () => { disposed = true; };
  }, [investigation.id]);
  useEffect(() => {
    if (!current || !active(current.status)) return;
    let disposed = false; let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const row = await api<Repair>(`/repairs/${current.id}`);
        if (disposed) return;
        setCurrent(row); setRows((prior) => [row, ...prior.filter((x) => x.id !== row.id)]);
        if (active(row.status)) timer = setTimeout(poll, 800);
      } catch (e) { if (!disposed) { setError((e as Error).message); timer = setTimeout(poll, 2000); } }
    };
    timer = setTimeout(poll, 350);
    return () => { disposed = true; clearTimeout(timer); };
  }, [current?.id, current?.status]);
  const attempt = current?.state.attempts.find((a) => a.number === selected) ?? current?.state.attempts.at(-1);
  async function start() {
    setBusy(true); setError(""); setPreview(""); setSelected(0);
    try {
      const row = await api<Repair>(`/investigations/${investigation.id}/repairs`, { method: "POST" });
      setCurrent(row); setRows((prior) => [row, ...prior.filter((x) => x.id !== row.id)]);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function cancel() {
    if (!current) return;
    setBusy(true);
    try { setCurrent(await api<Repair>(`/repairs/${current.id}/cancel`, { method: "POST" })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function openPreview() {
    if (!current || !attempt) return;
    setBusy(true); setError("");
    try {
      const result = await api<{url: string}>(`/repairs/${current.id}/attempts/${attempt.number}/preview`, { method: "POST" });
      setPreview(result.url); setReset((n) => n + 1);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <section className="report-panel repair-workspace" aria-label="Repair workspace">
    <div className="repair-heading"><div><span className="eyebrow">BOUNDED MODEL REPAIR · ORIGINAL PRESERVED</span>
      <h2><Wrench size={19} /> Build a candidate. Check its behavior.</h2>
      <p>NVIDIA can fetch missing source through MCP and propose up to two patches. Trusted browser checks decide the result.</p></div>
      {active(current?.status) ? <button className="secondary-button" onClick={cancel} disabled={busy}><Square size={13} />Cancel repair</button> :
        <button className="primary-button" onClick={start} disabled={busy || investigation.status !== "completed"}>
          {busy ? <LoaderCircle size={14} className="spin" /> : <Wrench size={14} />}Generate candidate with NVIDIA<ArrowRight size={13} /></button>}
    </div>
    {error && <p role="alert" className="error-banner">{error}</p>}
    {rows.length > 0 && <div className="investigation-history"><label htmlFor="saved-repairs">Saved repairs</label>
      <select id="saved-repairs" value={current?.id ?? ""} onChange={(e) => { setCurrent(rows.find((r) => r.id === e.target.value) ?? null); setPreview(""); setSelected(0); }}>
        {rows.map((r) => <option key={r.id} value={r.id}>{new Date(r.created_at).toLocaleTimeString()} · {label(r.status)} · {r.id.slice(0,8)}</option>)}
      </select><span className="run-status">{active(current?.status) && <LoaderCircle size={13} className="spin" />}{label(current?.status)}</span></div>}
    {current && <>
      <div className="repair-budget"><span>{current.state.attempt_count}/2 candidate attempts</span><span>{current.state.request_remaining} provider requests left</span><span>{current.state.output_budget_remaining} reserved-output tokens left</span></div>
      <details className="repair-events" open={active(current.status)}><summary>Observable repair events</summary><ol>{current.events.map((e) => <li key={e.sequence}><strong>{e.title}</strong><p>{e.detail}</p></li>)}</ol></details>
      <h3 aria-live="polite">{label(current.status)}</h3>
      {current.error && <p className="error-banner">{current.error} <code>{current.error_code}</code></p>}
      <div className="repair-attempts" aria-label="Candidate attempts">{current.state.attempts.map((a) => <button key={a.number} className={a.number === attempt?.number ? "selected" : ""} onClick={() => { setSelected(a.number); setPreview(""); }}>Attempt {a.number} · {label(a.status)}</button>)}</div>
      {attempt && <><p>{attempt.proposal.explanation}</p>{attempt.rejection && <p role="alert">Rejected: {attempt.rejection}</p>}
        {attempt.candidate && <>
          <dl className="snapshot-identity"><div><dt>Candidate SHA-256</dt><dd className="mono">{attempt.candidate.candidate_hash}</dd></div><div><dt>Source snapshot</dt><dd className="mono">{current.state.snapshot_id}</dd></div></dl>
          <div className="section-heading"><h3>Exact candidate diff · cart.js</h3><a href={`/api/repairs/${current.id}/attempts/${attempt.number}/patch`}><Download size={13} />Download patch</a></div>
          <Suspense fallback={<p>Loading diff…</p>}><CandidateDiff original={attempt.candidate.original} modified={attempt.candidate.content} /></Suspense>
          <details className="raw-data"><summary>Plain diff and PR preview</summary><p>Proposed change to fixtures/retail/cart.js. No application branch or pull request is published. Any future publication requires owner approval of this exact candidate and destination.</p><pre>{attempt.candidate.diff}</pre></details>
          <div className="section-heading"><div><ShieldCheck size={16} /><h3>Independent behavioral verification</h3></div><span className="small-tag">{attempt.verification?.status ?? "NOT EXECUTED"}</span></div>
          {attempt.verification && <><p>{attempt.verification.scope}</p><p className="mono verification-identity">Verifier {attempt.verification.verifier_version}<br/>Candidate {attempt.verification.candidate_hash}</p>
            <div className="verification-table"><table><thead><tr><th>Trusted check</th><th>Original</th><th>Candidate</th></tr></thead><tbody>{attempt.verification.checks.map((c) => <tr key={c.name}><th>{c.name}</th><td>{current.state.original_verification?.checks.find((x) => x.name === c.name)?.passed ? "Passed" : "Failed"}</td><td><details><summary>{c.passed ? "Passed" : "Failed"}</summary><pre>{JSON.stringify({expected: c.expected, observed: c.observed}, null, 2)}</pre></details></td></tr>)}</tbody></table></div>
            <a href={`/api/repairs/${current.id}/attempts/${attempt.number}/screenshot`} target="_blank" rel="noreferrer">Captured candidate browser evidence ↗</a></>}
          <div className="section-heading"><h3>Try the behavior yourself</h3><button className="secondary-button" onClick={openPreview} disabled={busy}>Start / reset candidate preview</button></div>
          <p className="citation-validity">Separate browser sessions. The candidate uses an opaque sandbox origin with network requests blocked by CSP. Preview environments expire after ten minutes; reset starts a fresh session.</p>
          <div className="repair-previews"><div><strong>Original · defective frozen storefront</strong><iframe title="Original application" src="/retail/" sandbox="allow-scripts" key={`original-${investigation.id}`} /></div><div><strong>Candidate · {attempt.candidate.candidate_hash.slice(0,12)}</strong>{preview ? <iframe title="Candidate application" src={preview} sandbox="allow-scripts" referrerPolicy="no-referrer" key={`${preview}-${reset}`} /> : <div className="preview-empty">Start the candidate preview to interact with the proposed change.</div>}</div></div>
        </>}
      </>}
      <details className="raw-data"><summary>Exact MCP discovery, calls, model inputs and rejected outputs</summary><pre>{JSON.stringify({ source_reads: current.state.source_reads, mcp_events: current.state.mcp_events, model_records: current.state.model_records, provider_calls: current.state.provider_calls }, null, 2)}</pre></details>
      <a href={`/api/repairs/${current.id}/evidence`}><Download size={13} />Download complete repair evidence</a>
    </>}
  </section>;
}
