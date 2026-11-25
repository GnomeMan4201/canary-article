# Follow-up protocol draft: main-02

Status: **draft, not frozen.** No data has been collected under this design. It responds to feedback on the published article and turns the article's stated limitations into a study that can produce a disagreement. The frozen [main-01 protocol](experiment.md) stays unchanged. Results from this design must be reported as a separate cohort.

## Why a follow-up

main-01 gave 30/30 passing checks and 15/15 exact markers. With no marker omission and no checked failure, every diagnostic fraction except the marker compliance rate was either undefined or showed no variation. The study showed that the marker format can be followed. It could not show whether an omission comes with a failure.

Readers asked two questions:

1. Should the next study use a different model or harder tasks?
2. Was the marker ever meant to be a warning?

On the second question: as main-01 defined it, the marker measures one thing, whether the final response complied with one instruction. Whether that compliance tracks anything else is the open question this follow-up addresses.

## Question

When checked failures occur, how often does marker noncompliance come with them, and how often does an exact marker appear alongside incomplete or failing work?

This is still a final-outcome study. It cannot establish that a marker warned *before* a failure. That needs the multi-turn design under [Not in this protocol](#not-in-this-protocol).

## Change one factor per arm

Changing the model and the tasks together would leave no way to attribute a new failure to either change. Each arm changes exactly one thing relative to main-01 and is reported as its own cohort.

| Arm | Change from main-01 | Everything else | Why this order |
| --- | --- | --- | --- |
| 02a | Reasoning effort `high` → `low` on the same model | Same tasks, evaluator, contract, limits | Supported by the runner today. Reuses the calibrated evaluator, so any new failure is a model-side difference. |
| 02b | A different, smaller model at `high` effort | Same tasks, evaluator, contract, limits | Next cheapest change. Needs only a new pilot. |
| 02c | Harder tasks (see below) on the main-01 model and effort | Same model, effort, limits | Needs a new contract, reference solutions, and calibration cases, so it comes last. |

Run 02a first. If 02a still produces no checked failure, that is a reportable result. It does **not** license escalating within the same cohort.

### Candidate harder tasks for 02c

These must be written into the contract and calibrated before any agent run. They are candidates, not commitments:

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

Sample per arm: 3 tasks × 3 conditions × 5 repetitions = 45 planned attempts, randomized in blocks as in main-01. That gives 15 marker-enabled runs per arm. This is still small. The protocol commits to reporting counts, not rates presented as reliability.

## Runtime negative control

A reader suggested checking that the signal behaves sensibly when the runtime is broken. pilot-01 was an accidental version of this. A missing execution helper blocked all work, and the marker **was still present** (`CANARY:fd11c73f1ba333de`). A marker is therefore not evidence that the runtime worked.

Each arm should include a small, deliberate, labeled control cohort created with `plan-control`: one B run per task with the agent's workspace mounted read-only, so no edit can land. The expected outcome is an exact or noncompliant marker with incomplete or unevaluable work. The [signal-versus-work table](../lab/report.py) must place those runs in the "incomplete" or "unevaluable" column. If any of them is classified as complete work, the evaluator or report is wrong, and collection stops.

The report computes this verdict automatically for `control` cohorts. These are calibration-style runs. They never enter the arm's main tables.

## Reporting

Report everything main-01 reports. In addition:

- The signal-versus-work table (marker status × feature completion) for condition B, including runs whose rules are unevaluable. This is where "marker present, work blocked" shows up.
- The condition C versus condition A contrast in feature and rule outcomes, described only, never as an effect estimate.
- For each arm, whether any checked failure occurred. If none did, say so in the first paragraph of results.

## Stopping rules

- Freeze each arm's plan before its collection. Do not replace or retry failed attempts.
- Do not raise difficulty or swap models inside an arm to get a disagreement. Each new factor is a new arm with its own plan.
- An infrastructure defect stops the arm, as in main-01. Publish a dated amendment and start a replacement cohort.

## Prerequisites before any 02 collection

1. Changes to `lab/` alter the source fingerprint. The post-publication report change already does this. Every arm therefore needs a new six-run pilot and fresh calibration before `freeze-main`, as the runner enforces.
2. ~~Condition C support in runner, report, and tests.~~ Done.
3. ~~The negative-control mode in the runner, with a test.~~ Done (`plan-control`, read-only workspace).
4. For 02c only: contract, reference solutions, and calibration cases for the new tasks.
5. Before any live run: rebuild the runtime image and run `doctor`. Confirm that the read-only mount blocks writes in a control pilot.

## Not in this protocol

- **Early-warning and drift studies.** These need multi-turn sessions with a marker and independent checks after every meaningful edit, comparing the first omission against the first failure. Checkpoints within one session are dependent observations. That is a separate longitudinal design. See [Optional follow-up studies](experiment.md#optional-follow-up-studies).
- **Ranking canary designs or recovery strategies.**
