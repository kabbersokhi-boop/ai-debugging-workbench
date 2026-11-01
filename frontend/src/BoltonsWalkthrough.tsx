import { useState } from "react";

type Check = {
  name: string;
  status: string;
  expected: unknown;
  observed: unknown;
};
export default function BoltonsWalkthrough({
  checks,
  patch,
}: {
  checks: Check[];
  patch: string;
}) {
  const [step, setStep] = useState(0);
  const empty = checks.find((c) => c.name === "standalone_urlutils:empty");
  const titles = [
    "The selected tests passed",
    "A second implementation was overlooked",
    "Empty input exposes the incomplete repair",
  ];
  return (
    <section
      id="guided-boltons"
      className="evaluation-panel guided-playback"
      aria-label="Guided Boltons walkthrough"
    >
      <span className="eyebrow">SAVED PLAYBACK · NO FRESH EXECUTION</span>
      <nav aria-label="Boltons walkthrough steps">
        {titles.map((title, i) => (
          <button
            key={title}
            aria-current={step === i ? "step" : undefined}
            onClick={() => setStep(i)}
          >
            {i + 1}. {title}
          </button>
        ))}
      </nav>
      <article aria-live="polite" aria-atomic="true">
        <p>Step {step + 1} of 3</p>
        <h2>{titles[step]}</h2>
        {step === 0 && (
          <>
            <p>
              <strong>What passed:</strong> 155 selected existing tests. They
              exercised normal package imports, which use the repaired
              implementation in <code>boltons/dictutils.py</code>.
            </p>
            <p>
              A green result establishes the selected suite passed in the saved
              environment. The standalone implementation still needed checking.
            </p>
          </>
        )}
        {step === 1 && (
          <>
            <p>
              The patch changed <code>boltons/dictutils.py</code>. It left the
              required standalone copy in <code>boltons/urlutils.py</code>{" "}
              unchanged.
            </p>
            <pre className="walkthrough-code">{patch}</pre>
            <p>
              <strong>Why it matters:</strong> standalone mode uses the omitted
              copy, so callers can still encounter the original defect.
            </p>
          </>
        )}
        {step === 2 && (
          <>
            <p>
              <strong>What failed:</strong> the independently specified
              empty-input check for the standalone copy. Empty input should
              leave length zero; the saved observation reports length one while
              keys and items are empty.
            </p>
            <dl className="observation-pair">
              <div>
                <dt>Expected behavior</dt>
                <dd>
                  <pre>{JSON.stringify(empty?.expected, null, 2)}</pre>
                </dd>
              </div>
              <div>
                <dt>Actual behavior</dt>
                <dd>
                  <pre>{JSON.stringify(empty?.observed, null, 2)}</pre>
                </dd>
              </div>
            </dl>
            <p>
              Related failed assertions describe one incomplete repair. Passing
              remains limited to the declared checks.
            </p>
            <a href="#saved-patch-evidence">
              Inspect the complete result, logs, provenance and downloads below
            </a>
          </>
        )}
      </article>
      <div className="walkthrough-controls">
        <button disabled={step === 0} onClick={() => setStep(step - 1)}>
          Previous
        </button>
        <button disabled={step === 2} onClick={() => setStep(step + 1)}>
          Next
        </button>
      </div>
    </section>
  );
}
