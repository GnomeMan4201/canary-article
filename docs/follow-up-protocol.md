# Follow-up protocol draft: main-02

Status: **draft, not frozen.** No data has been collected under this design. It responds to feedback on the published article and turns the article's stated limitations into a study that can produce a disagreement. The arm order was revised on 2026-11-25 after a [literature review](../reports/Canary%20Lab%20research%20foundations.md). The frozen [main-01 protocol](experiment.md) stays unchanged. Results from this design must be reported as a separate cohort.

## Why a follow-up

main-01 gave 30/30 passing checks and 15/15 exact markers. With no marker omission and no checked failure, every diagnostic fraction except the marker compliance rate was either undefined or showed no variation. The study showed that the marker format can be followed. It could not show whether an omission comes with a failure.

Readers asked two questions:

1. Should the next study use a different model or harder tasks?
2. Was the marker ever meant to be a warning?

On the second question: as main-01 defined it, the marker measures one thing, whether the final response complied with one instruction. Whether that compliance tracks anything else is the open question this follow-up addresses.

## Question

When checked failures occur, how often does marker noncompliance come with them, and how often does an exact marker appear alongside incomplete or failing work?

This is still a final-outcome study. It cannot establish that a marker warned *before* a failure. That needs the multi-turn design under [Not in this protocol](#not-in-this-protocol).

## Step 0: harden the evaluator and re-score main-01

This step changes no agent setting, so it is not an arm. Every major test-based coding benchmark has been found to accept wrong code. 30/30 is only as strong as the hidden checks, and 16 hand-built calibration cases is a small sample of how strong they are.

1. **Planted bugs.** Generate mutants of each reference `booking.py` aimed at the contract's risk points: `<` vs `<=` in the half-open overlap check, a dropped same-room condition, an offset sign error, state changed before raising, a partial batch commit, a missing self-exclusion in reschedule. Report how many the hidden checks catch, and turn survivors into new checks.
2. **Randomized stateful checks.** Add Hypothesis state-machine checks with the reference implementation as the oracle. Vendor them into the offline evaluator with a fixed seed and example count.
3. **Differential pass.** Compare every submission with the reference on randomized operation sequences.
4. **Re-score main-01.** Run the hardened evaluator over the 30 saved main-01 snapshots and report it as a separate, labeled re-analysis. If any snapshot now fails, the 30/30 headline gets a dated amendment, and the result is the cheapest marker/failure disagreement available.

The evaluator change alters the source fingerprint, so it must land before the first 02 pilot. Every arm then uses the same hardened evaluator.

### Step 0 results (2026-11-25)

- **Planted bugs** (`lab/mutation.py`, [report](../artifacts/mutation-step0/summary.json)): 32 mutants across all three tasks. One is equivalent: Python's `timezone()` already rejects ±24:00, so loosening the offset-hour bound changes nothing. It is excluded from the score.
  - Before hardening, the fixed checks caught 30 of the remaining 31. The survivor was a reschedule that silently moved the booking to another room.
  - The hardened evaluator catches 31 of 31. A new fixed check, `reschedule.preserves_room`, covers the survivor, and the randomized checks also catch all 31 on their own.
- **Randomized stateful and differential checks** (`evaluator/randomized.py`, `evaluator/oracle.py`). Each task runs 120 fixed-seed sequences of 18 operations. Every step is compared with a trusted oracle on:
  - acceptance;
  - returned values;
  - error codes, where any code the contract permits is accepted, since it sets no precedence;
  - stored state;
  - detachment of inputs, results and listings.

  A failure is shrunk to a minimal reproduction. These replace the planned Hypothesis checks: the evaluation container is offline and standard-library only, so a seeded standard-library generator does the same job without adding a dependency.
- **Calibration**: all 16 container calibration cases still meet their expectations under the hardened evaluator ([report](../artifacts/calibration-step0/summary.json)).
- **main-01 re-score** (`lab/rescore.py`, [report](../artifacts/main-01-rescore-step0/summary.json)): all 30 snapshots, hash-checked and evaluated in the isolated container, still pass every check. No outcome changed, and no exact-marker run now fails. The 30/30 headline stands and needs no amendment. It now rests on a stronger instrument, and Step 0 did not produce any marker/failure disagreement.

## Change one factor per arm

Changing two things at once would leave no way to attribute a new failure to either change. Each arm changes exactly one thing relative to main-01 and is reported as its own cohort.

A single isolated instruction is followed at close to 100% (IFEval, ManyIFEval), so main-01's 15/15 was the expected result. The arms are therefore ordered by how strongly the literature predicts they will move compliance below 100%. Cheapness comes second.

| Arm | Change from main-01 | Why this order |
| --- | --- | --- |
| 02a | **Instruction load:** add a fixed set of neutral, checkable rules to `AGENTS.md` (for example 25), with the marker unchanged | The strongest quantitative evidence. On ManyIFEval, GPT-4o's all-instructions accuracy fell from 0.94 with one instruction to 0.21 with ten. Tests whether marker omission and rule failure co-occur beyond what independent per-instruction rates predict. |
| 02b | **Repeated in-code marker:** a `# canary:<token>` comment required on every new or modified function, instead of one line in the final reply | The closest prior study (McMillan 2026, 1,650 Claude Code sessions) found only about 64% per-function compliance, falling with each extra function in a session. Gives many observations per run, which can be compared with the hidden checks function by function. Condition C's neutral text must be re-matched to the new instruction's length. |
| 02c | **Conflict:** the task prompt or a fixture comment mildly contradicts one published rule, and the contract says so | Instruction-hierarchy studies find even simple formatting conflicts are resolved inconsistently. Makes "exact marker, rule failed" likely by construction. |
| 02d | Reasoning effort `high` → `low` on the same model | Supported by the runner today. Its direction is **not** assumed: HAL (21,730 rollouts) found higher effort *reduced* accuracy in most runs, so lower effort may not produce failures. The comparison is two-sided. |
| 02e | A different, smaller model at `high` effort | Needs only a new pilot. |
| 02f | Harder tasks (see below), graded so the main-01 model passes about half the time | Needs a new contract, reference solutions and calibration, so it comes last. |

Run 02a first. An arm with no checked failure is a reportable result. It does **not** license escalating within the same cohort.

### Candidate harder tasks for 02f

These must be written into the contract and calibrated before any agent run. They are candidates, not commitments. Use METR's time-horizon approach to grade them: time two or three developers on each candidate, pilot the main-01 model, and keep tasks near 50% success. A task the agent always passes or always fails cannot produce a disagreement.

- Recurring reservations that expand into instances, where one conflicting instance rejects the whole series.
- Moving a booking between rooms while keeping its identity, with rollback on conflict.
- A two-file change that splits storage from validation, so the agent has to keep rules intact across a refactor.

The contract must publish every behavior the hidden checks exercise. Harder means more surface area, not surprise requirements.

## Conditions

| Condition | Instructions | Purpose |
| --- | --- | --- |
| A | Shared project rules | Control, same as main-01 |
| B | Rules plus the marker instruction | Same as main-01 |
| C | Rules plus a **neutral instruction of the same length** that asks for no observable output | Separates the marker's own effect from the cost of any extra instruction in context |

Condition C answers the article's open question about whether the marker instruction itself changes behavior. The neutral text must match B's instruction in characters (±5%) and position. It must not ask for anything the scorer could check. Example: a sentence restating that the public examples live in `test_public.py`. The final wording must be fixed before the pilot.

**Implemented:** `--conditions ABC` on `plan-pilot` and `freeze-main`. The neutral text is `NEUTRAL_INSTRUCTION` in `lab/runner.py`. A test enforces the length match and checks that the text requests no marker. Review the wording before the pilot. Once a pilot uses it, it is frozen.

Sample per arm: 3 tasks × 3 conditions × 5 repetitions = 45 planned attempts, randomized in blocks as in main-01. That gives 15 marker-enabled runs per arm.

## What 15 marker runs per arm can and cannot show

These figures come from `scripts/evalstats.py` in the `agent-eval-methodology` skill and from the research report. They are fixed here before any collection.

- **Chance of seeing even one failure.** With 15 marker runs, the chance of at least one failure is 0.54, 0.79 or 0.97 if the true failure rate is 5%, 10% or 20%. An arm with no failure is likely at low failure rates.
- **Sensitivity is not estimable at this size.** Estimating how often an omitted marker comes with a failure, to within about ±0.15–0.20, needs roughly 20–45 failures. At a 10% failure rate, observing 20 failures takes about 234 marker runs. This protocol does not claim to estimate sensitivity.
- **Optional diagnostic cohort.** If an arm produces failures, a separately labeled, preregistered cohort of condition B runs only can be sized for about 20 failures in that arm. That would be about 116–471 runs, depending on the arm's observed failure rate. Any "stop at k failures" rule must be fixed in advance and analysed with anytime-valid confidence sequences.
- **Does the marker cost anything?** If B and A both come out 15/15, the 90% interval for the difference is ±0.15. So this design can support at most a **20-point non-inferiority margin** for B vs A and C vs A. A 10-point margin would need roughly 60–75 runs per condition.
- **Scope of claims.** Three tasks are too few for clustered standard errors or mixed models. Claims are conditional on the pinned configuration and these tasks, and are reported per task.

## Runtime negative control

A reader suggested checking that the signal behaves sensibly when the runtime is broken. pilot-01 was an accidental version of this. A missing execution helper blocked all work, and the marker **was still present** (`CANARY:fd11c73f1ba333de`). A marker is therefore not evidence that the runtime worked.

Each arm should include a small, deliberate, labeled control cohort created with `plan-control`: one B run per task with the agent's workspace mounted read-only, so no edit can land. The expected outcome is an exact or noncompliant marker with incomplete or unevaluable work. The [signal-versus-work table](../lab/report.py) must place those runs in the "incomplete" or "unevaluable" column. If any of them is classified as complete work, the evaluator or report is wrong, and collection stops.

The report computes this verdict automatically for `control` cohorts. These are calibration-style runs. They never enter the arm's main tables.

## Reporting

Report everything main-01 reports. In addition:

- A Wilson 95% interval (primary) and a Clopper-Pearson interval (secondary) on every rate, null when the denominator is zero, and never a Wald interval. A headline in interval form, for example "0/15 exact-marker runs failed a checked rule (95% CI 0–20%)."
- STARD-style accounting: a flow of every planned run, and the 2×2 table including indeterminate cells. Report PPV and NPV only alongside the observed failure rate.
- A per-task pass^5 column, labeled descriptive.
- The signal-versus-work table (marker status × feature completion) for condition B, including runs whose rules are unevaluable. This is where "marker present, work blocked" shows up.
- The B vs A and C vs A differences, each with a Newcombe interval, judged against the 20-point non-inferiority margin.
- For each arm, whether any checked failure occurred. If none did, say so in the first paragraph of results.

## Stopping rules

- Freeze each arm's plan before its collection. Do not replace or retry failed attempts.
- Do not raise difficulty or swap models inside an arm to get a disagreement. Each new factor is a new arm with its own plan.
- An infrastructure defect stops the arm, as in main-01. Publish a dated amendment and start a replacement cohort.

## Prerequisites before any 02 collection

1. ~~Step 0's hardened evaluator, with its planted-bug kill count published, and the main-01 re-score reported.~~ Done; see Step 0 results. `freeze-main --calibration` now takes a calibration directory and records which one it used. Because later code changes alter the fingerprint, each 02 freeze uses a fresh calibration run just before freezing, not `calibration-step0`, which documents Step 0 itself.
2. Changes to `lab/` alter the source fingerprint. The post-publication report change already does this. Every arm therefore needs a new six-run pilot and fresh calibration before `freeze-main`, as the runner enforces.
3. ~~Condition C support in runner, report, and tests.~~ Done.
4. ~~The negative-control mode in the runner, with a test.~~ Done (`plan-control`, read-only workspace).
5. Report intervals: add Wilson and Clopper-Pearson intervals to `report.json`.
6. A per-run harness record: CLI version, the model ID the API returned, effort, tools, resources, timestamps, and a hash of the instruction stack actually sent. Restrict network egress to the inference endpoint. Treat a CLI version change as a new cohort.
7. For 02a and 02b: runner support for the extra rules and the per-function marker, plus a scorer for the per-function marker, with tests.
8. For 02f only: contract, reference solutions, and calibration cases for the new tasks.
9. Before any live run: rebuild the runtime image and run `doctor`. Confirm that the read-only mount blocks writes in a control pilot.

## Not in this protocol

- **Early-warning and drift studies.** These need multi-turn sessions with a marker and independent checks after every meaningful edit, comparing the first omission against the first failure. Checkpoints within one session are dependent observations. That is a separate longitudinal design. See [Optional follow-up studies](experiment.md#optional-follow-up-studies).
- **Ranking canary designs or recovery strategies.**
