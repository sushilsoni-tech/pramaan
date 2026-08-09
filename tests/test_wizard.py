import base64
import json
import os
import stat
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from pramaan.canonical import sha256_bytes
from pramaan.verify import verify_bundle
from pramaan.wizard import RecordCreationError, WizardApplication, create_editorial_record
from pramaan.wizard_ui import render_wizard_html


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pramaan-wizard-tests-")
        self.root = Path(self.temp.name)
        self.content = b"Final publication text.\n"

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, review_state: str = "complete") -> dict:
        payload = {
            "file_name": "final publication.txt",
            "file_base64": base64.b64encode(self.content).decode("ascii"),
            "file_hash": sha256_bytes(self.content),
            "title": "Community update",
            "publication_context": "Independent local newsletter",
            "ai_system": "ChatGPT",
            "ai_model": "not recorded",
            "ai_contribution": "Sections or passages",
            "generation_at": "2026-08-04T08:00:00+10:00",
            "review_state": review_state,
            "reviewer_name": "Maya Chen",
            "reviewer_role": "Editor",
            "review_at": "2026-08-04T08:30:00+10:00",
            "review_duration_minutes": 30,
            "review_scopes": ["facts_claims", "whole_item"],
            "competence_basis": "Editor with six years of local reporting experience.",
            "changes_made": True,
            "change_summary": "Corrected two dates and clarified the source attribution.",
            "partial_review_note": "Sources and calculations were not reviewed.",
            "responsibility_name": "Maya Chen",
            "responsibility_role": "editor",
            "correction_contact": "corrections@example.test",
            "publication_at": "2026-08-04T09:00:00+10:00",
            "disclosure_state": "item",
            "declaration_confirmed": True,
        }
        if review_state != "complete":
            for key in (
                "reviewer_name",
                "reviewer_role",
                "review_at",
                "review_duration_minutes",
                "review_scopes",
                "competence_basis",
                "changes_made",
                "change_summary",
            ):
                payload.pop(key)
        if review_state != "partial":
            payload["partial_review_note"] = ""
        return payload

    def create(self, payload: dict):
        return create_editorial_record(
            payload,
            self.root / "records",
            self.root / "keys" / "producer-private.pem",
        )

    def test_complete_review_creates_verified_downloadable_record(self):
        record = self.create(self.payload())
        self.assertTrue(record.valid)
        self.assertTrue(record.integrity_valid)
        self.assertTrue(record.report_path.is_file())
        self.assertTrue(record.result_json_path.is_file())
        self.assertTrue(record.zip_path.is_file())
        self.assertEqual(0, record.editorial_counts["not_satisfied"])
        result_payload = json.loads(record.result_json_path.read_text(encoding="utf-8"))
        change_check = next(
            item for item in result_payload["editorial_checks"]
            if item["check_id"] == "review.change_evidence"
        )
        self.assertEqual("unverifiable", change_check["status"])
        html = record.report_path.read_text(encoding="utf-8")
        self.assertIn("producer declared complete substantive review", html.lower())
        self.assertIn(record.file_hash, html)
        self.assertIn("30 minutes", html)
        self.assertIn("six years of local reporting", html)
        with zipfile.ZipFile(record.zip_path) as archive:
            names = archive.namelist()
        self.assertFalse(any(name.endswith("verification-result.html") for name in names))
        self.assertFalse(any(name.endswith("verification-result.json") for name in names))
        self.assertIn("bundle.json", names)
        self.assertIn("editorial-record.json", names)
        self.assertFalse(any(name.startswith(f"{record.record_id}/") for name in names))
        self.assertFalse(any("private" in name.lower() or name.endswith(".pem") and "public-key" not in name for name in names))
        extracted = self.root / "extracted"
        with zipfile.ZipFile(record.zip_path) as archive:
            archive.extractall(extracted)
        self.assertTrue(verify_bundle(extracted).valid)

    def test_no_review_is_signed_but_cannot_pass(self):
        record = self.create(self.payload("none"))
        self.assertFalse(record.valid)
        self.assertTrue(record.integrity_valid)
        html = record.report_path.read_text(encoding="utf-8")
        self.assertIn("No substantive human review is claimed for this item", html)
        payload = json.loads(record.result_json_path.read_text(encoding="utf-8"))
        self.assertEqual("none", payload["editorial_record"]["review_state"])
        self.assertGreater(payload["editorial_summary"]["not_satisfied"], 0)

    def test_partial_review_is_preserved_and_cannot_pass(self):
        record = self.create(self.payload("partial"))
        self.assertFalse(record.valid)
        self.assertTrue(record.integrity_valid)
        payload = json.loads(record.result_json_path.read_text(encoding="utf-8"))
        self.assertEqual("partial", payload["editorial_record"]["review_state"])
        self.assertEqual(
            "Sources and calculations were not reviewed.",
            payload["editorial_record"]["partial_review_note"],
        )
        self.assertIn("partial or incomplete review", record.report_path.read_text(encoding="utf-8"))

    def test_impossible_timeline_is_rejected(self):
        payload = self.payload()
        payload["review_at"] = "2026-08-04T07:30:00+10:00"
        with self.assertRaisesRegex(RecordCreationError, "review time cannot be before"):
            self.create(payload)

    def test_review_duration_cannot_exceed_generation_to_review_window(self):
        payload = self.payload()
        payload["review_at"] = "2026-08-04T08:01:00+10:00"
        payload["review_duration_minutes"] = 10080
        with self.assertRaisesRegex(RecordCreationError, "review duration cannot be longer"):
            self.create(payload)

    def test_same_minute_generation_and_review_allows_one_minute_duration(self):
        payload = self.payload()
        payload["review_at"] = "2026-08-04T08:00:00+10:00"
        payload["review_duration_minutes"] = 1
        record = self.create(payload)
        self.assertTrue(record.valid)

    def test_not_yet_published_record_does_not_require_publication_time(self):
        payload = self.payload()
        payload["disclosure_state"] = "not_published"
        payload["publication_at"] = ""
        record = self.create(payload)
        result_payload = json.loads(record.result_json_path.read_text(encoding="utf-8"))

        self.assertTrue(record.valid)
        self.assertEqual("unknown", result_payload["editorial_record"]["disclosure_state"])
        self.assertIsNone(result_payload["editorial_record"]["published_at"])
        timing = next(
            item for item in result_payload["editorial_checks"]
            if item["check_id"] == "review.timing"
        )
        self.assertEqual("unverifiable", timing["status"])

    def test_future_publication_time_is_rejected(self):
        payload = self.payload()
        payload["publication_at"] = "2030-01-01T00:00:00+10:00"
        with self.assertRaisesRegex(RecordCreationError, "publication time cannot be in the future"):
            self.create(payload)

    def test_file_is_rehashed_at_creation(self):
        payload = self.payload()
        payload["file_hash"] = "0" * 64
        with self.assertRaisesRegex(RecordCreationError, "changed after selection"):
            self.create(payload)

    def test_tone_only_does_not_qualify_as_substantive_review(self):
        payload = self.payload()
        payload["review_scopes"] = ["tone_framing"]
        with self.assertRaisesRegex(RecordCreationError, "content review scope"):
            self.create(payload)

    def test_uploaded_filename_is_normalized_without_path_traversal(self):
        payload = self.payload()
        payload["file_name"] = "../../secret/Report Final.PDF"
        record = self.create(payload)
        self.assertEqual("report-final.pdf", record.stored_file_name)
        self.assertTrue((record.bundle_dir / "artifacts" / "report-final.pdf").is_file())
        self.assertFalse((record.record_dir / "secret").exists())

    def test_signing_identity_persists_across_records(self):
        first = self.create(self.payload())
        second_payload = self.payload()
        second_payload["title"] = "Second community update"
        second = self.create(second_payload)
        self.assertEqual(first.signer_fingerprint, second.signer_fingerprint)

    @unittest.skipUnless(os.name == "posix", "POSIX permission bits are not enforced on Windows")
    def test_posix_signing_key_permissions_are_restrictive(self):
        self.create(self.payload())
        key = self.root / "keys" / "producer-private.pem"
        self.assertEqual(0o600, stat.S_IMODE(key.stat().st_mode))
        self.assertEqual(0o700, stat.S_IMODE(key.parent.stat().st_mode))

    def test_ui_is_offline_and_keeps_truth_boundary_visible(self):
        html = render_wizard_html("/session/test-token")
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)
        self.assertIn("You are recording what you did", html)
        self.assertIn("does not certify compliance", html)
        self.assertIn("Step 1 of 6", html)
        self.assertIn("Partial or incomplete review", html)
        self.assertIn("Signer fingerprint", html)
        self.assertIn("Review time spent is longer", html)
        self.assertIn("Download signed bundle", html)
        self.assertIn("run Pramaan verification", html)
        self.assertIn("Published date is required unless the item is not yet published", html)
        self.assertIn("Published cannot be in the future", html)
        self.assertIn("create.disabled=n!==6", html)
        self.assertIn("current!==6||create.hidden||create.disabled", html)
        self.assertIn("The file could not be read. Re-select it to continue.", html)

    def test_http_session_token_is_required_for_creation(self):
        app = WizardApplication(
            self.root / "http-records",
            self.root / "http-key" / "producer-private.pem",
            token="known-token",
        )
        server = app.server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/session/known-token/") as response:
                self.assertEqual(200, response.status)
                self.assertIn("Create record", response.read().decode("utf-8"))
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/session/known-token/create",
                data=json.dumps(self.payload()).encode("utf-8"),
                headers={"Content-Type": "application/json", "X-Pramaan-Session": "wrong"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(403, caught.exception.code)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_report_and_download_routes_serve_created_record(self):
        app = WizardApplication(
            self.root / "route-records",
            self.root / "route-key" / "producer-private.pem",
            token="route-token",
        )
        record = create_editorial_record(self.payload(), app.output_root, app.private_key_path)
        app.records[record.record_id] = record
        server = app.server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}/session/route-token/records/{record.record_id}"
        try:
            with urllib.request.urlopen(base + "/report") as response:
                self.assertEqual("text/html; charset=utf-8", response.headers["Content-Type"])
                self.assertIn("Verification is not truth", response.read().decode("utf-8"))
            with urllib.request.urlopen(base + "/download") as response:
                self.assertEqual("application/zip", response.headers["Content-Type"])
                self.assertIn("attachment", response.headers["Content-Disposition"])
                self.assertTrue(response.read().startswith(b"PK"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
