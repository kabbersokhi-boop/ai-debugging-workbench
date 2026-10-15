import { useRef, useState } from "react";
import { api } from "./types";

type Frame = { image: string; candidate_hash: string; observed: Record<string, string> };

/** Only trusted controls and pixels reach the visitor. Candidate JavaScript stays remote. */
export default function RemotePreview({ endpoint, candidateHash }: { endpoint: string; candidateHash: string }) {
  const [frame, setFrame] = useState<Frame | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(0);
  async function act(action: string) {
    const id = ++request.current;
    setBusy(true); setError("");
    try {
      const next = await api<Frame>(endpoint, { method: "POST", body: JSON.stringify({ action }) });
      if (id !== request.current) return;
      if (next.candidate_hash !== candidateHash) throw new Error("Remote preview identity mismatch");
      setFrame(next);
    } catch (e) { if (id === request.current) setError((e as Error).message); }
    finally { if (id === request.current) setBusy(false); }
  }
  return <section className="remote-preview" aria-label="Remote candidate application">
    <p>Interactive remote browser · candidate scripts execute in the isolated container. Only pixels and named controls reach this page.</p>
    <div className="remote-controls">
      {[["reset", "Reset candidate"], ["add", "Add to bag"], ["increase", "Increase quantity"], ["decrease", "Decrease quantity"]].map(([action, label]) =>
        <button className="secondary-button" key={action} onClick={() => act(action)} disabled={busy || (!frame && action !== "reset")}>{label}</button>)}
    </div>
    {busy && <p role="status">Remote browser working…</p>}
    {error && <p role="alert">{error}</p>}
    {frame ? <><p aria-live="polite">Quantity <strong data-testid="remote-quantity">{frame.observed["bag-count"]}</strong> · total <strong data-testid="remote-total">{frame.observed.total}</strong></p>
      <img src={`data:image/png;base64,${frame.image}`} alt="Current candidate state captured in the remote browser" /></> : <p>Reset candidate to open a fresh remote browser session.</p>}
  </section>;
}
