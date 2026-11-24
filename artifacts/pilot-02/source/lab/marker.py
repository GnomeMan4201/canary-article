"""Protocol-defined marker scoring; no model-based judging."""
import re


def score_marker(response, token):
    if token is None:
        return {"status": "not_applicable"}
    if not re.fullmatch(r"[0-9a-f]{16}", token):
        raise ValueError("token must be 16 lowercase hexadecimal characters")
    if response is None:
        return {"status": "unobserved"}
    normalized = response.replace("\r\n", "\n").replace("\r", "\n")
    first = next((line for line in normalized.split("\n") if line.strip(" \t")), "")
    if first == "CANARY:" + token:
        return {"status": "exact"}
    return {"status": "malformed" if token in normalized else "absent"}


def parse_events(text):
    """Only accept final-phase assistant messages, never tool output/commentary."""
    import json
    final = None
    usage = None
    completed = False
    failures = []
    malformed_lines = 0
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            malformed_lines += 1
            continue
        if not isinstance(event, dict):
            malformed_lines += 1
            continue
        if event.get("type") == "turn.started":
            final, usage, completed = None, None, False
        item = event.get("item", {})
        if not isinstance(item, dict):
            malformed_lines += 1
            continue
        if event.get('type') == 'item.completed' and item.get('type') == 'error':
            failures.append(event)
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            # Pinned CLI versions differ in whether they include a phase field.
            # Without phase, wait for turn.completed; use the final agent message.
            if item.get("phase") in (None, "final_answer"):
                final = item.get("text") if isinstance(item.get("text"), str) else None
        if event.get("type") == "turn.completed":
            completed = True
            usage = event.get("usage")
        if event.get("type") in ("error", "turn.failed"):
            failures.append(event)
            final, completed = None, False
    return {"final_response": final if completed else None, "usage": usage,
            "completed": completed, "errors": failures, "malformed_lines": malformed_lines}
