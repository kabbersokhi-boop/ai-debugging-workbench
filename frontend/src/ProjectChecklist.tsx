import { useEffect, useRef, useState } from "react";
import { api } from "./types";

export type ChecklistPreparation = {
  ordinary: { id: string; plan: any };
  verification: { id: string; plan: any; requirements: any[] };
  checklist_use: { id: string; checklist_id: string; checklist: any };
};
export function downloadJson(value: unknown, filename: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2) + "\n"], {
      type: "application/json",
    }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export default function ProjectChecklist({
  candidateId,
  runtimes,
  disabled,
  onPrepared,
  onBusy,
}: {
  candidateId: string;
  runtimes: { runtime: string; image_id?: string; available: boolean }[];
  disabled: boolean;
  onBusy: (busy: boolean) => void;
  onPrepared: (value: ChecklistPreparation) => void;
}) {
  const [checklist, setChecklist] = useState<any>(null);
  const [match, setMatch] = useState<{
    status: string;
    reasons: string[];
    checklist_id: string;
  } | null>(null);
  const [reviewed, setReviewed] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const epoch = useRef(0);
  useEffect(
    () => () => {
      epoch.current++;
      onBusy(false);
    },
    [],
  );
  async function load(file?: File) {
    const token = ++epoch.current;
    setReviewed(false);
    setChecklist(null);
    setMatch(null);
    setError("");
    if (!file) return;
    setBusy(true);
    onBusy(true);
    try {
      if (file.size > 1048576) throw Error("Checklist exceeds 1 MiB");
      const value = JSON.parse(await file.text());
      const checked = await api<{ checklist: any }>(
        "/repository-audits/checklists/validate",
        { method: "POST", body: JSON.stringify(value) },
      );
      const compatible = await api<typeof match>(
        "/repository-audits/checklists/compatibility",
        {
          method: "POST",
          body: JSON.stringify({
            candidate_id: candidateId,
            checklist: checked.checklist,
          }),
        },
      );
      if (token !== epoch.current) return;
      setChecklist(checked.checklist);
      setMatch(compatible);
    } catch (e) {
      if (token === epoch.current) setError(String(e));
    } finally {
      if (token === epoch.current) {
        setBusy(false);
        onBusy(false);
      }
    }
  }
  async function prepare() {
    if (!reviewed || match?.status !== "compatible") return;
    setBusy(true);
    onBusy(true);
    setError("");
    const token = epoch.current;
    try {
      const runtime = runtimes.find(
        (r) => r.runtime === checklist.runtime && r.available && r.image_id,
      );
      if (!runtime)
        throw Error("Build the checklist's selected local runtime and reload.");
      const result = await api<ChecklistPreparation>(
        "/repository-audits/checklists/prepare",
        {
          method: "POST",
          body: JSON.stringify({
            candidate_id: candidateId,
            checklist,
            image_id: runtime.image_id,
            approve_requirements: true,
          }),
        },
      );
      if (token === epoch.current) {
        setReviewed(false);
        onPrepared(result);
      }
    } catch (e) {
      if (token === epoch.current) setError(String(e));
    } finally {
      if (token === epoch.current) {
        setBusy(false);
        onBusy(false);
      }
    }
  }
  return (
    <section
      className="evaluation-panel"
      aria-label="Reusable project checklist"
    >
      <h2>Reuse a project checklist</h2>
      <p>
        Load a versioned checklist for this patch. Compatibility checks compare
        the project, immutable source, declared scope and verifier version. Each
        application requires new review and execution approval.
      </p>
      <label>
        Project checklist file
        <input
          aria-label="Project checklist file"
          type="file"
          accept=".json"
          disabled={disabled || busy}
          onChange={(e) => load(e.target.files?.[0])}
        />
      </label>
      {error && <p role="alert">{error}</p>}
      {match && (
        <>
          <p role="status">Checklist {match.status}</p>
          <ul>
            {match.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </>
      )}
      {checklist && (
        <>
          <h3>
            {checklist.name} · revision {checklist.revision}
          </h3>
          <code>{match?.checklist_id}</code>
          <p>
            Runtime: {checklist.runtime} · target: {checklist.module} · export:{" "}
            {checklist.export || "module function"}
          </p>
          {checklist.requirements.map((r: any, i: number) => (
            <article key={i}>
              <h4>{r.statement}</h4>
              <p>{r.expected_behavior}</p>
              <p>Supported inputs: {r.input_domain}</p>
              <blockquote>{r.provenance.excerpt}</blockquote>
              <p>{r.provenance.reference}</p>
              <p>{r.provenance.justification}</p>
              <pre>
                {JSON.stringify(
                  { assumptions: r.assumptions, ambiguities: r.ambiguities },
                  null,
                  2,
                )}
              </pre>
            </article>
          ))}
          <details>
            <summary>Complete checklist, commands and declared checks</summary>
            <pre>{JSON.stringify(checklist, null, 2)}</pre>
          </details>
          <label>
            <input
              type="checkbox"
              aria-label="Approve checklist requirements"
              checked={reviewed}
              disabled={disabled || busy || match?.status !== "compatible"}
              onChange={(e) => setReviewed(e.target.checked)}
            />
            I reviewed this checklist's requirements, justification, supported
            inputs, commands and expected results independently of this patch.
          </label>
          <button
            disabled={
              disabled || busy || !reviewed || match?.status !== "compatible"
            }
            onClick={prepare}
          >
            Prepare checklist plans for review
          </button>
        </>
      )}
      <p>
        To create a checklist, configure the ordinary and independent checks
        below, then choose “Download reusable project checklist”. Checklists
        contain declarations and preserve no execution approvals.
      </p>
    </section>
  );
}
