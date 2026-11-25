"""Opt-in checks that the real evaluation container enforces what the unit tests mock.

Skipped unless CANARY_DOCKER_TESTS=1 and the runtime image exists:

    docker build --pull=false -t canary-lab-runtime:local .
    CANARY_DOCKER_TESTS=1 python3 -m unittest tests.test_container_integration -v

Each test writes a small booking.py into a temporary snapshot and evaluates it
with runner.evaluate, exactly as collection does. Probe submissions define a
correct BookingStore only if the isolation holds, so a pass proves the guard.
"""

import os
from pathlib import Path
import tempfile
import unittest

from lab import mutation, runner


IMAGE = os.environ.get("CANARY_IMAGE", "canary-lab-runtime:local")
REFERENCE = mutation.SOURCES["batch"].read_text(encoding="utf-8")


def image_id():
    if os.environ.get("CANARY_DOCKER_TESTS") != "1":
        return None
    try:
        result = runner.command(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"])
    except (OSError, Exception):
        return None
    return result.stdout.strip() or None


IMAGE_ID = image_id()


@unittest.skipUnless(IMAGE_ID, "set CANARY_DOCKER_TESTS=1 and build canary-lab-runtime:local")
class ContainerIntegrationTests(unittest.TestCase):
    def evaluate(self, source, task="batch", timeout=20):
        with tempfile.TemporaryDirectory(prefix="canary-it-") as temporary:
            snapshot = Path(temporary)
            (snapshot / "booking.py").write_text(source, encoding="utf-8")
            os.chmod(snapshot, 0o755)
            os.chmod(snapshot / "booking.py", 0o644)
            result, process = runner.evaluate(snapshot, task, IMAGE_ID, timeout=timeout)
        self.assertTrue(process["cleanup_verified"], "container cleanup was not verified")
        return result, process

    def probe(self, guard):
        """A correct store that raises at import if `guard` (code run at import) finds isolation broken."""
        return guard + "\n" + REFERENCE

    # Correctness inside the container --------------------------------------

    def test_references_pass_in_the_container(self):
        for task, path in mutation.SOURCES.items():
            with self.subTest(task=task):
                result, _ = self.evaluate(path.read_text(encoding="utf-8"), task)
                self.assertEqual((result["status"], result["rules"], result["feature"]), ("completed", "pass", "pass"))

    def test_planted_bugs_fail_in_the_container(self):
        cases = {
            "non-atomic-batch": ("batch", "batch.invalid_atomicity"),
            "reschedule-changes-room": ("reschedule", "reschedule.preserves_room"),
            "touching-start": ("baseline", "baseline.adjacency_and_rooms"),
        }
        for identifier, (task, expected_check) in cases.items():
            _, _, _, old, new = next(m for m in mutation.MUTANTS if m[0] == identifier)
            with self.subTest(mutant=identifier):
                result, _ = self.evaluate(mutation.apply(task, old, new), task)
                failed = {c["id"] for c in result["checks"] if c["status"] == "fail"}
                self.assertEqual(result["rules"], "fail")
                self.assertIn(expected_check, failed)
                self.assertIn(f"{'baseline' if task == 'baseline' else task}.randomized_differential", failed)

    # Isolation ---------------------------------------------------------------

    def test_network_is_unreachable(self):
        guard = (
            "import socket\n"
            "try:\n"
            "    socket.create_connection(('1.1.1.1', 53), timeout=2).close()\n"
            "except OSError:\n"
            "    pass\n"
            "else:\n"
            "    raise RuntimeError('network reachable from evaluation container')\n"
        )
        result, _ = self.evaluate(self.probe(guard))
        self.assertEqual(result["status"], "completed", result.get("errors"))
        self.assertEqual(result["rules"], "pass")

    def test_filesystem_is_read_only_outside_tmp(self):
        guard = (
            "import os\n"
            "for _path in ('/submission/written', '/harness/evaluator/written', '/written', '/home/agent/written'):\n"
            "    try:\n"
            "        with open(_path, 'w') as _handle:\n"
            "            _handle.write('x')\n"
            "    except OSError:\n"
            "        continue\n"
            "    raise RuntimeError('writable: ' + _path)\n"
            "with open('/tmp/scratch', 'w') as _handle:\n"
            "    _handle.write('tmp is writable scratch space')\n"
        )
        result, _ = self.evaluate(self.probe(guard))
        self.assertEqual(result["status"], "completed", result.get("errors"))
        self.assertEqual(result["rules"], "pass")

    def test_runs_unprivileged_without_credentials(self):
        guard = (
            "import os\n"
            "if os.getuid() == 0:\n"
            "    raise RuntimeError('evaluator runs as root')\n"
            "for _path in ('/run/canary-auth.json', '/var/run/docker.sock'):\n"
            "    if os.path.exists(_path):\n"
            "        raise RuntimeError('present in evaluation container: ' + _path)\n"
        )
        result, _ = self.evaluate(self.probe(guard))
        self.assertEqual(result["status"], "completed", result.get("errors"))

    # Resource limits -----------------------------------------------------------

    def test_hanging_submission_is_killed_and_recorded(self):
        result, process = self.evaluate("while True:\n    pass\n", timeout=5)
        self.assertTrue(process["timeout"])
        self.assertEqual(result["status"], "evaluator_error")
        self.assertEqual(result["errors"][0]["kind"], "timeout")

    def test_output_flood_is_truncated_and_recorded(self):
        # Writes straight to file descriptor 1, bypassing the evaluator's in-process capture.
        flood = "import os\nfor _ in range(64):\n    os.write(1, b'x' * (1024 * 1024))\n"
        result, process = self.evaluate(flood)
        self.assertTrue(process["output_truncated"])
        self.assertEqual(result["status"], "evaluator_error")


if __name__ == "__main__":
    unittest.main()
