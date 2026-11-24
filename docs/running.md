# Running Canary Lab

The project uses Python's standard library. Local development tests need Python 3.11 or newer. Actual trials and independent evaluations use Docker. The current adapter supports the native Linux x64 Codex CLI bundle, including its execution helper and bundled resources, and an existing Codex authentication file.

## Validate the implementation

```sh
python3 -m unittest discover -s tests -v
docker build --pull=false -t canary-lab-runtime:local .
```

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

The plan records the randomized schedule, unique marker tokens, runtime identifiers, and source hashes. Each cohort archives the source bytes used by the evaluator and controller. Source or runtime-asset changes prevent continuing that cohort. The 30 planned main attempts are fixed; an amendment or replacement cohort must remain visibly separate. The local freeze is not a public preregistration.

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
