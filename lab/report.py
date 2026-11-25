"""Build a static, auditable report from a saved Canary Lab cohort."""

from __future__ import annotations

from collections import Counter
from html import escape
import json
from pathlib import Path
import re
from typing import Any


MARKER_STATUSES = {"exact", "malformed", "absent", "unobserved", "not_applicable"}
EVALUATION_FIELDS = ("build", "baseline_rules", "new_rules", "feature", "rules", "status")
CELL_NAMES = ("exact_pass", "exact_fail", "noncompliant_pass", "noncompliant_fail")
# Signal versus work: marker observation against feature completion. Unlike the
# four-cell rule table, this keeps runs whose rules were unevaluable, which is
# where a present marker with blocked work appears (see pilot-01).
SIGNAL_MARKERS = ("exact", "noncompliant", "unobserved")
WORK_OUTCOMES = ("complete", "incomplete", "unevaluable")


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    cells = dict.fromkeys(CELL_NAMES, 0)
    exclusions: Counter[str] = Counter()
    recording: Counter[str] = Counter()
    termination: Counter[str] = Counter()
    markers: Counter[str] = Counter()
    evaluations = {field: Counter() for field in EVALUATION_FIELDS}
    exact_unevaluable = 0
    signal_work = {marker: dict.fromkeys(WORK_OUTCOMES, 0) for marker in SIGNAL_MARKERS}
    for run in runs:
        recording[run["recording_status"]] += 1
        if run["recording_status"] != "recorded":
            exclusions[run["recording_status"]] += 1
            continue
        result = run["result"]
        termination[str(result.get("termination", "unknown"))] += 1
        marker = result["marker"]["status"]
        markers[marker] += 1
        evaluation = result.get("evaluation") or {}
        for field in EVALUATION_FIELDS:
            evaluations[field][str(evaluation.get(field, "unavailable"))] += 1
        rules = evaluation.get("rules")
        if marker == "exact" and rules not in {"pass", "fail"}:
            exact_unevaluable += 1
        if run["condition"] == "B":
            signal = "exact" if marker == "exact" else "noncompliant" if marker in {"malformed", "absent"} else "unobserved"
            feature = evaluation.get("feature")
            work = "complete" if feature == "pass" else "incomplete" if feature == "fail" else "unevaluable"
            signal_work[signal][work] += 1
        # Reasons are disjoint. Separate counters above retain overlapping facts.
        if run["condition"] != "B":
            exclusions["no_marker_condition"] += 1
        elif marker not in {"exact", "malformed", "absent"}:
            exclusions["unobserved_marker"] += 1
        elif rules not in {"pass", "fail"}:
            exclusions["unevaluable_rules"] += 1
        else:
            group = "exact" if marker == "exact" else "noncompliant"
            cells[f"{group}_{rules}"] += 1
    exact = cells["exact_pass"] + cells["exact_fail"]
    noncompliant = cells["noncompliant_pass"] + cells["noncompliant_fail"]
    failures = cells["exact_fail"] + cells["noncompliant_fail"]
    return {
        "planned": len(runs),
        "recording": dict(recording),
        "termination": dict(termination),
        "marker": dict(markers),
        "evaluation": {field: dict(counts) for field, counts in evaluations.items()},
        "four_cells": cells,
        "four_cell_included": exact + noncompliant,
        "four_cell_excluded": dict(exclusions),
        "exact_marker_unevaluable_rules": exact_unevaluable,
        "signal_work": signal_work,
        "marker_present_work_blocked": signal_work["exact"]["incomplete"] + signal_work["exact"]["unevaluable"],
        "rates": {
            "failure_given_exact": _rate(cells["exact_fail"], exact),
            "failure_given_noncompliant": _rate(cells["noncompliant_fail"], noncompliant),
            "noncompliance_given_failure": _rate(cells["noncompliant_fail"], failures),
            "noncompliance_among_evaluable": _rate(noncompliant, exact + noncompliant),
            "work_blocked_given_exact": _rate(
                signal_work["exact"]["incomplete"] + signal_work["exact"]["unevaluable"],
                sum(signal_work["exact"].values()),
            ),
            "noncompliance_among_observed_markers": _rate(
                markers["malformed"] + markers["absent"],
                markers["exact"] + markers["malformed"] + markers["absent"],
            ),
        },
    }


def _extra_rules_summary(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Arm 02a: per-rule compliance, joint compliance, and the product-of-marginals baseline."""
    scored = [run for run in runs if run["recording_status"] == "recorded" and run["result"].get("extra_rule_outcomes")]
    if not scored:
        return None
    per_rule: dict[str, Counter[str]] = {}
    for run in scored:
        for outcome in run["result"]["extra_rule_outcomes"]:
            per_rule.setdefault(outcome["id"], Counter())[outcome["status"]] += 1
    rates = {}
    for rule_id, counts in sorted(per_rule.items()):
        observed = counts["followed"] + counts["violated"]
        rates[rule_id] = _rate(counts["followed"], observed)
    fully_observed = [run for run in scored
                      if all(o["status"] in {"followed", "violated"} for o in run["result"]["extra_rule_outcomes"])]
    joint = _rate(sum(all(o["status"] == "followed" for o in run["result"]["extra_rule_outcomes"]) for run in fully_observed),
                  len(fully_observed))
    expected = None
    if all(rate["value"] is not None for rate in rates.values()):
        expected = 1.0
        for rate in rates.values():
            expected *= rate["value"]
    return {"runs": len(scored), "rules_per_run": len(scored[0]["result"]["extra_rule_outcomes"]),
            "per_rule": {rule_id: dict(counts) for rule_id, counts in sorted(per_rule.items())},
            "per_rule_compliance": rates, "all_rules_followed": joint,
            "expected_all_followed_if_independent": expected}


def _function_marker_summary(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Arm 02b: function-level marker outcomes across marker-enabled runs."""
    scored = [run for run in runs if run["recording_status"] == "recorded"
              and isinstance(run["result"].get("marker"), dict) and "functions" in run["result"]["marker"]]
    if not scored:
        return None
    functions = [item for run in scored for item in run["result"]["marker"]["functions"]]
    counts = Counter(item["status"] for item in functions)
    return {"runs": len(scored), "functions": len(functions), "status_counts": dict(counts),
            "exact_functions": _rate(counts["exact"], len(functions)),
            "runs_without_changed_functions": sum(not run["result"]["marker"]["functions"] for run in scored)}


def _read_runs(cohort_dir: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    if plan.get("phase") not in {"pilot", "main", "control"} or not isinstance(plan.get("runs"), list):
        raise ValueError("plan.json must declare phase pilot, main, or control and a runs list")
    runs = []
    seen = set()
    for planned in plan["runs"]:
        run_id = planned.get("run_id")
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_id):
            raise ValueError("Each run_id must be a safe, nonempty filename component")
        if run_id in seen:
            raise ValueError(f"Duplicate run_id: {run_id}")
        seen.add(run_id)
        if planned.get("condition") not in {"A", "B", "C"} or not isinstance(planned.get("task"), str):
            raise ValueError(f"Invalid condition or task for {run_id}")
        run = {key: planned[key] for key in ("run_id", "task", "condition")}
        folder = cohort_dir / "runs" / run_id
        result_path = folder / "result.json"
        if not result_path.exists():
            run["recording_status"] = "interrupted" if (folder / "attempt.json").exists() else "not_attempted"
            run["result"] = None
        else:
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
                if not isinstance(result, dict):
                    raise ValueError("result must be an object")
                for field in ("run_id", "task", "condition"):
                    if result.get(field) != run[field]:
                        raise ValueError(f"result {field} disagrees with plan")
                if result.get("phase") != plan["phase"]:
                    raise ValueError("result phase disagrees with plan")
                marker = result.get("marker")
                if not isinstance(marker, dict) or marker.get("status") not in MARKER_STATUSES:
                    raise ValueError("unknown or missing marker status")
                if run["condition"] in {"A", "C"} and marker["status"] != "not_applicable":
                    raise ValueError(f"condition {run['condition']} marker must be not_applicable")
                if run["condition"] == "B" and marker["status"] == "not_applicable":
                    raise ValueError("condition B marker cannot be not_applicable")
                evaluation = result.get("evaluation")
                if evaluation is not None and not isinstance(evaluation, dict):
                    raise ValueError("evaluation must be an object or null")
                if evaluation and any(
                    field in evaluation and not isinstance(evaluation[field], str)
                    for field in EVALUATION_FIELDS
                ):
                    raise ValueError("evaluation status fields must be strings")
                run["recording_status"] = "recorded"
                run["result"] = result
            except (OSError, ValueError, TypeError) as error:
                run["recording_status"] = "invalid_evidence"
                run["result"] = None
                run["error"] = str(error)
        runs.append(run)
    return runs


def _html(value: Any) -> str:
    return escape(str(value), quote=True)


def _table(headers: list[str], rows: list[list[Any]], caption: str) -> str:
    head = "".join(f'<th scope="col">{_html(item)}</th>' for item in headers)
    body = "".join("<tr>" + "".join(f"<td>{_html(item)}</td>" for item in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><caption>{_html(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _counts(counts: dict[str, int]) -> str:
    return "; ".join(f"{key}: {value}" for key, value in sorted(counts.items())) or "none"


def _render(report: dict[str, Any]) -> str:
    summary = report["summary"]
    pilot_note = {
        "pilot": "Pilot evidence is for validating the procedure. It is not part of the main dataset.",
        "control": "Negative-control cohort: the workspace was read-only, so no run can complete its feature. It validates the report, not the agent, and never enters main tables.",
    }.get(report["phase"], "Main cohort. This label alone does not establish that the protocol was frozen or that collection is complete.")
    accounting = _table(["Record status", "Runs"], [
        [name.replace("_", " "), summary["recording"].get(name, 0)]
        for name in ("recorded", "not_attempted", "interrupted", "invalid_evidence")
    ], "All planned runs")
    cells = summary["four_cells"]
    matrix = _table(["Marker instruction", "Rules pass", "Rules fail"], [
        ["Exact", cells["exact_pass"], cells["exact_fail"]],
        ["Noncompliant (malformed or absent)", cells["noncompliant_pass"], cells["noncompliant_fail"]],
    ], "Condition B · observed final responses and evaluable rules only")
    rate_labels = {
        "failure_given_exact": "Rule failures among exact markers",
        "failure_given_noncompliant": "Rule failures among noncompliant markers",
        "noncompliance_given_failure": "Noncompliant markers among rule failures",
        "noncompliance_among_evaluable": "Noncompliant markers among evaluable runs",
        "work_blocked_given_exact": "Incomplete or unevaluable work among exact markers",
        "noncompliance_among_observed_markers": "Noncompliant markers among observed responses",
    }
    rate_rows = []
    for key, rate in summary["rates"].items():
        value = "Undefined" if rate["value"] is None else f'{rate["value"]:.1%}'
        rate_rows.append([rate_labels[key], f'{rate["numerator"]}/{rate["denominator"]}', value])
    rates = _table(["Descriptive fraction", "Count", "Fraction"], rate_rows, "Denominators remain visible")
    sw = summary["signal_work"]
    signal_table = _table(["Marker instruction", "Feature complete", "Feature incomplete", "Unevaluable"], [
        [label, sw[key]["complete"], sw[key]["incomplete"], sw[key]["unevaluable"]]
        for key, label in (("exact", "Exact"), ("noncompliant", "Noncompliant (malformed or absent)"), ("unobserved", "Unobserved final response"))
    ], "Condition B · signal versus work, all recorded runs")
    exclusions = _table(["Excluded from four-cell table", "Runs"], [
        [key.replace("_", " "), value] for key, value in sorted(summary["four_cell_excluded"].items())
    ], "Exclusions · disjoint accounting categories")
    status_rows = [["Termination", _counts(summary["termination"])], ["Marker", _counts(summary["marker"])]]
    status_rows.extend([field.replace("_", " "), _counts(summary["evaluation"][field])] for field in EVALUATION_FIELDS)
    statuses = _table(["Evidence dimension", "Recorded result counts"], status_rows, "Separate outcome dimensions")
    breakdown_rows = []
    for task, conditions in report["by_task_condition"].items():
        for condition, group in conditions.items():
            breakdown_rows.append([
                task, condition, group["planned"], group["recording"].get("recorded", 0),
                _counts(group["evaluation"]["rules"]), _counts(group["evaluation"]["feature"]),
                " / ".join(str(group["four_cells"][cell]) for cell in CELL_NAMES),
            ])
    arm_html = ""
    extra = report.get("extra_rules")
    if extra:
        rows = [[rule_id, f'{rate["numerator"]}/{rate["denominator"]}', "Undefined" if rate["value"] is None else f'{rate["value"]:.1%}']
                for rule_id, rate in extra["per_rule_compliance"].items()]
        joint = extra["all_rules_followed"]
        expected = extra["expected_all_followed_if_independent"]
        arm_html += (f'<h2>Extra rules (instruction load)</h2><p>{extra["runs"]} runs carried {extra["rules_per_run"]} extra rules each. '
                     f'All rules followed: {joint["numerator"]}/{joint["denominator"]}. Expected if rules were followed independently: '
                     f'{"undefined" if expected is None else f"{expected:.1%}"}.</p>'
                     + _table(["Rule", "Followed", "Rate"], rows, "Per-rule compliance among observed runs"))
    fm = report.get("function_markers")
    if fm:
        exact = fm["exact_functions"]
        arm_html += (f'<h2>Per-function marker</h2><p>{fm["functions"]} added or modified functions across {fm["runs"]} marker-enabled runs; '
                     f'exact marker on {exact["numerator"]}/{exact["denominator"]}. Runs that changed no function: {fm["runs_without_changed_functions"]}.</p>')
    control_html = ""
    if report.get("negative_control"):
        nc = report["negative_control"]
        verdict = {
            "pass": "Pass: every run produced a final response, and none was classified as complete work.",
            "inconclusive": f'Inconclusive: these runs never produced a final response, so they did not exercise the control: {", ".join(nc["not_exercised"])}. Treat the cohort as void and collect a replacement.',
            "fail": f'FAIL: runs classified as complete work despite a read-only workspace: {", ".join(nc["violations"])}. Stop and inspect the evaluator and report.',
        }[nc["status"]]
        control_html = f"<h2>Negative control</h2><p>{_html(verdict)}</p>"
    breakdown = _table(["Task", "Condition", "Planned", "Recorded", "Rules", "Feature", "Four cells*"], breakdown_rows, "Task and condition breakdown")
    details = []
    for run in report["runs"]:
        result = run["result"]
        detail = json.dumps(result if result is not None else run, indent=2, ensure_ascii=False)
        label = f'{run["run_id"]} · {run["task"]} · {run["condition"]} · {run["recording_status"]}'
        details.append(f"<details><summary>{_html(label)}</summary><pre>{_html(detail)}</pre></details>")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Canary Lab — {_html(report["phase"])} evidence</title>
<style>
:root{{color-scheme:light;--paper:#faf8ef;--ink:#25291f;--line:#d7d8c8;--yellow:#f2d764}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1120px;margin:auto;padding:44px 24px 72px}}header{{border-bottom:2px solid var(--ink);padding-bottom:28px}}
.eyebrow{{display:inline-block;background:var(--yellow);padding:3px 10px;font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em}}
h1{{font:clamp(2rem,5vw,3.5rem)/1.1 Georgia,serif;margin:18px 0}}h2{{font-size:1.35rem;margin:36px 0 8px}}
p{{max-width:80ch}}.muted{{color:#565e4b}}.table-wrap{{overflow-x:auto;margin:20px 0}}table{{border-collapse:collapse;width:100%;text-align:left;font-size:.9rem}}
caption{{text-align:left;font-weight:700;margin-bottom:8px}}th,td{{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}}th{{background:#eeeee2}}
details{{border-top:1px solid var(--line);padding:12px 0}}summary{{cursor:pointer;font-weight:600}}summary:focus-visible{{outline:3px solid #766100;outline-offset:4px}}
pre{{background:#efefe4;padding:16px;overflow:auto;font:13px/1.6 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}}
footer{{margin-top:40px;border-top:2px solid var(--ink);padding-top:16px;font-size:.85rem}}@media print{{main{{padding:0}}details{{break-inside:avoid}}}}
</style></head><body><main>
<header><span class="eyebrow">{_html(report["phase"])} cohort</span><h1>Canary Lab evidence</h1>
<p>Instruction markers and independently checked booking behavior, recorded separately.</p>
<p class="muted">{pilot_note}</p></header>
<h2>All-run accounting</h2><p>{summary["planned"]} planned runs. Missing or invalid evidence stays visible.</p>{accounting}{statuses}
<h2>Marker and rule outcomes</h2><p>{summary["four_cell_included"]} runs enter the four-cell table. “Pass” means the specified checks passed, not that all possible behavior is correct.</p>{matrix}{rates}{exclusions}
<p>Exact markers with unevaluable rules: {summary["exact_marker_unevaluable_rules"]}. These are outside the four-cell table. Exclusion reasons are assigned in order: recording status, condition, marker observation, rule evaluation.</p>
<p class="muted">These are descriptive final outcomes. They do not establish causation, early warning, or reliability beyond these tasks. A constant marker cannot distinguish outcomes; zero denominators are undefined.</p>
<h2>Signal versus work</h2><p>A marker shows only that the final response followed one instruction. This table sets it against feature completion for every recorded marker-enabled run, including runs whose rules could not be evaluated. Exact markers with incomplete or unevaluable work: {summary["marker_present_work_blocked"]}.</p>{signal_table}
<p class="muted">“Feature incomplete” means the independent feature check failed. It does not identify why: a broken runtime, a refusal, and an unfinished implementation all land in the same cell.</p>
{arm_html}{control_html}<h2>By task and condition</h2>{breakdown}<p class="muted">* Four-cell order: exact/pass, exact/fail, noncompliant/pass, noncompliant/fail. Conditions A and C have no marker and do not enter those cells. C adds a neutral instruction of matched length.</p>
<h2>Run evidence</h2><p>Expand a run to inspect recorded statuses, per-check evidence, errors, duration, and usage where supplied.</p>{''.join(details)}
<footer>Static report from saved cohort evidence. No model calls, external assets, or network requests are required. Machine-readable aggregate: report.json.</footer>
</main></body></html>'''


def build_report(cohort_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Write report.json and standalone report.html, returning the report data."""
    cohort_dir, output_dir = Path(cohort_dir), Path(output_dir)
    plan = json.loads((cohort_dir / "plan.json").read_text(encoding="utf-8"))
    runs = _read_runs(cohort_dir, plan)
    tasks = sorted({run["task"] for run in runs})
    conditions = plan.get("conditions") or ["A", "B"]
    report = {
        "schema_version": 2,
        "phase": plan["phase"],
        "summary": _summarize(runs),
        "by_task": {task: _summarize([run for run in runs if run["task"] == task]) for task in tasks},
        "by_condition": {condition: _summarize([run for run in runs if run["condition"] == condition]) for condition in conditions},
        "by_task_condition": {
            task: {condition: _summarize([run for run in runs if run["task"] == task and run["condition"] == condition]) for condition in conditions}
            for task in tasks
        },
        "runs": runs,
    }
    if plan.get("arm"):
        report["arm"] = plan["arm"]
    extra = _extra_rules_summary(runs)
    if extra:
        report["extra_rules"] = extra
    function_markers = _function_marker_summary(runs)
    if function_markers:
        report["function_markers"] = function_markers
    if plan["phase"] == "control":
        recorded = [run for run in runs if run["recording_status"] == "recorded"]
        violations = [run["run_id"] for run in recorded
                      if (run["result"].get("evaluation") or {}).get("feature") == "pass"]
        # Untouched code always fails its feature check, so "no complete work" is
        # only meaningful when the agent actually ran and answered.
        not_exercised = [run["run_id"] for run in runs if run["recording_status"] != "recorded"
                         or run["result"].get("final_response_observed") is not True]
        status = "fail" if violations else "inconclusive" if not_exercised else "pass"
        report["negative_control"] = {"expected": "no complete work from an agent that ran",
                                      "violations": violations, "not_exercised": not_exercised,
                                      "status": status}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "report.html").write_text(_render(report), encoding="utf-8")
    return report
