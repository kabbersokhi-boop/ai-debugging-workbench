import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { api } from "./types";
import { evidenceSummary } from "./evaluationSummary";
import "./evaluation.css";
import "./patchAudit.css";
const RepositoryAudit = lazy(() => import("./RepositoryAudit"));
const Diff = lazy(() => import("./Diff"));

type Task = { id: string; title: string; problem: string; expected: string; ordinary_scope: string; base_commit: string; spec_hash: string; upstream: string; issue: string; license: string };
type Provenance = { category: string; producer_label?: string; producer?: string; source_reference?: string; limitations: string; metadata_note?: string };
type Candidate = { id: string; task_id: string; candidate_hash: string; record_hash: string; patch: string; submitted_patch_hash: string; base_commit: string; affected_files: string[]; provenance: Provenance; original: Record<string,string>; modified: Record<string,string> };
type Check = { name: string; status: string; expected: unknown; observed: unknown };
type Phase = { status: string; outcome?: string; exit_code?: number; duration_ms?: number; stdout?: string; stderr?: string; checks?: Check[] };
type Result = { status: string; reason?: string; ordinary?: Phase; independent?: Phase; binding?: unknown };
type Audit = { id: string; status: string; candidate_id: string; candidate_hash: string; created_at: string; execution_mode: string; evidence: { task: Task; candidate: Candidate; reason?: string; envelope?: { result: Result }; license_text?: string } };
type Preset = { key: string; label: string; task_id: string; category: string };
type Saved = Pick<Audit,"id"|"status"|"candidate_hash"|"created_at"> & {provenance_category: string; candidate_label: string};
const label = (s: string) => ({invalid_candidate:"insufficient or invalid observations", invalid_evidence:"invalid stored evidence", infrastructure_error:"execution or infrastructure error"})[s] ?? s.replaceAll("_", " ");
function provenanceLabel(p: Provenance) {
  return ({retained_model:"Retained model output · captured generation evidence", user_declared:"Imported patch · user-declared provenance (unverified)", human:"Imported patch · declared human-authored", unknown:"Imported patch · authorship unknown", control:"Deliberately authored evaluator control"})[p.category] ?? "Unverified provenance";
}
function assertAudit(a: Audit, id?: string, c?: Candidate) {
  if ((id && a.id !== id) || a.candidate_id !== a.evidence.candidate.id || a.candidate_hash !== a.evidence.candidate.candidate_hash || (c && (a.candidate_id !== c.id || a.candidate_hash !== c.candidate_hash))) throw new Error("Audit response identity mismatch; no result displayed.");
  return a;
}
function url(values: Record<string,string>) { const u = new URL(location.href); u.search = new URLSearchParams(values).toString(); history.replaceState(null,"",u); }

function PreparedPatchAudit({ recorded = false }: {recorded?: boolean}) {
  const [tasks,setTasks] = useState<Task[]>([]), [taskId,setTaskId] = useState("boltons-addlist");
  const [presets,setPresets] = useState<Preset[]>([]), [preset,setPreset] = useState("");
  const [candidate,setCandidate] = useState<Candidate|null>(null), [audit,setAudit] = useState<Audit|null>(null);
  const [historyRows,setHistory] = useState<Saved[]>([]);
  const [patch,setPatch] = useState(""), [category,setCategory] = useState("unknown");
  const [producer,setProducer] = useState(""), [producerLabel,setProducerLabel] = useState(""), [sourceRef,setSourceRef] = useState("");
  const [confirmed,setConfirmed] = useState(false), [busy,setBusy] = useState(false), [error,setError] = useState("");
  const epoch = useRef(0);
  const running = audit?.status === "running";
  const task = tasks.find(t => t.id === taskId) ?? audit?.evidence.task;
  const result = audit?.evidence.envelope?.result;
  function clear() { epoch.current++; setCandidate(null); setAudit(null); setConfirmed(false); setError(""); setBusy(false); }
  async function refresh() { if (!recorded) setHistory(await api<Saved[]>("/patch-audits/runs")); }
  async function openAudit(id: string) {
    clear(); const token = epoch.current;
    try { const a = assertAudit(await api<Audit>(`${recorded ? "/recorded-audits" : "/patch-audits/runs"}/${id}`),id);
      if (token !== epoch.current) return;
      setAudit(a); setCandidate(a.evidence.candidate); setTaskId(a.evidence.task.id); setTasks(ts => ts.length ? ts : [a.evidence.task]);
      if (!recorded) url({audit:a.id}); else { setPreset(id); url({recordedAudit:id}); }
    } catch(e) { if (token === epoch.current) setError(String(e)); }
  }
  async function loadPreset(key: string) {
    if (recorded) { await openAudit(key); return; }
    clear(); setPreset(key); const token = epoch.current;
    try { const c = await api<Candidate>(`/patch-audits/examples/${key}`); if (token !== epoch.current) return;
      setCandidate(c); setTaskId(c.task_id); url({candidate:c.id});
    } catch(e) { if (token === epoch.current) setError(String(e)); }
  }
  useEffect(() => {
    let disposed = false;
    const token = epoch.current;
    (async () => {
      if (recorded) {
        const x = await api<{records:{id:string;title:string;task_id:string}[]}>("/recorded-audits");
        if (disposed || token !== epoch.current) return;
        setPresets(x.records.map(r => ({key:r.id,label:r.title,task_id:r.task_id,category:"retained_model"})));
        await openAudit(new URLSearchParams(location.search).get("recordedAudit") ?? x.records[0].id);
      } else {
        const [ts,ps] = await Promise.all([api<Task[]>("/patch-audits/tasks"), api<Preset[]>("/patch-audits/examples")]);
        if (disposed || token !== epoch.current) return;
        setTasks(ts); setPresets(ps); await refresh();
        if (disposed || token !== epoch.current) return;
        const params = new URLSearchParams(location.search);
        if (params.get("audit")) await openAudit(params.get("audit")!);
        else if (params.get("candidate")) {
          const c = await api<Candidate>(`/patch-audits/candidates/${params.get("candidate")}`);
          if (!disposed && token === epoch.current) { setCandidate(c); setTaskId(c.task_id); }
        } else await loadPreset(ps[0].key);
      }
    })().catch(e => {if (!disposed) setError(String(e));});
    return () => {disposed = true;};
  }, [recorded]);
  useEffect(() => {
    if (!audit || audit.status !== "running" || recorded) return;
    let disposed = false; const token = epoch.current, id = audit.id, c = audit.evidence.candidate;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { const next = assertAudit(await api<Audit>(`/patch-audits/runs/${id}`),id,c);
        if (!disposed && epoch.current === token) { setAudit(next); if (next.status !== "running") { await refresh(); return; } }
      } catch(e) { if (!disposed && epoch.current === token) setError(String(e)); }
      if (!disposed && epoch.current === token) timer = setTimeout(poll,700);
    }
    timer = setTimeout(poll,700);
    return () => {disposed = true; clearTimeout(timer);};
  }, [audit?.id,audit?.status,recorded]);
  async function importPatch() {
    clear(); setBusy(true); const token = epoch.current;
    try { const c = await api<Candidate>("/patch-audits/candidates", {method:"POST",body:JSON.stringify({task_id:taskId,patch,category,producer,producer_label:producerLabel,source_reference:sourceRef})});
      if (token !== epoch.current) return; setCandidate(c); setPreset(""); url({candidate:c.id});
    } catch(e) {if (token === epoch.current) setError(`Patch rejected before execution. ${String(e)}`);}
    finally {if (token === epoch.current) setBusy(false);}
  }
  async function start() {
    if (!candidate || !confirmed) return;
    const c = candidate, token = epoch.current; setBusy(true); setError("");
    try { const a = assertAudit(await api<Audit>("/patch-audits/runs",{method:"POST",body:JSON.stringify({candidate_id:c.id,candidate_hash:c.candidate_hash,record_hash:c.record_hash,confirm_local_execution:true})}),undefined,c);
      if (token !== epoch.current) return; setAudit(a); setConfirmed(false); url({audit:a.id}); await refresh();
    } catch(e) {if (token === epoch.current) setError(String(e));}
    finally {if (token === epoch.current) setBusy(false);}
  }
  const emptyStandalone = result?.independent?.checks?.find(c => c.name === "standalone_urlutils:empty" && c.status === "failed")?.observed as {length?: number; keys?: unknown[]; items?: unknown[]} | undefined;
  const missedStandalone = taskId === "boltons-addlist" && result?.ordinary?.outcome === "passed"
    && candidate?.affected_files.includes("boltons/dictutils.py") && !candidate?.affected_files.includes("boltons/urlutils.py")
    && emptyStandalone?.length === 1 && JSON.stringify(emptyStandalone.keys) === "[]" && JSON.stringify(emptyStandalone.items) === "[]"
    && result.independent?.checks?.filter(c => !c.name.startsWith("standalone_urlutils:")).every(c => c.status === "passed");
  const evidenceUrl = audit ? `/api/${recorded ? "recorded-audits" : "patch-audits/runs"}/${audit.id}/evidence` : "";
  const patchUrl = candidate ? recorded ? `/api/recorded-audits/${audit?.id}/patch` : `/api/patch-audits/candidates/${candidate.id}/patch` : "";
  return <main className="evaluation-workspace patch-audit-workspace">
    <nav className="evaluation-nav" aria-label="Workbench navigation"><strong>AI debugging workbench</strong><div>
      <a href={recorded ? "/recorded/?workspace=debugger" : "/?workspace=debugger"}>{recorded ? "Recorded debugger runs" : "Debugger"}</a>{" · "}
      {!recorded && <><a href="/?workspace=evaluation">Agent Evaluation</a>{" · "}</>}
      <a href={recorded ? "/" : "/recorded/"}>{recorded ? "Local auditing requires the local application" : "Inspect recorded audits"}</a>
    </div></nav>
    <header className="evaluation-intro"><span className="eyebrow">{recorded ? "RECORDED EVIDENCE · NO EXECUTION" : "TRUSTED LOCAL OWNER MODE"}</span>
      <h1>Patch Audit</h1><p>Bring a completed patch. See what the ordinary tests establish, what independent checks establish, and the evidence behind both.</p>
      <p>Independent checks are evaluator-owned behavioral checks for the named task. Passing them does not establish universal correctness or security.</p></header>
    {error && <p role="alert" className="error-banner">{error}{recorded && " No live audit was substituted."}</p>}
    <section className="evaluation-selection" aria-label="Choose audit material">
      {!recorded && <label>Supported software task<select aria-label="Supported software task" value={taskId} disabled={running} onChange={e => {clear();setTaskId(e.target.value);setPreset("");setPatch("");url({});}}>{tasks.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}</select></label>}
      <label>{recorded ? "Saved patch audit" : "Retained candidate"}<select aria-label={recorded ? "Saved patch audit" : "Retained candidate"} value={preset} disabled={running} onChange={e => loadPreset(e.target.value)}>
        <option value="" disabled>Choose an example</option>
        <optgroup label="Genuine retained model outputs">{presets.filter(p => p.category === "retained_model" && (recorded || p.task_id === taskId)).map(p => <option key={p.key} value={p.key}>{p.label}</option>)}</optgroup>
        {!recorded && <optgroup label="Authored evaluator controls · separate evidence">{presets.filter(p => p.category === "control" && p.task_id === taskId).map(p => <option key={p.key} value={p.key}>{p.label} · control</option>)}</optgroup>}
      </select></label>
    </section>
    {recorded && <p className="evaluation-mismatch">Inspect saved evidence. This is not a fresh audit or animated execution. To audit a new patch, run this application locally in trusted owner mode. Import and execution are unavailable here.</p>}
    {audit && <section className="evaluation-panel audit-result" aria-label="Patch audit result">
      <div className="evaluation-heading"><div><span className="eyebrow">{recorded ? "SAVED HISTORICAL EXECUTION" : "FRESH LOCAL AUDIT"}</span><h2>{audit.evidence.task.title}</h2></div><strong role="status" className={`evaluation-status ${audit.status}`}>{label(audit.status)}</strong></div>
      <p>{candidate?.provenance.producer_label || "Imported completed patch"}</p>
      <p className="audit-summary">{running ? "Running checks in disposable restricted environments. No completed result yet." : ["cancelled","interrupted","invalid_evidence","infrastructure_error","timeout"].includes(audit.status) ? (audit.evidence.reason ?? `Audit ${label(audit.status)}. No complete passing conclusion is available.`) : result?.status === "passed" ? "Passed these checks for this task and environment." : evidenceSummary(taskId,result)}</p>
      <div className="evaluation-phases"><PhaseCard title="Ordinary repository checks" phase={result?.ordinary} /><PhaseCard title="Independent behavioral checks" phase={result?.independent} /></div>
      {result?.ordinary?.outcome === "passed" && result?.independent?.outcome === "failed" && <p className="evaluation-mismatch">The selected ordinary suite passed. Independent checks found additional behavior the suite missed.{candidate?.provenance.category === "control" && " This is an authored control, not a genuine model failure."}</p>}
      {result?.ordinary?.outcome === "failed" && <p>Ordinary checks detected a failure too. Independent observations are additional evidence, not a unique discovery.</p>}
      {missedStandalone && <div className="audit-case"><h3>The missed standalone implementation</h3><p>The patch repaired <code>boltons/dictutils.py</code> but left the required standalone copy in <code>boltons/urlutils.py</code> unchanged. Normal package imports use the repaired implementation; standalone mode uses the missed copy. The selected 155 existing tests passed.</p><p>Empty input should leave length zero. The standalone object reports length one while its keys and items are empty. Related observations describe one incomplete repair.</p><details><summary>Inspect the omitted standalone file · boltons/urlutils.py</summary><pre>{candidate?.modified["boltons/urlutils.py"]}</pre></details></div>}
      <p><a href={patchUrl} download>Download exact patch</a>{" · "}<a href={evidenceUrl} download>Download audit evidence</a>{" · "}<button onClick={() => navigator.clipboard?.writeText(location.href).catch(() => setError("Copy failed. Use the saved URL in the address bar."))}>Copy saved audit link</button></p>
      {result?.independent?.checks && <details className="evaluation-observations"><summary>Detailed behavioral observations · {result.independent.checks.length}</summary>{result.independent.checks.map(c => <details key={c.name}><summary>{label(c.status)} · {c.name}</summary><p>Expected</p><pre>{JSON.stringify(c.expected,null,2)}</pre><p>Observed</p><pre>{JSON.stringify(c.observed,null,2)}</pre></details>)}</details>}
      <details><summary>Execution identities and reproduction</summary><p>{recorded ? "These identities belong to the saved execution. No fresh environment was started." : "Every re-audit creates a new execution UUID, not a new candidate, agent trial or defect discovery."}</p><pre>{JSON.stringify(result?.binding ?? {},null,2)}</pre>{!recorded && <pre>uv run --project backend python -m workbench.patch_audit.cli {candidate?.id} --confirm-local-execution</pre>}<p>Start the local stack with <code>docker compose up --build -d --wait api</code>, import the downloaded patch for this pinned task, inspect it, and confirm local execution. The runtime image ID may differ on rebuild; compare the retained identities.</p></details>
      <details><summary>Saved audit evidence</summary><pre>{JSON.stringify(audit,null,2)}</pre></details>
    </section>}
    {task && <details className="evaluation-panel"><summary>Problem, explicit requirement and pinned source</summary><p>{task.problem}</p><p>{task.expected}</p><p>{task.ordinary_scope}</p><p><a href={task.upstream}>Upstream project</a>{" · "}<a href={task.issue}>Original issue</a>{" · "}{task.license}</p><code>Base {task.base_commit}</code><br/><code>Task {task.spec_hash}</code>{audit?.evidence.license_text && <pre>{audit.evidence.license_text}</pre>}</details>}
    {!recorded && <details className="evaluation-panel audit-import"><summary>Import a completed patch · review before execution</summary><p>UTF-8 .patch/.diff or pasted unified diff, at most 64 KiB. Existing approved production files only; exact pinned-base context, no fuzzy application. Import does not execute code.</p>
      <label>Plain-text patch file<input aria-label="Plain-text patch file" type="file" accept=".patch,.diff,text/plain" disabled={running} onChange={async e => { const f=e.target.files?.[0]; if (!f) return; clear(); const token=epoch.current; try {if (!/\.(patch|diff)$/i.test(f.name) || f.size > 65536) throw new Error("Choose a .patch/.diff file of at most 64 KiB"); const text=new TextDecoder("utf-8",{fatal:true}).decode(await f.arrayBuffer()); if (epoch.current === token) setPatch(text);} catch(x) {if (epoch.current === token) setError(String(x));} }}/></label>
      <label>Unified diff<textarea aria-label="Unified diff" value={patch} disabled={running} onChange={e => {clear();setPatch(e.target.value);}} rows={10} spellCheck={false}/></label>
      <label>Declared authorship<select aria-label="Declared authorship" value={category} disabled={running} onChange={e => {clear();setCategory(e.target.value);}}><option value="unknown">Unknown</option><option value="human">Human-authored (declared)</option><option value="user_declared">Model or tool (user-declared, unverified)</option></select></label>
      <div className="audit-import-fields"><label>Optional producer label<input aria-label="Optional producer label" value={producerLabel} maxLength={200} disabled={running} onChange={e => {clear();setProducerLabel(e.target.value);}}/></label><label>Optional model or tool<input aria-label="Optional model or tool" value={producer} maxLength={200} disabled={running} onChange={e => {clear();setProducer(e.target.value);}}/></label><label>Optional source reference<input aria-label="Optional source reference" value={sourceRef} maxLength={500} disabled={running} onChange={e => {clear();setSourceRef(e.target.value);}}/></label></div><p>Labels and references are declarations, not evidence of authorship. No reference is fetched.</p>
      <button className="primary-button" disabled={!patch || running || busy} onClick={importPatch}>{busy ? "Checking patch…" : "Import for review"}</button>
    </details>}
    {candidate && <section className="evaluation-panel" aria-label="Candidate review"><h2>Exact completed patch</h2><p><strong>{provenanceLabel(candidate.provenance)}</strong></p><p>{candidate.provenance.producer_label}{candidate.provenance.producer && ` · ${candidate.provenance.producer}`}</p><p>{candidate.provenance.limitations}</p>{candidate.provenance.metadata_note && <p>{candidate.provenance.metadata_note}</p>}<p>Affected files: {candidate.affected_files.map(p => <code key={p}>{p}{" "}</code>)}</p><pre className="evaluation-patch">{candidate.patch}</pre>
      {candidate.affected_files.map(p => <details key={p}><summary>Open code comparison · {p}</summary><Suspense fallback={<p>Opening local diff viewer…</p>}><Diff original={candidate.original[p]} modified={candidate.modified[p]} language="python"/></Suspense></details>)}
      <details><summary>Candidate, base and provenance identities</summary><pre>{JSON.stringify({id:candidate.id,candidate_hash:candidate.candidate_hash,record_hash:candidate.record_hash,submitted_patch_hash:candidate.submitted_patch_hash,base_commit:candidate.base_commit,provenance:candidate.provenance},null,2)}</pre></details>
      {!recorded && <div className="audit-confirm"><p>Import is review only. Confirmation starts untrusted code in restricted local containers. Containers and in-process Python observations are not a complete anti-tampering system for malicious programs.</p><label><input type="checkbox" checked={confirmed} disabled={running || busy} onChange={e => setConfirmed(e.target.checked)}/>I reviewed this exact patch and authorize local execution for this pinned task.</label><button className="primary-button" disabled={!confirmed || running || busy} onClick={start}>Run fresh audit</button>{running && <button className="secondary-button" onClick={() => api(`/patch-audits/runs/${audit.id}/cancel`,{method:"POST"}).catch(e => setError(String(e)))}>Cancel audit</button>}</div>}
    </section>}
    {!recorded && <section className="evaluation-panel"><div className="evaluation-heading"><h2>Saved audit history</h2><button onClick={() => refresh().catch(e => setError(String(e)))}>Refresh audit history</button></div>{!historyRows.length ? <p>No fresh audits yet. Imported patches do not appear as completed executions.</p> : <ul className="evaluation-history">{historyRows.map(h => <li key={h.id}><button disabled={running || busy} onClick={() => openAudit(h.id)}><span>{h.candidate_label} · {h.provenance_category === "control" ? "authored control" : h.provenance_category === "retained_model" ? "captured model output" : "imported, declared provenance"}<br/>{new Date(h.created_at).toLocaleString()} · {label(h.status)}</span><code>{h.candidate_hash.slice(0,16)} · {h.id.slice(0,8)}</code></button></li>)}</ul>}</section>}
    <footer>Finite checks on approved historical tasks. Authorship is separate from correctness. Repeated executions are not independent model trials. Original m02-v1: 0/6 additional detections. Separate development evidence: one detection from one ordinary-passing final, with three other journeys producing no submission. No pooled ranking.</footer>
  </main>;
}

function PhaseCard({title,phase}:{title:string;phase?:Phase}) { return <article><h3>{title}</h3><strong className={`evaluation-status ${phase?.outcome ?? phase?.status ?? "pending"}`}>{label(phase?.outcome ?? phase?.status ?? "No completed evidence")}</strong>{phase && <><p>Exit {phase.exit_code ?? "unknown"} · {phase.duration_ms === undefined ? "duration unknown" : `${(phase.duration_ms/1000).toFixed(2)} seconds`}</p><details><summary>Execution logs</summary><pre>{phase.stdout || "No stdout retained."}</pre>{phase.stderr && <pre>{phase.stderr}</pre>}</details></>}</article>; }


export default function PatchAudit({recorded=false}:{recorded?:boolean}) {
  const [source,setSource]=useState(new URLSearchParams(location.search).get("source")==="external" || new URLSearchParams(location.search).has("repositoryAudit") ? "external" : "prepared");
  if(recorded)return <PreparedPatchAudit recorded/>;
  return <><section className="evaluation-selection audit-source-selection"><label>Audit source<select aria-label="Audit source" value={source} onChange={e=>{setSource(e.target.value);const u=new URL(location.href);u.search=e.target.value==="external"?"source=external":"";history.replaceState(null,"",u);}}><option value="prepared">Existing prepared task</option><option value="external">External repository (experimental)</option></select></label></section>{source==="external"?<Suspense fallback={<p>Opening repository audit…</p>}><RepositoryAudit/></Suspense>:<PreparedPatchAudit/>}</>;
}
