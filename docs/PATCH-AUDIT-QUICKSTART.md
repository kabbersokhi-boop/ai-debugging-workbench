# Your first Patch Audit

Use the recorded viewer to inspect evidence without installing anything:
<https://ai-debugging-workbench-recorded.vercel.app/>. It has no execution or import authority.
The G4 candidate interface is validated locally; this milestone does not update that public URL.

## Start the private local application

Prerequisites: Git, Docker with Compose, sufficient space for the pinned browser/Python/Node
images, and a trusted local owner. Image building and the trusted API’s repository intake/PR
preview require outbound network access to their package sources and GitHub respectively. Candidate
execution containers remain network-disabled. Linux is the tested environment. No model key is needed for Patch Audit.

```sh
git clone https://github.com/kabbersokhi-boop/ai-debugging-workbench.git
cd ai-debugging-workbench
# For the unmerged G4 review candidate:
git switch feature/generalized-patch-audit-g04
docker compose up --build -d --wait api
```

Open <http://127.0.0.1:8010/> and choose **Audit a completed patch**. This is a privileged local
execution stack. Do not expose it to the internet. Use a disposable isolated VM for adversarial
source; container isolation is not a complete hostile-code sandbox.

## A small reproducible Python audit

This uses the already accepted G2 positive example, not a new experiment. The patch is a scoped
portion of a historical developer change, not an AI-generated submission. Read the complete
[frozen example declaration](../evaluation/repository-examples/g2/examples.json) and
[exact patch](../evaluation/repository-examples/g2/python-positive.patch).

1. **Repository.** Enter `hynek/first` and immutable commit
   `106ee3cf389cf2bb76f2816bf22a845c44275f94`. Select **Fetch source for review**.
   Review the recomputed source identities, file budget and license.
2. **Patch.** Approve only `first.py` in the production scope selector. Upload
   `evaluation/repository-examples/g2/python-positive.patch`, then select **Admit patch for review**.
   Inspect the exact diff. No execution has occurred.
3. **Existing tests.** Select Python 3.12. Leave offline setup `[]` and working directory `.`.
   Set test command arguments to `["python", "-m", "pytest", "-q", "test_first.py"]`.
   Describe the scope as the unchanged upstream test file. Select **Prepare exact plan for approval**.
4. **Independent requirements.** Check **Add independently specified behavioral verification**.
   Use the guided form for a single requirement, or **Advanced JSON** for the complete declaration.
   The accepted requirement is: with `key` omitted, return the first truthy iterable element,
   or `None` when none exists. The source is the README at this exact base revision.
   Copy the `python-positive` entry's `requirement` as a single-element JSON array into
   **Independent requirements** to preserve its exact excerpt, assumptions and justification.
   The UI recomputes the excerpt hash. Review the provenance approval checkbox yourself.
5. Set the independent target to `first.py`, public function export to `first`. In the guided form,
   add named examples with the declared argument arrays and expected JSON results:

   | Name | Function arguments | Expected JSON result |
   | --- | --- | --- |
   | `string_truthy` | `[[0, false, "ready", 42]]` | `"ready"` |
   | `negative_truthy` | `[[0, -7, 2]]` | `-7` |
   | `all_false` | `[[0, false, null, []]]` | `null` |
   | `empty` | `[[]]` | `null` |

   The contract comes from exact-base upstream documentation. These concrete JSON examples were
   owner-specified independently of the candidate, using that contract and Python truthiness.
   Switch back to guided mode after editing advanced requirement details if desired.
6. **Controls and approval.** Prepare the independent plan. Inspect its exact requirements,
   function, inputs, expected values, limits and identities. Explicitly authorize positive/negative
   synthetic controls, then select **Validate independent checker**. This starts real restricted
   local execution. Controls check the adapter and assertions, not the truth of the specification.
   After successful validation, approve the exact independent plan. Finally approve the exact
   source, patch and ordinary plan, and select **Run ordinary and independent checks**.
7. **Evidence.** Ordinary tests and independent outcomes remain separate. A passing outcome says
   **Passed the declared checks**, not universally correct or safe. Open expected/observed values,
   provenance and command output. Select **Download repository evidence** and **Download exact
   repository patch**. Copy the saved link or navigate away and reopen **Saved repository audit
   history**. Reopening reads saved evidence and does not execute the candidate again.

Without a trustworthy requirement, leave independent verification disabled. The result will say
**Independent checks not configured**, even when ordinary tests pass. Editing any bound input
requires preparing/approving the changed plan; old approval does not authorize new bytes.

## Try the accepted Node example

Use `component/escape-html` at `b42947eefa79efff01b3fe988c4c7e7b051ec8d8`, the immutable source in the
frozen `node-positive` declaration. Approve `index.js`, upload `node-positive.patch`, select Node 22, and use
`["node", "/opt/test-tools/node_modules/mocha/bin/mocha.js", "test/index.js"]`.
Use the exact Node requirement, function/module and four expected JSON examples from that entry.
Create fresh control validation and exact approval; historical validation IDs are not reusable
authorization, and retired verifier versions remain history-only.

## PR links and unsupported inputs

Expand **Start from a public GitHub pull request** and enter a canonical URL such as
`https://github.com/owner/repository/pull/123`. The local preview reads public metadata only,
shows observed base/head SHAs and counts, and admits no source or patch. Private/deleted heads,
redirects, rate limits and invalid URLs fail visibly. The PR can change after preview. Its base
tip may differ from its diff's merge-base; deliberately choose the immutable source and a
compatible production-only patch for manual intake. Preview values are not recomputed source
or candidate identities, and never authorize execution.

Tests/configuration changes, new/deleted files, unsupported paths, excessive source budgets,
missing offline dependencies and incompatible runtime behavior remain unsupported. Intake
restrictions apply equally to manual and PR-inspired workflows. No green result substitutes
for rejected, invalid, interrupted or infrastructure evidence.

## Inspect rather than execute

For the authentic AI missed-copy case, open **Recorded examples** and select the retained
Boltons development repair. Ordinary checks passed; the standalone copy failed independent
checks. Related assertion failures describe one defect. The G3 research panels in the private
repository workspace retain separate original/addendum evidence and their honest zero-additional-
discovery result. Neither replay starts execution.

Stop local services with `docker compose down`; saved volumes remain. `down -v` deletes local
history. For contributor checks see [README](../README.md) and the
[G4 engineering report](reports/GENERALIZED-PATCH-AUDIT-G04.md).
