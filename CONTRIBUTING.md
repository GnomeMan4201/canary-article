# Contributing to Canary Lab

The experiment is complete, but the project is built to be reused and extended. Here's how.

## Reproducing the experiment

1. Clone this repo.
2. Read [docs/running.md](docs/running.md) for setup, calibration, pilots, collection, and replay.
3. The main study used Codex CLI 0.166.0 with `gpt-6-astra`, high reasoning effort, 240-second time limit per attempt.
4. All 30 main-attempt results are in `artifacts/main-01/`. Each run has its instructions, task, prompt, final response, code diff, and check results.

## Running your own

- Change the tasks in `fixtures/` to exercise your own contract.
- The evaluator is independent of the agent: it runs in a separate container with no network access.
- Results are saved as standalone HTML (the evidence explorer) and machine-readable JSON.

## Calibration

The evaluator was calibrated against 16 known cases: correct implementations, deliberately broken overlap handling, timestamp errors, partial batch writes, missing features, import failures, and a hanging import. Calibration records are in `artifacts/calibration/`. Run calibration before any new study.

## What this repo is NOT

- A benchmark. 30 runs on one model prove nothing general.
- A canary design recommendation. This experiment shows that the marker format was followed in 15 of 15 runs. That is all. With no omissions and no checked failures, it can't measure whether the marker signals anything else.
- A tool you should run without understanding. The experiment is small and inspectable by design. Read the [experiment protocol](docs/experiment.md) before running your own.

## Extending the study

The article identifies the key limitation: uniform success means no failure to correlate against.

- [docs/replicating.md](docs/replicating.md) explains how to run an independent replication or a one-factor extension and report it as a separate cohort.
- [docs/follow-up-protocol.md](docs/follow-up-protocol.md) is the draft main-02 design. It changes one factor per arm, adds an equal-length neutral-instruction control, and adds a runtime negative control.
- Early-warning and drift questions need multi-turn sessions with checks after every edit. That is a separate longitudinal design.

## License

MIT. See [LICENSE](LICENSE).

## Contact

Open an issue on this repo.