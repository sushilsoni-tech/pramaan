import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        src = str(Path(__file__).resolve().parents[1] / "src")
        env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        return subprocess.run(
            [sys.executable, "-m", "pramaan", *args],
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=env,
            timeout=30,
        )

    def test_demo_pass_then_fail(self):
        with tempfile.TemporaryDirectory(prefix="pramaan-cli-") as temp:
            root = Path(temp)
            valid = root / "valid"
            invalid = root / "invalid"
            built = self.run_cli("example", "two-agent", str(valid))
            self.assertEqual(0, built.returncode, built.stderr)
            passed = self.run_cli("verify", str(valid))
            self.assertEqual(0, passed.returncode, passed.stdout + passed.stderr)
            self.assertIn("Pramaan verification: PASS", passed.stdout)
            self.assertIn("Signer trust: UNPINNED", passed.stdout)
            self.assertIn("Policy enforced: evidence_links=on", passed.stdout)
            fingerprint = json.loads((valid / "bundle.json").read_text(encoding="utf-8"))["public_key_fingerprint"]
            pinned = self.run_cli("verify", str(valid), "--expected-key", fingerprint)
            self.assertEqual(0, pinned.returncode, pinned.stdout + pinned.stderr)
            self.assertIn("Signer trust: PINNED", pinned.stdout)
            tampered = self.run_cli("tamper", str(valid), "--case", "missing-approval", "--output", str(invalid))
            self.assertEqual(0, tampered.returncode, tampered.stderr)
            failed = self.run_cli("verify", str(invalid))
            self.assertEqual(1, failed.returncode, failed.stdout + failed.stderr)
            self.assertIn("MISSING_REQUIRED_APPROVAL", failed.stdout)
            self.assertIn("SUBJECT_DIGEST_MISMATCH", failed.stdout)


if __name__ == "__main__":
    unittest.main()
