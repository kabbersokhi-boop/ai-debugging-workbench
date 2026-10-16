import { useEffect, useRef, useState } from "react";
import { api, type Bug, type Run } from "./types";

type Job = { id: string; status: string; error?: string | null; state?: { attempts: { proposal: { explanation: string }; verification?: { checks: { passed: boolean }[] } }[] } };
const active = (status: string) => ["queued", "running", "indexing", "retrieving", "diagnosing", "inspecting", "proposing", "validating", "candidate_created", "verifying"].includes(status);

export default function Workflow({ bug, onRun, onStage }: { bug: Bug; onRun: (run: Run) => void; onStage: (stage: string) => void }) {
  const [stage, setStage] = useState("ready");
  const [result, setResult] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const current = useRef("");
  const working = ["reproduction", "diagnosis", "repair"].includes(stage);
  useEffect(() => () => { generation.current++; }, []);
  async function start() {
    const request = ++generation.current;
    setError(""); setResult(null); current.current = "";
    const valid = () => request === generation.current;
    const phase = (next: string) => { if (valid()) {setStage(next); onStage(next);} };
    async function wait<T extends Job>(path: string): Promise<T> {
      current.current = path;
      for (let n = 0; n < 600; n++) {
        if (!valid()) throw new Error("Workflow stopped");
        const row = await api<T>(path);
        if (!active(row.status)) return row;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      throw new Error("Workflow observation timed out; inspect saved history.");
    }
    try {
      phase("reproduction");
      const run = await api<Run>("/runs", {method:"POST", body:JSON.stringify({bug_id:bug.id}), headers:{"Idempotency-Key":crypto.randomUUID()}});
      if (!valid()) { void api(`/runs/${run.id}/cancel`, {method:"POST"}).catch(() => {}); return; }
      current.current = `/runs/${run.id}`; onRun(run);
      const reproduced = await wait<Run>(current.current);
      if (!valid()) return;
      onRun(reproduced);
      if (reproduced.status !== "reproduced") throw new Error(`Reproduction ended: ${reproduced.status}. No repair started.`);
      phase("diagnosis");
      const investigation = await api<Job>(`/runs/${run.id}/investigations`, {method:"POST", body:"{}"});
      if (!valid()) { void api(`/investigations/${investigation.id}/cancel`, {method:"POST"}).catch(() => {}); return; }
      phase("diagnosis");
      const diagnosed = await wait<Job>(`/investigations/${investigation.id}`);
      if (!valid()) return;
      if (diagnosed.status !== "completed") throw new Error(`Diagnosis ended: ${diagnosed.status}. ${diagnosed.error ?? "No repair started."}`);
      phase("repair");
      const repair = await api<Job>(`/investigations/${investigation.id}/repairs`, {method:"POST"});
      if (!valid()) { void api(`/repairs/${repair.id}/cancel`, {method:"POST"}).catch(() => {}); return; }
      phase("repair");
      const completed = await wait<Job>(`/repairs/${repair.id}`);
      if (!valid()) return;
      setResult(completed); phase("finished");
    } catch (e) { if (valid()) {setError((e as Error).message); phase("stopped");} }
  }
  async function cancel() {
    const request = ++generation.current;
    try { if (current.current) await api(`${current.current}/cancel`, {method:"POST"}); }
    catch (e) {if (request === generation.current) setError((e as Error).message);}
    if (request !== generation.current) return;
    setStage("cancelled"); onStage("cancelled");
  }
  return <section className="report-panel workflow-launcher" aria-label="Complete workflow">
    <div className="section-heading"><div><h2>Reproduce → investigate → verify</h2><p>One supported scenario, real NVIDIA calls, an isolated candidate, and independent browser checks.</p></div>
      {working ? <button className="secondary-button" onClick={cancel}>Cancel workflow</button> : <button className="primary-button" onClick={start}>Start full workflow</button>}</div>
    {working && <p role="status">{stage === "reproduction" ? "Reproducing in Chromium" : stage === "diagnosis" ? "Retrieving source and requesting NVIDIA diagnosis" : "Generating and independently checking a candidate"}… Saved evidence remains available below.</p>}
    {error && <p role="alert" className="error-banner">{error}</p>}
    {stage === "cancelled" && <p>Workflow cancelled. Partial evidence is retained.</p>}
    {result && <div className="release-result"><h2>{result.status === "verified" ? "Verified for the supported checks" : `Repair outcome: ${result.status.replaceAll("_"," ")}`}</h2>
      <p>{result.state?.attempts.at(-1)?.proposal.explanation ?? result.error}</p>
      <a className="primary-button" href="#repair-result">Inspect diff, checks and original / candidate comparison ↓</a></div>}
  </section>;
}
