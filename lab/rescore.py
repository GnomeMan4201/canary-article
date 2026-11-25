"""Re-score a saved cohort's submissions with the current evaluator, as a labeled re-analysis.

The original cohort is never modified. Each saved snapshot is hash-checked
against its recorded result, then evaluated in the isolated container with the
current evaluator/ directory. The output records the original and new outcomes
side by side, plus checks that newly fail.

    python3 -m lab.rescore artifacts/main-01 artifacts/main-01-rescore-step0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab import runner


def rescore(cohort, output, image, evaluator_root=None):
    cohort, output = Path(cohort).resolve(), Path(output)
    if output.exists():
        raise FileExistsError("Re-score output exists; choose a new directory")
    plan = json.loads((cohort / "plan.json").read_text())
    evaluator_root = Path(evaluator_root or runner.ROOT / "evaluator").resolve()
    rows = []
    for planned in plan["runs"]:
        folder = cohort / "runs" / planned["run_id"]
        result_path = folder / "result.json"
        row = {"run_id": planned["run_id"], "task": planned["task"], "condition": planned["condition"]}
        if not result_path.is_file():
            rows.append({**row, "status": "no_original_result"})
            continue
        original = json.loads(result_path.read_text())
        snapshot = folder / "snapshot"
        actual = {str(p.relative_to(snapshot)): runner.sha(p) for p in snapshot.rglob("*") if p.is_file()}
        if actual != original.get("snapshot_hashes") or any(p.is_symlink() for p in snapshot.rglob("*")):
            rows.append({**row, "status": "snapshot_mismatch"})
            continue
        evaluation, process = runner.evaluate(snapshot, planned["task"], image, evaluator_root=evaluator_root)
        before = original.get("evaluation") or {}
        before_failed = {c["id"] for c in before.get("checks", []) if c.get("status") == "fail"}
        newly_failed = [c["id"] for c in evaluation["checks"] if c["status"] == "fail" and c["id"] not in before_failed]
        destination = output / "runs" / planned["run_id"]
        runner.write_json(destination / "evaluation.json", evaluation)
        runner.write_json(destination / "evaluation-process.json", process)
        rows.append({**row, "status": "rescored",
                     "marker": (original.get("marker") or {}).get("status"),
                     "original": {k: before.get(k) for k in ("rules", "feature", "status")},
                     "rescored": {k: evaluation.get(k) for k in ("rules", "feature", "status")},
                     "newly_failed_checks": newly_failed,
                     "changed": (before.get("rules"), before.get("feature")) != (evaluation.get("rules"), evaluation.get("feature"))})
    rescored = [r for r in rows if r["status"] == "rescored"]
    summary = {
        "schema_version": 1,
        "kind": "labeled re-analysis; not a new cohort and not a replacement for the original results",
        "source_cohort": str(cohort.relative_to(runner.ROOT)) if cohort.is_relative_to(runner.ROOT) else cohort.name,
        "evaluator_hashes": {str(p.relative_to(evaluator_root.parent)): runner.sha(p)
                             for p in sorted(evaluator_root.rglob("*.py")) if "__pycache__" not in p.parts},
        "image": image,
        "original_image_id": plan.get("runtime", {}).get("image_id"),
        "planned": len(rows),
        "rescored": len(rescored),
        "not_rescored": {r["run_id"]: r["status"] for r in rows if r["status"] != "rescored"},
        "evaluator_errors": [r["run_id"] for r in rescored if r["rescored"]["status"] == "evaluator_error"],
        "rules_pass": sum(r["rescored"]["rules"] == "pass" for r in rescored),
        "feature_pass": sum(r["rescored"]["feature"] == "pass" for r in rescored),
        "changed_outcomes": [r["run_id"] for r in rescored if r["changed"]],
        "exact_marker_and_now_failing": [r["run_id"] for r in rescored if r["marker"] == "exact" and r["rescored"]["rules"] == "fail"],
        "runs": rows,
    }
    runner.write_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cohort", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--image", default="canary-lab-runtime:local")
    args = parser.parse_args()
    image_id = runner.command(["docker", "image", "inspect", args.image, "--format", "{{.Id}}"]).stdout.strip()
    if not image_id:
        raise SystemExit("Docker image unavailable")
    summary = rescore(args.cohort, args.output, image_id)
    print(json.dumps({k: v for k, v in summary.items() if k != "runs"}, indent=2))


if __name__ == "__main__":
    main()
