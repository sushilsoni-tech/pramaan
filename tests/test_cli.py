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
            report = (valid / "report.html").read_text(encoding="utf-8")
            self.assertIn("Can I accept it yet? Not yet.", report)
            self.assertIn("Technical detail", report)
            self.assertIn("--expected-key", report)
            self.assertIn("Not independently checked", report)
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

    def test_editorial_example_writes_separate_result_files(self):
        with tempfile.TemporaryDirectory(prefix="pramaan-editorial-cli-") as temp:
            root = Path(temp)
            bundle = root / "bundle"
            result_html = root / "verification-result.html"
            result_json = root / "verification-result.json"
            built = self.run_cli("example", "editorial", str(bundle), "--case", "valid")
            self.assertEqual(0, built.returncode, built.stdout + built.stderr)
            verified = self.run_cli(
                "verify",
                str(bundle),
                "--result-html",
                str(result_html),
                "--result-json",
                str(result_json),
            )
            self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)
            self.assertIn("Pramaan signed-file integrity: PASS", verified.stdout)
            self.assertIn("Pramaan overall verification: PASS", verified.stdout)
            self.assertIn("not_satisfied=0", verified.stdout)
            self.assertTrue(result_html.is_file())
            self.assertTrue(result_json.is_file())
            self.assertFalse((bundle / "verification-result.html").exists())

    def test_adverse_editorial_result_exits_nonzero(self):
        with tempfile.TemporaryDirectory(prefix="pramaan-editorial-adverse-") as temp:
            bundle = Path(temp) / "late-review"
            built = self.run_cli("example", "editorial", str(bundle), "--case", "post-publication")
            self.assertEqual(0, built.returncode, built.stdout + built.stderr)
            verified = self.run_cli("verify", str(bundle), "--json")
            self.assertEqual(1, verified.returncode, verified.stdout + verified.stderr)
            payload = json.loads(verified.stdout)
            self.assertFalse(payload["valid"])
            self.assertTrue(payload["integrity_valid"])
            self.assertTrue(payload["editorial_summary"]["has_not_satisfied"])

    def test_policy_failure_demo_is_reachable(self):
        with tempfile.TemporaryDirectory(prefix="pramaan-policy-demo-") as temp:
            bundle = Path(temp) / "policy-failure"
            built = self.run_cli("example", "editorial", str(bundle), "--case", "policy-failure")
            self.assertEqual(0, built.returncode, built.stdout + built.stderr)
            verified = self.run_cli("verify", str(bundle), "--json")
            self.assertEqual(1, verified.returncode, verified.stdout + verified.stderr)
            payload = json.loads(verified.stdout)
            self.assertTrue(payload["integrity_valid"])
            self.assertFalse(payload["valid"])

    def test_shipped_editorial_samples_verify_as_documented(self):
        samples = Path(__file__).resolve().parents[1] / "samples"
        passed = self.run_cli("verify", str(samples / "editorial-pass"), "--json")
        self.assertEqual(0, passed.returncode, passed.stdout + passed.stderr)
        pass_payload = json.loads(passed.stdout)
        self.assertTrue(pass_payload["valid"])
        self.assertTrue(pass_payload["integrity_valid"])
        self.assertEqual(0, pass_payload["editorial_summary"]["not_satisfied"])
        self.assertFalse(pass_payload["editorial_summary"]["has_not_satisfied"])

        failed = self.run_cli("verify", str(samples / "editorial-fail-missing-reviewer"), "--json")
        self.assertEqual(1, failed.returncode, failed.stdout + failed.stderr)
        fail_payload = json.loads(failed.stdout)
        self.assertFalse(fail_payload["valid"])
        self.assertTrue(fail_payload["integrity_valid"])
        self.assertGreater(fail_payload["editorial_summary"]["not_satisfied"], 0)
        self.assertTrue(fail_payload["editorial_summary"]["has_not_satisfied"])


if __name__ == "__main__":
    unittest.main()
