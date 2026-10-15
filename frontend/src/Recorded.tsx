import { lazy, Suspense, useEffect, useState } from "react";
import { api } from "./types";

const Diff = lazy(() => import("./Diff"));
type Item = { id: string; title: string; outcome: string; mode: string; comparison_asset?: string; walkthrough_asset?: string };
type Recording = {
  recording_sha256: string;
  recording: { id: string; note: string; implementation_commit: string };
  repair: { id: string; status: string; error: string | null; state: {
    snapshot_id: string; model_records: { model: string }[];
    attempts: { number: number; rejection: string | null; proposal: { explanation: string };
      candidate: { candidate_hash: string; original: string; content: string; diff: string } | null;
      verification: { checks: { name: string; passed: boolean }[]; verifier_version: string; container_image_id: string } | null }[];
    mcp_events: unknown[]; provider_calls: unknown[];
  }};
  sources: { files: { path: string; content: string }[] };
  investigation?: { diagnosis?: { diagnosis: string; uncertainty: string[] }; retrieval?: {
    query: string; snapshot_id: string; supplied_context: {source_id: string; path: string; start_line: number; end_line: number; content: string}[];
  }};
};

export default function RecordedExplorer() {
  const [items, setItems] = useState<Item[]>([]);
  const [id, setId] = useState("");
  const [record, setRecord] = useState<Recording | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<{records: Item[]}>("/recordings").then(x => {setItems(x.records); setId(x.records[0]?.id ?? "");}).catch(e => setError(String(e))); }, []);
  useEffect(() => {
    if (!id) return;
    let disposed = false; setRecord(null); setError("");
    api<Recording>(`/recordings/${id}`).then(x => {if (!disposed) setRecord(x);}).catch(e => {if (!disposed) setError(String(e));});
    return () => {disposed = true;};
  }, [id]);
  const attempt = record?.repair.state.attempts.at(-1);
  const comparison = items.find(x => x.id === id)?.comparison_asset ?? (id === "m3-live-success" ? "live-repair-before-after.png" : null);
  return <main id="workspace" className="workspace recorded-explorer">
    <a className="skip-link" href="#recorded-result">Skip to result</a>
    <header className="page-intro"><div><span className="eyebrow">RECORDED RUN EXPLORER · NO NEW INFERENCE</span>
      <h1>From bug report to browser proof.</h1><p>Explore real execution records, exact source changes, and independent checks. This mode needs no provider credentials.</p></div>
      <a href="/" className="secondary-button">Workbench home</a></header>
    <section className="case-header"><label htmlFor="recording">Choose a saved execution</label>
      <select id="recording" value={id} onChange={e => setId(e.target.value)}>{items.map(x => <option key={x.id} value={x.id}>{x.title} · {x.outcome}</option>)}</select></section>
    {error && <p role="alert" className="error-banner">{error} Recorded evidence could not load; no live request was substituted.</p>}
    {!record && !error && <p role="status">Loading saved evidence…</p>}
    {record && <>
      <section id="recorded-result" className={`report-panel release-result ${record.repair.status === "verified" ? "release-verified" : "release-stopped"}`}><span className="eyebrow">HISTORICAL OUTCOME · {items.find(x => x.id === id)?.mode}</span>
        <h2>{record.repair.status === "verified" ? "Verified for the recorded checks" : record.repair.status.replaceAll("_", " ")}</h2>
        <p>Saved execution · viewing this evidence performs no new inference or repair.</p><p>{attempt?.proposal.explanation ?? record.repair.error}</p>
        <p>Model: <code>{record.repair.state.model_records[0]?.model ?? "See retained failure record"}</code></p>
        {attempt?.verification && <p>{attempt.verification.checks.filter(c => c.passed).length}/{attempt.verification.checks.length} named checks passed in the recorded environment.</p>}
        <nav className="release-links"><a href="#recorded-comparison">Original / candidate</a><a href="#recorded-diff">Exact diff</a><a href="#recorded-checks">Verification checks</a><a href="#recorded-sources">Sources and trace</a></nav>
      </section>
      {attempt?.candidate && <>
        <section id="recorded-comparison" className="report-panel"><h2>Original and candidate · captured browser comparison</h2><p>{comparison ? "Historical pixels from actual browser interaction. Viewing this image does not execute candidate code or perform a new repair." : "No comparison image exists for this stopped execution. Inspect the retained failure and cleanup evidence below."}</p>
          {comparison && <img className="recorded-comparison" src={`/api/recorded-assets/${comparison}`} alt="Captured original and candidate storefronts from this historical execution" />}</section>
        {items.find(x => x.id === id)?.walkthrough_asset && <details className="report-panel"><summary>Watch the 16-second captioned walkthrough · saved-run interaction</summary><p>This reopens the actual NVIDIA repair. It performs no new inference. Named controls drive the isolated candidate; the original totals $136 at quantity two and the candidate totals $128.</p><video controls preload="metadata" style={{width:"100%"}} aria-label="Captioned walkthrough of the saved NVIDIA shipping repair" src={`/api/recorded-assets/${items.find(x => x.id === id)?.walkthrough_asset}`} /><p>Transcript: reopen the saved repair; inspect its exact patch and twelve independent checks; use named remote controls; compare original and candidate; reopen history and inspect the mobile layout.</p></details>}
        <section id="recorded-diff" className="report-panel"><h2>Exact recorded diff</h2><Suspense fallback={<p>Loading local diff viewer…</p>}><Diff original={attempt.candidate.original} modified={attempt.candidate.content} /></Suspense><details><summary>Plain diff</summary><pre>{attempt.candidate.diff}</pre></details></section>
      </>}
      <section id="recorded-checks" className="report-panel"><h2>Independent recorded checks</h2>
        {attempt?.verification ? <ul>{attempt.verification.checks.map(c => <li key={c.name}>{c.passed ? "Passed" : "Failed"} · {c.name}</li>)}</ul> : <p>No completed candidate verification. This outcome is not a verified fix.</p>}
        {attempt?.rejection && <p role="alert">Rejected output: {attempt.rejection}</p>}</section>
      <section id="recorded-sources" className="report-panel"><h2>Engineering evidence</h2>
        {record.investigation?.diagnosis && <details><summary>Actual NVIDIA diagnosis and remaining uncertainty</summary><p>{record.investigation.diagnosis.diagnosis}</p><ul>{record.investigation.diagnosis.uncertainty.map(x => <li key={x}>{x}</li>)}</ul></details>}
        {record.investigation?.retrieval && <details><summary>Repository context actually supplied to diagnosis</summary><p>Saved query</p><pre>{record.investigation.retrieval.query}</pre><p>Snapshot <code>{record.investigation.retrieval.snapshot_id}</code></p>
          {record.investigation.retrieval.supplied_context.map(c => <details key={c.source_id}><summary>{c.path}:{c.start_line}–{c.end_line} · {c.source_id}</summary><pre>{c.content}</pre></details>)}</details>}
        <details><summary>Recording, source, candidate and runtime identity</summary><p>{record.recording.note}</p><pre>{JSON.stringify({recording:record.recording.id,recording_sha256:record.recording_sha256,implementation:record.recording.implementation_commit,snapshot:record.repair.state.snapshot_id,candidate:attempt?.candidate?.candidate_hash,verifier:attempt?.verification?.verifier_version,runtime:attempt?.verification?.container_image_id},null,2)}</pre></details>
        {record.sources.files.map(f => <details key={f.path}><summary>{f.path}</summary><pre>{f.content}</pre></details>)}
        <details><summary>Saved model calls, MCP trace, rejected outputs and full evidence</summary><pre>{JSON.stringify(record,null,2)}</pre></details>
      </section>
    </>}
  </main>;
}
