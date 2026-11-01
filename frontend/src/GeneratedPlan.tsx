import { useEffect, useRef, useState } from "react";
import { api } from "./types";
import type { IndependentApproval, PreparedExample } from "./IndependentPlan";

export default function GeneratedPlan(p: {
  snapshotId: string;
  candidateId: string;
  candidateHash: string;
  ordinaryPlanId: string;
  imageId: string;
  prepared?: PreparedExample;
  requirement?: any;
  target?: { module: string; export: string; setup: string[][] };
  disabled: boolean;
  onChange: (v: IndependentApproval | null) => void;
  onBusy: (v: boolean) => void;
}) {
  const initial = p.requirement ?? p.prepared?.requirement;
  const [statement, setStatement] = useState(initial?.statement ?? "");
  const [domain, setDomain] = useState(initial?.input_domain ?? "");
  const [excerpt, setExcerpt] = useState(initial?.provenance.excerpt ?? "");
  const [reference, setReference] = useState(
    initial?.provenance.reference ?? "",
  );
  const [justification, setJustification] = useState(
    initial?.provenance.justification ?? "",
  );
  const [module, setModule] = useState(
    p.target?.module ?? p.prepared?.module ?? "",
  );
  const [exportName, setExport] = useState(
    p.target?.export ?? p.prepared?.export ?? "",
  );
  const [property, setProperty] = useState("first_truthy");
  const [atoms, setAtoms] = useState('[0,false,null,"ready","a",1,-1]');
  const [seed, setSeed] = useState(1),
    [cases, setCases] = useState(16),
    [rounds, setRounds] = useState(4);
  const [approved, setApproved] = useState(false),
    [controlsApproved, setControlsApproved] = useState(false);
  const [plan, setPlan] = useState<any>(null),
    [validation, setValidation] = useState<any>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const epoch = useRef(0);
  useEffect(
    () => () => {
      epoch.current++;
    },
    [],
  );
  function invalidate() {
    epoch.current++;
    setApproved(false);
    setPlan(null);
    setValidation(null);
    setControlsApproved(false);
    setError("");
    p.onChange(null);
  }
  async function prepare() {
    if (!approved) return;
    const token = epoch.current;
    setBusy(true);
    p.onBusy(true);
    setError("");
    try {
      const hash = Array.from(
        new Uint8Array(
          await crypto.subtle.digest(
            "SHA-256",
            new TextEncoder().encode(excerpt),
          ),
        ),
        (b) => b.toString(16).padStart(2, "0"),
      ).join("");
      const requirement = await api<{ id: string }>(
        "/repository-audits/requirements",
        {
          method: "POST",
          body: JSON.stringify({
            version: "behavioral-requirement-v1",
            snapshot_id: p.snapshotId,
            statement,
            expected_behavior: statement,
            input_domain: domain,
            assumptions: [
              ...(initial?.assumptions ?? []),
              "Deterministic stateless Python function on the approved finite JSON domain",
            ],
            ambiguities: [],
            approval: "owner_approved",
            provenance: {
              origin: initial?.provenance.origin ?? "owner_authored_property",
              reference,
              excerpt,
              excerpt_hash: hash,
              justification,
              independent_of_candidate: true,
            },
          }),
        },
      );
      const created = await api<any>("/repository-audits/generated-plans", {
        method: "POST",
        body: JSON.stringify({
          snapshot_id: p.snapshotId,
          candidate_id: p.candidateId,
          candidate_hash: p.candidateHash,
          ordinary_plan_id: p.ordinaryPlanId,
          image_id: p.imageId,
          module,
          export: exportName,
          setup: p.target?.setup ?? [],
          requirement_id: requirement.id,
          property_approval: "owner_approved",
          stateless_function: true,
          search: {
            version: "bounded-json-list-v1",
            property,
            atoms: JSON.parse(atoms),
            max_length: 8,
            seed,
            cases,
            reduction_rounds: rounds,
            replay_inputs: [],
          },
        }),
      });
      if (token === epoch.current) {
        setPlan(created);
        setValidation(null);
        setControlsApproved(false);
        p.onChange(null);
      }
    } catch (e) {
      if (token === epoch.current) setError(String(e));
    } finally {
      if (token === epoch.current) {
        setBusy(false);
        p.onBusy(false);
      }
    }
  }
  async function validate() {
    if (!plan || !controlsApproved) return;
    const token = epoch.current;
    setBusy(true);
    p.onBusy(true);
    setError("");
    p.onChange(null);
    try {
      let run = await api<any>("/repository-audits/runs", {
        method: "POST",
        body: JSON.stringify({
          candidate_id: p.candidateId,
          plan_id: p.ordinaryPlanId,
          verification_id: plan.id,
          stage: "validation",
          approve_independent_plan: true,
          approve_exact_plan: true,
          confirm_local_execution: true,
        }),
      });
      while (token === epoch.current) {
        setValidation(run);
        if (run.status !== "running") break;
        await new Promise((r) => setTimeout(r, 700));
        if (token !== epoch.current) return;
        const next = await api<any>(`/repository-audits/runs/${run.id}`);
        if (next.id !== run.id) throw Error("Validation identity mismatch");
        run = next;
      }
    } catch (e) {
      if (token === epoch.current) setError(String(e));
    } finally {
      if (token === epoch.current) {
        setBusy(false);
        p.onBusy(false);
      }
    }
  }
  const disabled = p.disabled || busy;
  return (
    <section
      className="evaluation-panel audit-import"
      aria-label="Generated Python verification"
    >
      <h3>Generate bounded inputs and simplify a failure</h3>
      <p>
        Verifier v3 supports one positional JSON list of approved scalar values.
        The selected property is a trusted built-in reference behavior; review
        its justification separately from the patch. Only deterministic
        stateless Python functions are supported.
      </p>
      <label>
        Required behavior
        <input
          aria-label="Generated required behavior"
          value={statement}
          disabled={disabled}
          onChange={(e) => {
            invalidate();
            setStatement(e.target.value);
          }}
        />
      </label>
      <label>
        Supported input domain
        <input
          aria-label="Generated input domain"
          value={domain}
          disabled={disabled}
          onChange={(e) => {
            invalidate();
            setDomain(e.target.value);
          }}
        />
      </label>
      <label>
        Supporting source reference
        <input
          aria-label="Generated source reference"
          value={reference}
          disabled={disabled}
          onChange={(e) => {
            invalidate();
            setReference(e.target.value);
          }}
        />
      </label>
      <label>
        Supporting source excerpt
        <textarea
          aria-label="Generated source excerpt"
          value={excerpt}
          disabled={disabled}
          onChange={(e) => {
            invalidate();
            setExcerpt(e.target.value);
          }}
        />
      </label>
      <label>
        Why this expectation is justified
        <textarea
          aria-label="Generated justification"
          value={justification}
          disabled={disabled}
          onChange={(e) => {
            invalidate();
            setJustification(e.target.value);
          }}
        />
      </label>
      <label>
        Python target file
        <input
          aria-label="Generated target file"
          value={module}
          disabled={disabled}
          onChange={(e) => {
            invalidate();
            setModule(e.target.value);
          }}
        />
      </label>
      <label>
        Public function export
        <input
          aria-label="Generated export"
          value={exportName}
          disabled={disabled}
          onChange={(e) => {
            invalidate();
            setExport(e.target.value);
          }}
        />
      </label>
      <label>
        Approved property
        <select
          aria-label="Generated property"
          value={property}
          disabled={disabled}
          onChange={(e) => {
            invalidate();
            setProperty(e.target.value);
          }}
        >
          <option value="first_truthy">
            Return first truthy element, or None
          </option>
          <option value="integer_sum">Return the sum of integers</option>
          <option value="integer_sort">
            Return integers in ascending order
          </option>
        </select>
      </label>
      {p.target?.setup.length ? (
        <p>
          Offline setup in each observer environment:{" "}
          <code>{JSON.stringify(p.target.setup)}</code>
        </p>
      ) : null}
      <details>
        <summary>Generation and reduction limits</summary>
        <label>
          Allowed scalar palette (JSON)
          <textarea
            aria-label="Generation atoms"
            value={atoms}
            disabled={disabled}
            onChange={(e) => {
              invalidate();
              setAtoms(e.target.value);
            }}
          />
        </label>
        <label>
          Deterministic seed
          <input
            type="number"
            min={0}
            max={2147483647}
            aria-label="Generation seed"
            value={seed}
            disabled={disabled}
            onChange={(e) => {
              invalidate();
              setSeed(Number(e.target.value));
            }}
          />
        </label>
        <label>
          Generated cases
          <input
            type="number"
            min={1}
            max={32}
            aria-label="Generation cases"
            value={cases}
            disabled={disabled}
            onChange={(e) => {
              invalidate();
              setCases(Number(e.target.value));
            }}
          />
        </label>
        <label>
          Reduction rounds
          <input
            type="number"
            min={0}
            max={4}
            aria-label="Reduction rounds"
            value={rounds}
            disabled={disabled}
            onChange={(e) => {
              invalidate();
              setRounds(Number(e.target.value));
            }}
          />
        </label>
      </details>
      <p>
        Lists contain at most 8 scalar values. At most 32 generated cases, 4
        reduction rounds of 16 proposals, an original replay and two final fresh
        reproductions. Each observer environment has a 5-second command budget.
        Reduction does not prove a globally smallest input.
      </p>
      <label>
        <input
          type="checkbox"
          aria-label="Approve generated property"
          checked={approved}
          disabled={disabled}
          onChange={(e) => {
            setApproved(e.target.checked);
            setPlan(null);
            setValidation(null);
            p.onChange(null);
          }}
        />
        I reviewed the requirement and approve this property as its executable
        interpretation on this domain. The function is deterministic and
        stateless. I approve these generation and reduction limits.
      </label>
      <button disabled={disabled || !approved} onClick={prepare}>
        Prepare generated verification plan
      </button>
      {error && <p role="alert">{error}</p>}
      {plan && (
        <>
          <details>
            <summary>Exact generated plan, oracle and requirements</summary>
            <pre>{JSON.stringify(plan, null, 2)}</pre>
          </details>
          <label>
            <input
              type="checkbox"
              aria-label="Approve generated controls"
              checked={controlsApproved}
              disabled={disabled}
              onChange={(e) => setControlsApproved(e.target.checked)}
            />
            Approve positive and negative synthetic generator controls in
            separate restricted environments. Controls validate the checker, not
            the specification.
          </label>
          <button disabled={disabled || !controlsApproved} onClick={validate}>
            Validate generated checker
          </button>
        </>
      )}
      {validation && (
        <div aria-label="Generated control result">
          <p role="status">{validation.status.replaceAll("_", " ")}</p>
          {validation.status === "running" && (
            <button
              onClick={() =>
                api(`/repository-audits/runs/${validation.id}/cancel`, {
                  method: "POST",
                }).catch((e) => setError(String(e)))
              }
            >
              Cancel generated validation
            </button>
          )}
          <details>
            <summary>Generated control evidence</summary>
            <pre>{JSON.stringify(validation, null, 2)}</pre>
          </details>
        </div>
      )}
      {validation?.status === "validation_passed" && (
        <label>
          <input
            type="checkbox"
            aria-label="Approve validated generated plan"
            disabled={disabled}
            onChange={(e) =>
              p.onChange(
                e.target.checked
                  ? {
                      verification_id: plan.id,
                      validation_run_id: validation.id,
                      approve_independent_plan: true,
                    }
                  : null,
              )
            }
          />
          I reviewed successful controls and approve this exact generated plan
          for this candidate.
        </label>
      )}
    </section>
  );
}
