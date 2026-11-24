# Article direction after runtime pilots

These are editorial notes, not main-study findings. At this draft, the planned 30 main attempts have not begun. Pilot evidence validates the procedure and stays outside the main dataset.

## A factual scene from the stopped pilot

The first completed attempt in `pilot-01` began its final response with the exact canary marker. The next sentence reported a missing execution helper: `/usr/local/bin/codex-code-mode-host`. The agent said it could not access the files or run checks. The saved implementation did not include the requested rescheduling feature.

The independent evaluator recorded a passing baseline, failed feature acceptance, and unevaluable new-operation rules. That last status matters: this was not an observed double booking or proof that the agent ignored project rules. The marker appeared while the environment prevented the work from happening.

The cohort was stopped, its next attempt interrupted, and the runtime defect documented in an amendment. This is a useful opening about why evidence needs separate statuses. Identify it immediately as a failed runtime pilot, and do not include it in the main four-cell table.

Evidence: [amendment](../artifacts/pilot-01/amendment.json), [completed result](../artifacts/pilot-01/runs/reschedule-01-B/result.json), [final response](../artifacts/pilot-01/runs/reschedule-01-B/final.txt).

## What the replacement pilot currently shows

The four completed results inspected for `pilot-02` cover availability and rescheduling, each with and without a marker. All four independently passed baseline rules, new-operation rules, and feature acceptance. Both marker-condition responses matched exactly. These observations establish neither a completed six-run pilot nor a main-study outcome. Batch attempts were not complete when these notes were drafted.

Evidence: [availability A](../artifacts/pilot-02/runs/availability-01-A/result.json), [availability B](../artifacts/pilot-02/runs/availability-01-B/result.json), [rescheduling A](../artifacts/pilot-02/runs/reschedule-01-A/result.json), [rescheduling B](../artifacts/pilot-02/runs/reschedule-01-B/result.json).

## Openings conditional on main results

- **All checks pass and all observed markers match:** Open with the absence of a dramatic failure. Explain that this sample cannot estimate warning performance against failures it never observed. Show exact counts, including unavailable results.
- **Marker and checks disagree:** Open with a real disagreement and immediately give its frequency. Distinguish checked rule failure from failed feature acceptance or unevaluable work. A missing marker alongside passing checks deserves the same attention as the reverse.
- **Mixed results:** Choose a representative run, then show the complete table. Let the evidence determine the story's emphasis.

## Reader takeaway and historical thread

Readers should leave able to add one inexpensive marker, inspect instruction loading, and keep its output separate from independently checked behavior. If the marker disappears, investigate loading and the relevant rule before deciding what happened. This response is engineering guidance; the study does not compare recovery actions.

Credit [Context Canary](https://github.com/Nachx639/context-canary) as prior work. Ground loading versus enforcement in [Anthropic's documentation](https://code.claude.com/docs/en/memory). Use the [Science Museum's oxygen-equipped canary cage](https://collection.sciencemuseumgroup.org.uk/objects/co8412250/cage-for-reviving-canary) for one short passage about detection and response. Briefly distinguish [production release canaries](https://sre.google/workbook/canarying-releases/) from this offline experiment.

## Claims to avoid

Avoid “the marker proves all instructions were read,” “the agent forgot,” “the canary caught a bug before it happened,” “canaries improve correctness,” “the best canary technique,” and “30 independent model samples.” Do not call unevaluable behavior correct, count pilot or calibration cases as main results, present a local freeze as public preregistration, or claim this project invented instruction canaries.
