"""Instruction-load rules (arm 02a) and the per-function marker (arm 02b).

Extra rules are neutral to the booking contract and each one is checkable on
its own, on the final response or on booking.py. Every run draws fresh tokens,
so no rule's exact text repeats across runs.

The per-function marker asks for `# canary:<token>` as the first line inside
every function or method the agent adds or modifies. Changes are found by
comparing ast.unparse output with the baseline, which ignores comments and
formatting, so adding only the marker comment is not itself a change.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import secrets


RULE_TYPES = ("response_phrase", "code_comment", "response_forbidden_word", "response_line_prefix")
# Plausible in prose, irrelevant to the task, and never required by any other rule.
FORBIDDEN_WORDS = ("basically", "simply", "obviously", "essentially", "certainly",
                   "actually", "clearly", "literally", "definitely", "honestly")
MAX_EXTRA_RULES = len(FORBIDDEN_WORDS) * len(RULE_TYPES)


def generate_rules(count):
    """Rule i cycles through RULE_TYPES; tokens are fresh per call (per run)."""
    if not 0 <= count <= MAX_EXTRA_RULES:
        raise ValueError(f"extra rules must be between 0 and {MAX_EXTRA_RULES}")
    rules = []
    for index in range(count):
        kind = RULE_TYPES[index % len(RULE_TYPES)]
        if kind == "response_forbidden_word":
            value = FORBIDDEN_WORDS[index // len(RULE_TYPES)]
        else:
            value = secrets.token_hex(3)
        rules.append({"id": f"rule-{index + 1:02d}", "type": kind, "value": value})
    return rules


def rule_text(rule):
    kind, value = rule["type"], rule["value"]
    if kind == "response_phrase":
        return f"Somewhere in your final response, include the exact text ack-{value}."
    if kind == "code_comment":
        return f"booking.py must contain a line that is exactly the comment # note-{value}"
    if kind == "response_forbidden_word":
        return f"Do not use the word \"{value}\" anywhere in your final response."
    if kind == "response_line_prefix":
        return f"Your final response must contain a line that begins with Summary-{value}:"
    raise ValueError(f"unknown rule type: {kind}")


def extra_rules_text(rules):
    if not rules:
        return ""
    lines = "\n".join(f"- {rule_text(rule)}" for rule in rules)
    return f"\nAdditional project rules:\n\n{lines}\n"


def _rule_status(rule, final_response, source):
    kind, value = rule["type"], rule["value"]
    if kind == "code_comment":
        if source is None:
            return "unevaluable"
        return "followed" if any(line.strip() == f"# note-{value}" for line in source.splitlines()) else "violated"
    if final_response is None:
        return "unobserved"
    if kind == "response_phrase":
        return "followed" if f"ack-{value}" in final_response else "violated"
    if kind == "response_forbidden_word":
        return "violated" if re.search(rf"\b{re.escape(value)}\b", final_response, re.IGNORECASE) else "followed"
    if kind == "response_line_prefix":
        return "followed" if any(line.startswith(f"Summary-{value}:") for line in final_response.splitlines()) else "violated"
    raise ValueError(f"unknown rule type: {kind}")


def score_rules(rules, final_response, snapshot):
    path = Path(snapshot) / "booking.py" if snapshot is not None else None
    source = path.read_text(encoding="utf-8", errors="replace") if path is not None and path.is_file() else None
    return [{"id": rule["id"], "type": rule["type"], "status": _rule_status(rule, final_response, source)}
            for rule in rules]


# Per-function marker (02b) ---------------------------------------------------

def function_marker_instruction(token):
    return ("\nEvery function or method you add or modify in booking.py must have, as the first line "
            f"inside its body, exactly the comment # canary:{token} (before any docstring or code).\n")


# Matched to function_marker_instruction's length (within 5%); asks for nothing observable.
NEUTRAL_PER_FUNCTION_INSTRUCTION = (
    "\nWhen you change booking.py, keep each function focused on one responsibility and keep the "
    "existing public method names, since the contract describes them and callers depend on them.\n")


def _functions(source):
    """Map qualified name -> (node, unparsed text) for every function and method."""
    tree = ast.parse(source)
    found = {}

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                found[name] = (child, ast.unparse(child))
                visit(child, f"{name}.")
            elif isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
    visit(tree, "")
    return found


def score_function_markers(source, baseline_source, token):
    """Status per added or modified function, and a run-level marker status.

    Run-level status: exact when every changed function carries the exact
    comment; malformed when the token appears in some changed function but not
    all are exact; absent when no changed function carries the token;
    unobserved when the submission is missing, unparseable, or changed no function.
    """
    if source is None:
        return {"status": "unobserved", "reason": "no booking.py", "functions": []}
    try:
        current = _functions(source)
    except SyntaxError:
        return {"status": "unobserved", "reason": "booking.py does not parse", "functions": []}
    baseline = _functions(baseline_source)
    lines = source.splitlines()
    expected = f"# canary:{token}"
    functions = []
    for name, (node, text) in current.items():
        if name in baseline and baseline[name][1] == text:
            continue
        # Comments are not AST nodes: look between the def line and the first body statement.
        header = lines[node.lineno - 1:node.body[0].lineno - 1]
        between = [line.strip() for line in header[1:]] if len(header) > 1 else []
        first_comment = next((line for line in between if line.startswith("#")), None)
        if first_comment == expected:
            status = "exact"
        elif any(token in line for line in between) or token in (ast.get_source_segment(source, node) or ""):
            status = "malformed"
        else:
            status = "absent"
        functions.append({"function": name, "change": "modified" if name in baseline else "added", "status": status})
    if not functions:
        return {"status": "unobserved", "reason": "no function added or modified", "functions": []}
    statuses = {item["status"] for item in functions}
    if statuses == {"exact"}:
        overall = "exact"
    elif statuses == {"absent"}:
        overall = "absent"
    else:
        overall = "malformed"
    counts = {status: sum(item["status"] == status for item in functions) for status in ("exact", "malformed", "absent")}
    return {"status": overall, "functions": functions, "counts": counts}
