# Replicating or extending Canary Lab

Independent replications and extensions are welcome. This guide covers which comparisons stay valid and how to report results so they can sit next to main-01 without being mistaken for it.

## Replication or extension?

| You change | Call it | Compare against main-01? |
| --- | --- | --- |
| Nothing except the machine you run on | Replication | Yes, directly |
| Model, effort, CLI version, or agent tool | Extension (one factor) | Only as "same tasks, different X" |
| Tasks, contract, or evaluator | Extension (new instrument) | No. Recalibrate and report as a separate study |
| Session length, multi-turn, injected instruction conflicts | New design | No. Needs its own protocol |

Change one factor per cohort. If two things change and a failure appears, you can't attribute it to either.

## What to keep fixed

- The four separate observations: instruction-loading evidence, marker compliance, rule checks, and feature completion. Don't collapse them into one pass/fail.
- All-run accounting. Every planned attempt appears in the report, including timeouts, interruptions, and missing final responses. Never silently replace a failed attempt.
- A plan frozen before collection, with its seed, settings, and source hashes.
- Evaluator isolation. The agent can't read hidden checks or references, and evaluation runs in a separate container without network or credentials.
- Undefined is not zero. A fraction with a zero denominator is reported as undefined.

## Steps

1. Read the [protocol](experiment.md) and the [run guide](running.md).
2. Run the unit tests and the 16 calibration cases. A new instrument needs new calibration cases, including deliberately broken implementations that must fail.
3. Run a six-run pilot cohort. Fix infrastructure problems in a new pilot cohort rather than editing the old one.
4. Freeze the main plan with `python3 -m lab.runner freeze-main`. The runner refuses if sources, runtime, or calibration differ from the pilot.
5. Collect and build the report. Include the signal-versus-work table, which keeps "marker present, work blocked" visible even when rules are unevaluable.
6. Name the cohort after its design (for example `ext-effort-low-01`), not `main-02`, unless you are running the [follow-up protocol](follow-up-protocol.md) as written.

## Using a different agent tool

The runner adapter targets Codex CLI and its JSON event stream. Another tool needs its own adapter that:

- identifies the terminal final response and never takes the marker from tool output or intermediate messages,
- reports a missing final response as unobserved, not absent,
- places the marker instruction in that tool's documented project instruction file, and records the effective instruction sources it can observe.

Add parser tests for exact, malformed, absent, and unobserved responses before any trial.

## Extensions we'd especially like to see

- Lower effort or a smaller model on the unchanged tasks. This is the cheapest way to get checked failures.
- An equal-length neutral instruction as a third condition (`--conditions ABC`). This shows whether adding the marker costs anything.
- Multi-turn sessions with checkpoints after each edit. This tests whether a marker persists while checked behavior degrades, which is the early-warning question main-01 could not address.

## Sharing results

Open an issue with a link to your cohort directory, or an archive of it, including `plan.json`, `runs/`, and `report/`. Please include the uninteresting results too. A replication that agrees with main-01 is still evidence.
