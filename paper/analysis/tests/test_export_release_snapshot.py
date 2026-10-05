"""Check export audit gates and the public field allowlist."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/export_release_snapshot.py"


class ExportTests(unittest.TestCase):
    def export(self, *, verified=True, duplicate=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            row = {
                "id": "test", "model": "model", "task": "task", "repeat": 1,
                "calls": 1, "tokens": 2, "passed": True,
                "replay_verified": verified, "conversation_order_verified": True,
                "input_delivery_verified": True, "state_updates_verified": True,
                "private_prompt": "do not publish", "path": "/private/path",
            }
            rows = [row, row] if duplicate else [row]
            (root / "audit.json").write_text(json.dumps({"finished_tasks": len(rows), "tasks": rows}))
            (root / "combined.json").write_text(json.dumps({
                "analysis": "development", "tasks": [{"id": "task", "preview": "secret image"}],
                "retired_tasks": [], "models": [{"model": "model", "secret": "token"}],
                "secret": "hidden",
            }))
            result = subprocess.run([
                sys.executable, str(SCRIPT), "--combined", str(root / "combined.json"),
                "--pilot-audit", str(root / "audit.json"), "--output", str(root / "output.json"),
            ], capture_output=True, text=True)
            output = (root / "output.json").read_text() if (root / "output.json").exists() else ""
            return result, output

    def test_public_allowlist(self):
        result, output = self.export()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("private", output)
        self.assertNotIn("secret", output)
        self.assertEqual(json.loads(output)["pilot"][0]["tokens"], 2)

    def test_unverified_replay_rejected(self):
        result, output = self.export(verified=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, "")

    def test_duplicate_attempt_rejected(self):
        result, output = self.export(duplicate=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Duplicate", result.stderr)
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()
