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
- A canary design recommendation. This experiment shows that the canary WORKS (100% compliance), but the uniform-green result means we can't measure its diagnostic value.
- A tool you should run without understanding. The experiment is small and inspectable by design. Read the [experiment protocol](docs/experiment.md) before running your own.

## Extending the study

The article identifies the key limitation: uniform success means no failure to correlate against. To measure the canary's diagnostic value, you would need:

- Longer sessions where context drifts.
- Multi-file architectural changes where intermediate state can be lost.
- A task hard enough that the agent sometimes fails a checked rule — then check whether canary omission precedes the failure.

## License

MIT. See [LICENSE](LICENSE).

## Contact

Open an issue on this repo.