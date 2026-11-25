# Canary Lab review and decisions

Three AI reviewers independently assessed the proposal from software engineering, experimental methods, and dev.to editorial perspectives. This is an internal design review, not external peer review or empirical validation. No implementation or agent trials were performed during the review.

## Initial decision

Proceed with the project as a small, reproducible case study. Build and calibrate the evidence pipeline before main trials or visual polish. The design is ready to guide implementation; it is not ready for main data collection.

## Findings and responses

| Finding | Review perspectives | Decision |
| --- | --- | --- |
| Marker wording allowed prose on the first line while the scorer prohibited it | Engineering, methods | Align instruction and parser; specify normalization and malformed-marker reporting |
| Named tasks lacked a callable API and error contract | Engineering, methods | Make the public contract and reference solutions prerequisites for evaluation |
| Baseline checks could pass when a new feature was absent | Engineering | Separate existing-operation, new-operation, and feature-completion results |
| Tests outside the fixture might still be readable by the agent | Engineering, methods | Require tested isolation and separate post-run evaluation |
| Final outcomes cannot establish early warning, recovery effectiveness, or best techniques | All three | Narrow the first study to a descriptive relationship and label operating advice separately |
| A constant marker or all-passing code would make diagnostic interpretation impossible | Engineering, methods, editorial | Predefine that interpretation and retain uninteresting outcomes |
| Restricting analysis to evaluable runs could hide failures | Methods, engineering | Lead with all-run accounting and publish unavailable outcomes and denominators |
| Pilot, completion, and retry policies were unspecified | Engineering, methods | Separate pilots; freeze 30 main attempts with no automatic replacements |
| The editorial plan preferred a dramatic disagreement before collection | Editorial | Select the opening after classifying all results and report its frequency |
| An animated bird is already prior art; a timeline exceeds available measurements | Editorial, engineering | Make the rerunnable evidence package the contribution; begin with a run matrix |

The corresponding decisions have been incorporated into the [project brief](../README.md) and [experiment protocol](experiment.md). The fragment notebook retains earlier speculative passages as exploration history; the revised editorial brief governs the article.

## Engineering build sequence

1. Specify the minimal synchronous booking API, task prompts, and observable error behavior.
2. Implement the baseline, three reference solutions, and calibration fixtures containing deliberate defects.
3. Implement independent behavioral checks, marker parsing, and explicit outcome classification.
4. Implement one agent runner adapter with tested isolation and replayable evidence capture.
5. Run separate pilots, correct infrastructure or specification problems, and freeze the main study.
6. Execute the fixed main matrix and generate a static report from saved records.
7. Build the visual explorer around real evidence, then draft the article around the observed results.

## Editorial commitments

The reader should leave with one concrete marker technique, an understanding of what was actually measured, and a way to repeat the comparison. Keep four observations distinct: instruction-loading evidence, marker adherence, tested behavior, and feature completion.

An absent marker does not establish forgotten instructions. A failed behavioral check does not establish that the instructions were unavailable. A marker that appears does not approve a code change. Present these as limits of the observations, not discoveries that prior canary authors overlooked.

All main outcomes are publishable. An opening about marker/check disagreement needs its observed frequency. An opening about universal marker compliance must explain why the experiment could not assess discrimination. A result in which warnings and failures align does not establish that warnings came first.

Keep the mining history to a short, sourced passage. It motivates a question about signals and responses; it cannot answer that question for coding agents.

## Decisions left by the initial review

At the initial design review, the implementation language, agent configuration, API contract, prompts, limits, and checks still required selection and validation; the implementation round below addresses them. The review does not assert a sample-size guarantee or broad reliability. Only 15 of the 30 planned main attempts include a marker. Any larger or longitudinal study requires a separately stated scope and protocol.

## Implementation review and pilot validation

The implementation now uses Python standard-library fixtures and a Codex CLI adapter in an unprivileged Docker container. An engineering review identified four additional evidence-handling issues: redaction could change evaluated source, replay did not verify saved snapshots, event parsing could retain a stale answer, and cleanup errors could hide process evidence. The implementation was corrected and regression checks added. The runner also limits captured process output, validates evaluator result schemas, archives source bytes, and records unavailable final responses.

The first live pilot exposed a missing native execution helper. The completed attempt emitted the marker but could not implement its task; the following attempt was interrupted when collection was stopped. Both remain in [pilot-01](../artifacts/pilot-01/amendment-dated.json). The replacement runtime mounts and fingerprints the native helper and resource bundle alongside the CLI.

All 16 container calibration cases passed their expected outcomes after that repair. All six [replacement pilot attempts](../artifacts/pilot-02/report/report.html) completed and passed the independent feature and rule checks; the three marker-enabled responses matched exactly. A saved pilot evaluation was replayed with identical results.

Engineering and experimental-methods reviewers independently inspected the corrected pilot evidence and approved freezing the unchanged main configuration. Their [readiness record](../artifacts/pilot-02/readiness-review.json) distinguishes observed explicit instruction-file reads from unavailable automatic-injection diagnostics. The runtime has no Git executable; this is recorded, and the controller independently produces code diffs. Uniform passing pilot outcomes validate the workflow, not the canary's ability to distinguish failures.

## Completed main study

All thirty planned main attempts completed; all independent feature and rule checks passed, and all fifteen marker-enabled responses matched exactly. The [final methods audit](results-audit.md) reproduced response and marker scores and verified the archived source and submission hashes. The editorial review confirmed that the article separates the failed runtime pilot from main evidence and does not infer diagnostic value from uniform passing outcomes.

The evidence explorer was added after collection as a separate presentation layer. It does not alter the frozen controller, evaluator, or run records. The article was later published on dev.to on 2026-11-24.

## Post-publication feedback

Reader comments raised several points, and each change below responds to one of them. Replies go in the comment thread, not in an article edit. None alters the frozen controller, evaluator, scoring, or saved run records.

| Feedback | Change |
| --- | --- |
| A canary present while work is blocked should be classified separately. | The report adds a **signal-versus-work** table: marker status × feature completion for every recorded condition B run, including runs whose rules are unevaluable. The four-cell rule table excludes those runs. Report schema version 2. pilot-01 is the one observed case: exact marker, feature incomplete. main-01 has 0 of 15. |
| 30/30 green says nothing about failure. What comes next: a different model or harder tasks? | [Draft follow-up protocol](follow-up-protocol.md) with one factor per arm. Revised 2026-11-25 after a [literature review](../reports/Canary%20Lab%20research%20foundations.md): evaluator hardening and a main-01 re-score first, then instruction load, a repeated in-code marker and a conflict arm, then effort, model and tasks, an equal-length neutral-instruction condition, and a runtime negative control. Not frozen; no data collected. |
| The marker instruction itself might change behavior. | Condition C (`--conditions ABC`): a neutral instruction matched to the marker's length that asks for no observable output. Runner, report, explorer, and tests. |
| Use a negative control so "canary present, work blocked" is caught on purpose. | `plan-control`: one marker run per task with a read-only workspace. The report fails the control if any run counts as complete work. |
| Interest in independent replication and extension. | [Replication guide](replicating.md). |
| CONTRIBUTING said the canary "WORKS". | Reworded to the narrower claim: the marker format was followed in 15 of 15 runs. |

Step 0 of the follow-up protocol hardened the evaluator, adding planted-bug scoring, seeded randomized checks against a trusted oracle, and one new fixed check. It then re-scored main-01: all 30 submissions still pass, so the published result stands. See [Step 0 results](follow-up-protocol.md#step-0-results-2026-11-25).

The first negative-control cohort, [control-01](../artifacts/control-01/amendment.json), is void. All three attempts hit a provider usage limit before the agent ran. Its first report still marked the control as passing, because untouched code fails the feature check by default. The report now marks a control inconclusive unless every run produced a final response. The replacement is control-02.

The report change modifies `lab/report.py`, which is part of the source fingerprint. Any future main freeze therefore needs a new pilot and fresh calibration, as the runner enforces. The main-01 replay uses its archived source and is unaffected. The `deliverables/` v1 bundle is the hashed release snapshot and keeps the schema-1 reports.
