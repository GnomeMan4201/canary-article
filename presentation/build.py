"""Present saved cohort evidence without running or rescoring an experiment."""

import argparse
from html import escape
import json
from pathlib import Path
import re

from lab.report import build_report


PANES = (("Project instructions", "instructions.md"), ("Task prompt", "prompt.txt"),
         ("Final response", "final.txt"), ("Code changes", "changes.diff"))


def safe_path(root, relative):
    """Evidence and output paths must stay inside the cohort, without symlinks."""
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"Path escapes cohort: {relative}")
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError(f"Symlink is not evidence: {relative}")
    return path


def html(value):
    return escape(str(value), quote=True)


def evidence_pane(cohort, run_id, title, filename):
    path = safe_path(cohort, Path("runs") / run_id / filename)
    if not path.is_file():
        body = f'<p class="missing">Not recorded: {html(filename)}.</p>'
    else:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            body = '<p class="missing">Unavailable: this file is not valid UTF-8 text.</p>'
        else:
            body = f'<pre>{html(text)}</pre>' if text else '<p class="missing">File recorded but empty.</p>'
    return f'<details><summary>{html(title)}</summary>{body}</details>'


CONDITION_LABELS = {"A": "A · no marker", "B": "B · marker", "C": "C · neutral instruction"}


def condition_options(report):
    conditions = list(report.get("by_condition") or ("A", "B"))
    everything = " and ".join(conditions) if len(conditions) == 2 else "All conditions"
    return f'<option value="">{html(everything)}</option>' + "".join(
        f'<option value="{html(c)}">{html(CONDITION_LABELS.get(c, c))}</option>' for c in conditions)


def run_card(cohort, run, index):
    result = run["result"] or {}
    evaluation = result.get("evaluation") or {}
    marker = (result.get("marker") or {}).get("status", "not recorded")
    fields = (("Marker", marker), ("Rules", evaluation.get("rules", "not recorded")),
              ("Feature", evaluation.get("feature", "not recorded")),
              ("Termination", result.get("termination", "not recorded")))
    statuses = ''.join(f'<div><dt>{html(label)}</dt><dd>{html(value)}</dd></div>' for label, value in fields)
    panes = ''.join(evidence_pane(cohort, run["run_id"], title, name) for title, name in PANES)
    checks = (f'<pre>{html(json.dumps(evaluation, indent=2, ensure_ascii=False))}</pre>'
              if evaluation else '<p class="missing">Independent evaluation not recorded.</p>')
    final_path = safe_path(cohort, Path("runs") / run["run_id"] / "final.txt")
    notice = '' if final_path.is_file() and final_path.stat().st_size else '<p class="missing">Final response not recorded or empty.</p>'
    return f'''<article class="run" data-task="{html(run['task'])}" data-condition="{html(run['condition'])}">
<div class="run-heading"><span class="number">{index:02d}</span><div>
<p class="eyebrow">{html(run['task'])} · Condition {html(run['condition'])}</p>
<h2>{html(run['run_id'])}</h2></div><span class="recording">{html(run['recording_status'])}</span></div>
<dl class="statuses">{statuses}</dl>{notice}{panes}
<details><summary>Independent evaluation</summary>{checks}</details></article>'''


def render(cohort, report):
    summary = report["summary"]
    counts = summary["recording"]
    planned, recorded = summary["planned"], counts.get("recorded", 0)
    options = ''.join(f'<option value="{html(task)}">{html(task)}</option>' for task in report["by_task"])
    cards = ''.join(run_card(cohort, run, index) for index, run in enumerate(report["runs"], 1))
    phase = report["phase"]
    note = ('Pilot runs validate the procedure and are separate from the main dataset.' if phase == 'pilot'
            else 'Main cohort. Recorded counts describe available evidence; they do not certify protocol compliance.')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Canary Lab · {html(phase)} run explorer</title>
<style>
:root{{color-scheme:light;--paper:#faf8ef;--ink:#25291f;--muted:#565e4b;--line:#d7d8c8;--yellow:#f2d764}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1080px;margin:auto;padding:48px 24px 80px}}header{{border-bottom:2px solid var(--ink);padding-bottom:30px}}
a{{color:inherit;text-underline-offset:3px}}.badge{{display:inline-block;background:var(--yellow);padding:4px 12px;font-weight:700}}
h1{{font:clamp(2.6rem,7vw,4.5rem)/1.05 Georgia,serif;margin:20px 0}}header p{{max-width:76ch}}
.muted,.eyebrow{{color:var(--muted)}}.eyebrow{{font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;margin:0}}
.accounting{{display:flex;gap:24px;flex-wrap:wrap;margin:24px 0 0}}.accounting strong{{font-size:1.5rem}}
.filters{{display:flex;gap:18px;align-items:end;flex-wrap:wrap;margin:28px 0}}label{{display:grid;gap:5px;font-size:.85rem;font-weight:600}}
select{{font:inherit;color:inherit;background:white;padding:9px 32px 9px 12px;border:1px solid #777e6e;border-radius:4px;min-height:44px}}
#visible-count{{margin:0 0 8px;color:var(--muted);font-size:.9rem}}.run{{border-top:1px solid var(--ink);padding:28px 0}}
.run-heading{{display:flex;align-items:center;gap:18px}}.number{{font:1.5rem Georgia,serif;color:var(--muted)}}
h2{{font-size:1.2rem;line-height:1.3;margin:4px 0;overflow-wrap:anywhere}}.recording{{margin-left:auto;font-size:.8rem;border:1px solid var(--line);padding:3px 9px}}
.statuses{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:22px 0}}dt{{color:var(--muted);font-size:.8rem}}dd{{margin:0;font-weight:650;overflow-wrap:anywhere}}
details{{border-top:1px solid var(--line);padding:11px 0}}summary{{cursor:pointer;font-weight:600;min-height:26px}}
pre{{margin:14px 0 4px;padding:18px;background:#efefe4;font:13px/1.65 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}}
.missing{{color:#74501e;background:#f5ebd9;padding:10px 14px;font-size:.9rem}}select:focus-visible,summary:focus-visible,a:focus-visible{{outline:3px solid #766100;outline-offset:4px}}
footer{{border-top:2px solid var(--ink);padding-top:22px;margin-top:30px;color:var(--muted);font-size:.85rem}}[hidden]{{display:none!important}}
@media(max-width:620px){{main{{padding:28px 16px 48px}}.statuses{{grid-template-columns:repeat(2,1fr)}}.run-heading{{gap:10px;flex-wrap:wrap}}.recording{{margin-left:0}}}}
@media print{{.filters{{display:none}}.run{{break-inside:avoid}}main{{padding:0}}}}
</style></head><body><main>
<header><span class="badge">{html(phase)} cohort</span><h1>Canary Lab<br>Run explorer</h1>
<p>Read the instructions, inspect the submitted change, and compare the response marker with independent checks.</p>
<p class="muted">{note} This view presents saved evidence without rescoring it.</p>
<p><a href="report/report.html">Full accounting and results</a> · <a href="report/report.json">Machine-readable report</a></p>
<div class="accounting"><span><strong>{recorded} / {planned}</strong> recorded runs</span>
<span>{counts.get('not_attempted', 0)} not attempted</span><span>{counts.get('interrupted', 0)} interrupted</span>
<span>{counts.get('invalid_evidence', 0)} invalid evidence</span></div></header>
<p class="muted">Condition A has no marker instruction. Condition B requests a marker. A marker status does not certify code correctness; a check pass applies only to the evaluated contract.</p>
<div class="filters"><label>Task<select id="task-filter"><option value="">All tasks</option>{options}</select></label>
<label>Condition<select id="condition-filter">{condition_options(report)}</select></label>
<p id="visible-count" role="status" aria-live="polite">Showing {planned} runs</p></div>
<section aria-label="Recorded run evidence">{cards}</section>
<footer>Built from saved cohort files. Missing evidence stays visible. No model calls, external assets, or network requests.</footer>
</main><script>
const task = document.getElementById('task-filter');
const condition = document.getElementById('condition-filter');
const cards = Array.from(document.querySelectorAll('.run'));
function filterRuns() {{
  let visible = 0;
  for (const card of cards) {{
    card.hidden = Boolean((task.value && card.dataset.task !== task.value) || (condition.value && card.dataset.condition !== condition.value));
    if (!card.hidden) visible++;
  }}
  document.getElementById('visible-count').textContent = `Showing ${{visible}} of ${{cards.length}} runs`;
}}
task.addEventListener('change', filterRuns);
condition.addEventListener('change', filterRuns);
</script></body></html>'''


def build(cohort):
    cohort = Path(cohort).resolve(strict=True)
    plan = json.loads(safe_path(cohort, "plan.json").read_text(encoding="utf-8"))
    for run in plan.get("runs", []):
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_id):
            raise ValueError("Unsafe run ID")
        for name in ("result.json", "attempt.json", *(name for _, name in PANES)):
            safe_path(cohort, Path("runs") / run_id / name)
    for name in ("report/report.json", "report/report.html", "explorer.html"):
        safe_path(cohort, name)
    report = build_report(cohort, cohort / "report")
    output = cohort / "explorer.html"
    output.write_text(render(cohort, report), encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cohort_dir", type=Path)
    print(build(parser.parse_args().cohort_dir))


if __name__ == "__main__":
    main()
