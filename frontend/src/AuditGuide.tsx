import {
  ArrowRight,
  FileCheck2,
  GitPullRequest,
  ShieldCheck,
} from "lucide-react";

export function AuditIntro({
  recorded = false,
  repository = false,
}: {
  recorded?: boolean;
  repository?: boolean;
}) {
  return (
    <>
      <nav
        className="evaluation-nav product-nav"
        aria-label="Patch Audit navigation"
      >
        <a className="product-brand" href={recorded ? "/recorded/" : "/"}>
          <FileCheck2 size={24} />
          <strong>Patch Audit</strong>
        </a>
        <div>
          <span className="mode-badge">
            {recorded ? "Recorded viewer" : "Local owner"}
          </span>
          <a
            href={
              recorded
                ? "/recorded/?workspace=debugger"
                : "/?workspace=debugger"
            }
          >
            Debugger
          </a>
          {!recorded && <a href="/recorded/">Recorded examples</a>}
          <a href="https://github.com/kabbersokhi-boop/ai-debugging-workbench#readme">
            Documentation ↗
          </a>
        </div>
      </nav>
      <header className="evaluation-intro product-intro">
        <span className="eyebrow">
          {recorded
            ? "REAL SAVED EVIDENCE · NO LIVE EXECUTION"
            : "COMPLETED CODE CHANGES · REPRODUCIBLE EVIDENCE"}
        </span>
        <h1>
          {recorded
            ? "Passing tests. What do they prove?"
            : repository
              ? "Audit a completed patch"
              : "A patch is more than a green test run."}
        </h1>
        <p className="product-lead">
          Examine a completed code change. Run its selected existing tests,
          separately check approved behavioral requirements, and keep the
          evidence behind each conclusion.
        </p>
        {recorded ? (
          <p>
            This is a recorded evidence viewer, not a public evaluation service.
            Explore authentic saved results below. New audits require the
            private local application and Docker.
          </p>
        ) : (
          <>
            <p>
              Python 3.12 and Node.js 22 · bounded, offline execution · explicit
              local owner approval · no model call required
            </p>
            {!repository && (
              <a
                className="primary-button product-cta"
                href="/?source=external"
              >
                Audit a completed patch <ArrowRight size={17} />
              </a>
            )}
          </>
        )}
        {recorded && (
          <a
            className="primary-button product-cta"
            href="#saved-patch-evidence"
          >
            Inspect the saved audit <ArrowRight size={17} />
          </a>
        )}
        <div className="product-principles">
          <article>
            <GitPullRequest size={20} />
            <h2>Start with the actual change</h2>
            <p>
              Pin source and patch identities. Importing a patch never
              authorizes execution.
            </p>
          </article>
          <article>
            <ShieldCheck size={20} />
            <h2>Specify what matters</h2>
            <p>
              Independent checks need a trustworthy requirement. Confidence
              alone is not an oracle.
            </p>
          </article>
          <article>
            <FileCheck2 size={20} />
            <h2>Read the evidence</h2>
            <p>
              Ordinary tests and independent checks stay separate. Missing
              checks never mean a pass.
            </p>
          </article>
        </div>
      </header>
    </>
  );
}

export function AuditSteps({ step }: { step: number }) {
  const stages = [
    ["Repository", "repository-source"],
    ["Patch", "repository-patch"],
    ["Existing tests", "repository-tests"],
    ["Independent requirements", "repository-requirements"],
    ["Approval", "repository-approval"],
    ["Evidence", "repository-evidence"],
  ];
  return (
    <nav className="audit-steps" aria-label="Audit workflow">
      <ol>
        {stages.map(([name, id], i) => (
          <li key={id} aria-current={step === i ? "step" : undefined}>
            <a href={`#${id}`}>
              <span>{i + 1}</span>
              {name}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function StudyContext() {
  return (
    <section
      className="evaluation-panel study-context"
      aria-label="Evidence provenance"
    >
      <span className="eyebrow">WHAT THESE EXAMPLES ESTABLISH</span>
      <h2>Real evidence, with the boundaries intact.</h2>
      <p>
        The Boltons missed-copy case below is a genuine retained AI-generated
        patch from a separate development run. Its related failing observations
        describe one incomplete repair.
      </p>
      <div className="evaluation-phases">
        <article>
          <h3>Separate Boltons development evidence</h3>
          <p>
            155 selected ordinary tests passed; independent checks exposed the
            overlooked standalone copy. Generation procedures differed; this is
            not a model ranking.
          </p>
        </article>
        <article>
          <h3>G3 historical developer patches</h3>
          <p>
            Six distinct historical candidates evaluated. Five passed selected
            ordinary tests; one regression was already caught by ordinary tests.
            Zero additional independent discoveries. No broad accuracy or
            false-positive estimate.
          </p>
        </article>
      </div>
      <p>
        Authored controls validate mechanisms and are labeled separately.
        Replaying saved evidence creates no fresh execution or new finding.
      </p>
      <a href="https://github.com/kabbersokhi-boop/ai-debugging-workbench/blob/9c025a37cc4a01d86ce0af599776a73a07b2bc16/docs/reports/GENERALIZED-PATCH-AUDIT-G03-COMPATIBILITY.md">
        Read the G3 methodology and limitations ↗
      </a>
    </section>
  );
}
