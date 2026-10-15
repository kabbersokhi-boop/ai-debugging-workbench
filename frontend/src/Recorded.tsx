import { lazy, Suspense, useEffect, useState } from "react";
import { api } from "./types";

const Diff = lazy(() => import("./Diff"));
type Item = { id: string; title: string; outcome: string; mode: string };
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
      <section id="recorded-result" className="report-panel release-result"><span className="eyebrow">HISTORICAL OUTCOME · {items.find(x => x.id === id)?.mode}</span>
        <h2>{record.repair.status === "verified" ? "Verified for the recorded checks" : record.repair.status.replaceAll("_", " ")}</h2>
        <p>{record.recording.note}</p><p>{attempt?.proposal.explanation ?? record.repair.error}</p>
        <p>Model: <code>{record.repair.state.model_records[0]?.model ?? "See retained failure record"}</code></p>
        {attempt?.verification && <p>{attempt.verification.checks.filter(c => c.passed).length}/{attempt.verification.checks.length} named checks passed in the recorded environment.</p>}
        <nav className="release-links"><a href="#recorded-comparison">Original / candidate</a><a href="#recorded-diff">Exact diff</a><a href="#recorded-checks">Verification checks</a><a href="#recorded-sources">Sources and trace</a></nav>
      </section>
      {attempt?.candidate && <>
        <section id="recorded-comparison" className="report-panel"><h2>Original and candidate · captured browser comparison</h2><p>Historical pixels from actual interaction at quantity three. Viewing this image does not execute candidate code or perform a new repair.</p>
          {id === "m3-live-success" && <img className="recorded-comparison" src="/api/recorded-assets/live-repair-before-after.png" alt="Captured quantity-three comparison: original total $72; verified candidate total $192" />}</section>
        <section id="recorded-diff" className="report-panel"><h2>Exact recorded diff</h2><Suspense fallback={<p>Loading local diff viewer…</p>}><Diff original={attempt.candidate.original} modified={attempt.candidate.content} /></Suspense><details><summary>Plain diff</summary><pre>{attempt.candidate.diff}</pre></details></section>
      </>}
      <section id="recorded-checks" className="report-panel"><h2>Independent recorded checks</h2>
        {attempt?.verification ? <ul>{attempt.verification.checks.map(c => <li key={c.name}>{c.passed ? "Passed" : "Failed"} · {c.name}</li>)}</ul> : <p>No completed candidate verification. This outcome is not a verified fix.</p>}
        {attempt?.rejection && <p role="alert">Rejected output: {attempt.rejection}</p>}</section>
      <section id="recorded-sources" className="report-panel"><h2>Engineering evidence</h2>
        <details><summary>Recording, source, candidate and runtime identity</summary><pre>{JSON.stringify({recording:record.recording.id,recording_sha256:record.recording_sha256,implementation:record.recording.implementation_commit,snapshot:record.repair.state.snapshot_id,candidate:attempt?.candidate?.candidate_hash,verifier:attempt?.verification?.verifier_version,runtime:attempt?.verification?.container_image_id},null,2)}</pre></details>
        {record.sources.files.map(f => <details key={f.path}><summary>{f.path}</summary><pre>{f.content}</pre></details>)}
        <details><summary>Saved model calls, MCP trace, rejected outputs and full evidence</summary><pre>{JSON.stringify(record,null,2)}</pre></details>
      </section>
    </>}
  </main>;
}
