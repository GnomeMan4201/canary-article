# Main study results audit

Independent internal audit of the completed `main-01` cohort, performed on 2026-10-30. This audit used saved evidence and did not make model calls or change the frozen experiment. Pilot and calibration records are excluded from the counts below.

## Verdict

The final records agree with the frozen 30-attempt plan. All 30 attempts completed and passed the specified build, baseline-rule, new-operation-rule, and feature checks. All 15 marker-condition final responses matched exactly. No missing results, unobserved final responses, timeouts, runtime errors, evaluator errors, or unevaluable behavioral outcomes were recorded.

| Task | Condition A attempts | Condition B attempts | Feature and rule checks passed |
| --- | --- | --- | --- |
| Reschedule | 5 | 5 | 10 of 10 |
| Availability | 5 | 5 | 10 of 10 |
| Batch | 5 | 5 | 10 of 10 |
| Total | 15 | 15 | 30 of 30 |

## Marker and behavior observations

The following table includes only the 15 marker-condition runs. Condition A's marker status is not applicable; it is not a missing marker.

| Marker observation | Rule checks pass | Rule checks fail |
| --- | --- | --- |
| Exact marker | 15 | 0 |
| Noncompliant marker | 0 | 0 |

There were zero malformed markers, absent markers, or unobserved final responses in condition B. The observed rule-failure fraction among exact-marker runs is 0/15. The failure fraction among noncompliant-marker runs and the warning fraction among rule-failing runs both have zero denominators and are undefined.

The marker never varied and no checked rule failed. This study therefore cannot assess whether the marker distinguishes passing from failing behavior or detects a rule violation. Both conditions passed all specified feature and rule checks; that observation does not establish that adding a marker improves reliability, that the conditions are generally equivalent, or that the code is universally correct. These final-response observations do not establish early warning, context retention, or recovery effectiveness.

## Evidence verification

- Matched all 30 result IDs and attempt records to the frozen plan, with no unexpected run directories; each task/condition combination has five attempts.
- Verified each attempt began after the dated plan freeze and that recorded task, condition, repetition, block, and token agree with the plan.
- Re-extracted all 30 final responses from saved event streams, matched them to saved final text, and reproduced all marker scores. No malformed event lines were found.
- Confirmed the 15 marker tokens are unique 16-character lowercase hexadecimal strings, appear in their saved instruction files, and are absent from their task prompts.
- Recomputed 120 submitted-file hashes across all 30 snapshots; every hash matched its run record. No snapshot paths were recorded as rejected or redacted.
- Matched each embedded evaluation to its saved evaluation file and raw evaluator JSON. Agent and evaluator process records confirm cleanup without output truncation; evaluator records show no timeouts.
- Recomputed all 20 archived source hashes and matched them to the frozen plan. The current frozen-source fingerprint also matches the plan at audit time.

Refusal classification is recorded as `not_inferred` for all 30 runs; this audit does not convert that field into a separately measured refusal rate. Instruction-loading evidence and the provider backend revision remain unavailable. The recorded model alias and configuration identify the requested setup, not a pinned provider backend revision.

The authoritative evidence is the [frozen plan](../artifacts/main-01/plan.json), its [archived source](../artifacts/main-01/source/), and the [saved run records](../artifacts/main-01/runs/). The audit found no accounting, rescoring, or integrity discrepancy. It verifies the recorded results and their limits; it is not an external peer review or an independent rerun of the model experiment.
