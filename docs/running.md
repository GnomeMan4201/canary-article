# Running Canary Lab

The project uses Python's standard library. Local development tests need Python 3.11 or newer. Actual trials and independent evaluations use Docker. The current adapter supports the native Linux x64 Codex CLI bundle, including its execution helper and bundled resources, and an existing Codex authentication file.

## Validate the implementation

```sh
python3 -m unittest discover -s tests -v
docker build --pull=false -t canary-lab-runtime:local .
CANARY_DOCKER_TESTS=1 python3 -m unittest tests.test_container_integration -v
```

The normal test run mocks Docker. The container integration tests are opt-in and skipped by default. They evaluate real submissions in the runtime image and check that:

- the references pass and planted bugs fail inside the container;
- the network is unreachable;
- the filesystem is read-only outside `/tmp`;
- evaluation runs unprivileged, with no credentials or Docker socket;
- a hanging or output-flooding submission is killed, and the kill is recorded.

Run them after rebuilding the image or changing the runner's container flags.

The image contains Python and an unprivileged user. It contains no experiment sources, hidden tests, credentials, or previous results. Trial runs mount only the baseline workspace, the read-only native Codex bundle, and one authentication file. Independent evaluation runs separately with no network or credentials. This adapter assumes host UID 1000 for writable bind mounts; adapt and validate the image user for a different host before a new study.

Locate the installed native binary, not the JavaScript launcher:

```sh
export CANARY_CODEX_BINARY="$(npm root -g)/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex"
python3 -m lab.runner doctor --binary "$CANARY_CODEX_BINARY"
python3 -m lab.calibrate --image canary-lab-runtime:local --output artifacts/calibration
```

Calibration executes known-correct fixtures, deliberate defects, missing features, import failures, and a hanging import. The output includes each source, evaluation, process outcome, and expectation. Calibration is not an agent experiment. Existing calibration directories are never overwritten; preserve an old directory under another name before making a new canonical calibration.

## Pilot collection

The following model and effort match the configuration selected for this project's initial trials. Use the model available in your own account and record any change as a different configuration.

```sh
python3 -m lab.runner plan-pilot artifacts/pilot-example \
  --binary "$CANARY_CODEX_BINARY" --model gpt-6-astra --effort high --timeout 240
python3 -m lab.runner run artifacts/pilot-example
python3 -m lab.runner report artifacts/pilot-example
```

Inference uses the connected account's normal Codex usage. The runner reads `~/.codex/auth.json` by default; `--auth-file` can select another file. It copies authentication only into the temporary container home and never into the evidence archive. It does not load the user's configuration, skills, project history, or previous sessions. Network access is enabled for inference; the fixture itself has no network dependency. The model alias and CLI version are recorded; the provider's underlying backend revision remains unavailable.

`run --limit 1` executes one previously unattempted row for an initial runtime check. Calling `run` again continues unattempted rows in the saved order. Attempted rows, including interrupted rows, are never automatically retried. A timeout has its own status. A tool-host failure is a runtime error even if the assistant subsequently produces a final message.

If a pilot exposes a runtime or specification defect, preserve the evidence and make a new pilot cohort after the fix. Do not relabel calibration or pilot observations as main-study data.

## Freeze and collect the main cohort

First inspect the pilot evidence for valid tool use, instruction handling, final-response capture, and evaluator operation. The command also requires six completed pilot rows and passing calibration with source hashes matching the current implementation. Those mechanical checks do not replace reviewing the evidence.

```sh
python3 -m lab.runner freeze-main artifacts/main-example \
  --pilot artifacts/pilot-example --binary "$CANARY_CODEX_BINARY" \
  --model gpt-6-astra --effort high --timeout 240
python3 -m lab.runner run artifacts/main-example
python3 -m lab.runner report artifacts/main-example
```

`freeze-main` checks calibration from `artifacts/calibration` by default, which is the record main-01 was frozen against. For a later cohort, calibrate the current code into a new directory immediately before freezing, and name it with `--calibration`:

```sh
python3 -m lab.calibrate --image canary-lab-runtime:local --output artifacts/calibration-main-02a
python3 -m lab.runner freeze-main artifacts/main-02a --pilot artifacts/pilot-02a \
  --calibration artifacts/calibration-main-02a --binary "$CANARY_CODEX_BINARY" --model gpt-6-astra --effort high --timeout 240
```

Calibration must match the current source fingerprint, so any change to `lab/`, `evaluator/`, `fixtures/`, `tasks/`, the contract, the protocol or the Dockerfile needs a fresh calibration. The plan records which calibration file it used and that file's hash.

The plan records the randomized schedule, unique marker tokens, runtime identifiers, and source hashes. Each cohort archives the source bytes used by the evaluator and controller. Source or runtime-asset changes prevent continuing that cohort. The 30 planned main attempts are fixed; an amendment or replacement cohort must remain visibly separate. The local freeze is not a public preregistration.

## Follow-up options: condition C and negative controls

These options support the [draft follow-up protocol](follow-up-protocol.md). They don't change how main-01 was collected or scored.

`--conditions ABC` on `plan-pilot` and `freeze-main` adds condition C. C appends a neutral instruction, matched to the marker instruction's length within 5%, that asks for no observable output. Blocks then hold one A, one B, and one C run, so a pilot has 9 runs and a main cohort has 45. `freeze-main` refuses a pilot planned with different conditions.

```sh
python3 -m lab.runner plan-pilot artifacts/pilot-abc-01 --conditions ABC \
  --binary "$CANARY_CODEX_BINARY" --model gpt-6-astra --effort low --timeout 240
```

`plan-control` creates a negative-control cohort with one marker run per task and the agent's workspace mounted read-only. No run can complete its feature. Runtime errors are expected, so they don't halt collection. Evaluator errors still do. The report adds a negative-control verdict that fails if any run is classified as complete work. Control cohorts never enter main tables.

```sh
python3 -m lab.runner plan-control artifacts/control-01 \
  --binary "$CANARY_CODEX_BINARY" --model gpt-6-astra --effort low --timeout 240
python3 -m lab.runner run artifacts/control-01
python3 -m lab.runner report artifacts/control-01
```

## Evaluator strength: planted bugs and re-scoring

`lab.mutation` plants targeted bugs in the trusted reference solutions and reports which checks catch each one. Equivalent mutants are listed separately and excluded from the score. It runs in-process, because the mutants are derived from trusted code.

```sh
python3 -m lab.mutation --output artifacts/mutation-example
```

`lab.rescore` re-evaluates a saved cohort's submissions with the current evaluator, in the isolated container, as a labeled re-analysis. Each snapshot is hash-checked first. The original cohort is never modified.

```sh
python3 -m lab.rescore artifacts/main-01 artifacts/main-01-rescore-example
```

## Inspect and replay evidence

Open `artifacts/<cohort>/report/report.html` for the standalone report. It retains every planned row and separates marker status, feature completion, checked behavior, and missing evidence. Expand a row for per-check results. Its adjacent `report.json` contains the aggregate and run records.

For a filterable view with the original instructions, prompts, responses, and code diffs, run `python3 -m presentation.build artifacts/<cohort>` and open `artifacts/<cohort>/explorer.html`. This presentation layer reads the recorded evidence without changing scores or making model calls.

Each run directory retains the exact prompt and instructions, redacted event log, final response when observed, final code snapshot, code diff, evaluation output, and status manifest. Secret substitutions are recorded; an implementation changed by redaction is not evaluated as if it were the original submission.

```sh
python3 -m lab.runner replay artifacts/main-example reschedule-01-B
```

Replay verifies the saved snapshot and archived source hashes before running the archived evaluator in the recorded image. It makes no model call and does not overwrite the original result. Preserve the Docker image or its retrievable equivalent alongside the evidence.

Raw local artifacts are ignored by Git. Review their contents before publishing an evidence package. The HTML report is a local research artifact; nothing is deployed or posted to dev.to automatically.

## Runtime references

The adapter uses the installed CLI's help and [OpenAI's noninteractive command documentation](https://learn.chatgpt.com/docs/developer-commands#codex-exec) for JSON events and ephemeral runs. Terminal-event behavior is verified against the actual pinned CLI in the pilots rather than assumed to be identical across versions.
