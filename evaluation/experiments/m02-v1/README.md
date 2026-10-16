# M2 controlled comparison v1

Frozen before comparison generation. The immutable procedure is `freeze.json`.
The accepted M1 engine and original evidence are unchanged. Both model configurations use
identical structured source inspection, exact production edits, and fixed ordinary-test tools.
No producer filesystem or tool reaches the evaluator repository, controls, references, independent
checks, expected matrices, previous candidates, or scoring records. The trusted coordinator owns
credentials. Source execution uses M1's restricted Docker adapter.

Twenty-four generation trials run sequentially in the pre-randomized order. Independent scoring
starts only after all generation terminates. No reruns, automatic provider retries, or budget
replenishment. An interrupted generation remains an incomplete raw prefix; do not restart its ID.
A final comparison requires all frozen coordinates. Existing completed scores may be read after
validation; an interrupted scoring claim becomes infrastructure failure and is never executed again.

Development availability and capability attempts are retained in `smoke/` and excluded from the
comparison denominator. See its `notes.json`, including an interrupted initial tool-schema probe.
Validation folders retain prefreeze control iterations; only `validation-final-v2/` is bound in
this freeze. No task selection used compared-producer outcomes.

Commands (from repository root):

```sh
uv run --project backend python -m workbench.evaluator.experiment_cli generate --live
uv run --project backend python -m workbench.evaluator.experiment_cli score
uv run --project backend python -m workbench.evaluator.experiment_cli import
uv run --project backend python -m workbench.evaluator.experiment_cli summary
uv run --project backend python -m workbench.evaluator.experiment_cli reproduce <approved-candidate-id>
```

`generate` makes genuine NVIDIA requests using existing coordinator credentials. All other commands
need no provider credentials. Reproduction runs current approved source in a fresh local container
and records the actual runtime identity. The original evaluation wrapper binds source identity
separately from trial/configuration/transcript identity, so identical patches remain traceable.

Each trial retains an exclusive claim, hash-chained request intents/responses/tool actions and
terminal event, final generation record, optional exact candidate, scoring claim, and result wrapper.
The database imports immutable validated snapshots into `agent_comparison_trials` and stores final
executions in the existing `agent_evaluations` history. No web endpoint starts inference or accepts
arbitrary inputs. In-process Python observations are not a complete anti-tampering boundary.
