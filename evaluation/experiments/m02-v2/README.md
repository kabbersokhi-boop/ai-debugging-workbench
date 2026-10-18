# M2 reliability pass — readiness failed; no formal comparison

Four fixed development journeys completed: Nemotron 3 submitted 1/2; Nemotron 3.5 submitted 0/2.
The other three reached the 12-request ceiling. All 43 responses were nontruncated with reported
reasoning tokens zero; provider errors and retries were zero. Reported usage: 245,336 tokens;
unknown usage: zero requests; monetary cost unknown. Reservations: 760,354 of 4,320,000.

The actual readiness gate refused to create a formal freeze. No newer-task formal call was made.
Do not run more preflights, replenish this pass or create replacement trials. This pass is stopped.
See `preflight-summary.json` and the correction report for all results and limitations.
One explicit development submission receives separate fresh independent evidence under
`development/independent/`; this is excluded from formal experiment metrics. Unsubmitted trees remain unscored.

The original m02-v1 remains immutable. This folder holds a distinct procedure.
Development is fixed to two calibration journeys per configuration (four runs), never the newer tasks.
Only if both configurations explicitly submit an inspected, edited, ordinary-passing calibration tree
may the frozen two-newer-task × two-configuration × two-trial experiment start (eight runs).
No retry beyond the single declared transient retry per run; all attempts are charged and retained.
No new models, replacement runs, independent feedback during generation, automatic submission, or M3.

Campaign ceilings include development: 12 runs, 144 actual request attempts, 4,320,000 conservative
reservations, 8,640 seconds of allocated generation wall. Each run reserves 720 wall seconds and
360,000 byte-plus-output units; ordinary tools are admitted only with 30 seconds left for the fixed
25-second executor. Docker cleanup/daemon responsiveness remains an inherited limitation.

The development draft freeze is retained from before offline review; no provider calls used it.
The final development freeze binds the tested source after those deterministic corrections.
Provider monetary cost is unknown. Failed and cancelled requests retain unknown usage and full
conservative charges. Commands require --live explicitly for preflight/generate; inspection/scoring do not.
