export default function GeneratedEvidence({
  result,
  verification,
}: {
  result: any;
  verification: any;
}) {
  const c = result.counterexample;
  const req = verification?.requirements?.find(
    (r: any) => r.id === c?.requirement_id,
  );
  return (
    <section
      className="evaluation-panel"
      aria-label="Generated failure evidence"
    >
      <h3>Generated Python checks · verifier v3</h3>
      <p>{result.limitations}</p>
      <p>
        Property: <code>{result.search?.property}</code> · seed{" "}
        {result.search?.seed} · up to {result.search?.cases} cases · up to{" "}
        {result.search?.reduction_rounds} reduction rounds.
      </p>
      {c ? (
        <>
          <h4>Reproduced failing input</h4>
          <p>{req?.statement}</p>
          <p>
            <strong>Why this matters:</strong> {req?.provenance.justification}
          </p>
          <div className="observation-pair">
            <article>
              <h4>Input</h4>
              <pre>{JSON.stringify(c.input, null, 2)}</pre>
            </article>
            <article>
              <h4>Expected behavior</h4>
              <pre>{JSON.stringify(c.expected, null, 2)}</pre>
            </article>
            <article>
              <h4>Actual observation</h4>
              <pre>{JSON.stringify(c.observed, null, 2)}</pre>
            </article>
          </div>
          <p>
            {c.reduced
              ? "A simpler failing input was retained."
              : "The retained failure was not reduced further within the approved budget."}{" "}
            Confirmed in {c.fresh_reproductions} fresh environments. No globally
            smallest input claim.
          </p>
          <details>
            <summary>Original failure and reproduction declaration</summary>
            <pre>{JSON.stringify(c, null, 2)}</pre>
            <p>
              Use the local CLI generated-prepare command with --replay-audit
              and this exact source and patch, then review fresh controls and
              approve the new exact plan.
            </p>
          </details>
        </>
      ) : (
        <p>
          {result.status === "completed"
            ? "Passed the declared generated cases only. No universal correctness claim."
            : "No reproducible reduced counterexample was established. Inspect the outcome and execution evidence."}
        </p>
      )}
      <details>
        <summary>Complete generation, reduction and reproduction trace</summary>
        <pre>{JSON.stringify(result.generated_runs, null, 2)}</pre>
      </details>
    </section>
  );
}
