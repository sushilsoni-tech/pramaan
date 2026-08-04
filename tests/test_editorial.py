import json
import tempfile
import unittest
from pathlib import Path

from pramaan.bundle import Recorder
from pramaan.canonical import sha256_file, write_json
from pramaan.crypto import sign_statement, verify_envelope
from pramaan.editorial import EDITORIAL_CHECK_IDS, evaluate_editorial_profile
from pramaan.examples import SYSTEM, build_editorial_example, build_two_agent_example, default_policy
from pramaan.verify import verify_bundle
from pramaan.verification_report import render_verification_report, write_verification_outputs


class EditorialProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pramaan-editorial-tests-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def check_map(result):
        return {item.check_id: item for item in result.editorial_checks}

    def test_identical_event_timestamps_raise_warning(self):
        recorder = Recorder("same-time", "vendor", "Vendor")
        timestamp = "2026-08-03T01:00:00Z"
        recorder.record("run.started", SYSTEM, {"summary": "Started"}, occurred_at=timestamp)
        recorder.record("run.completed", SYSTEM, {"summary": "Completed"}, occurred_at=timestamp)
        bundle = recorder.finalize(self.root / "same-time", default_policy("empty-policy"))
        result = verify_bundle(bundle)
        self.assertIn("UNCORROBORATED_EVENT_TIMESTAMPS", {item.code for item in result.findings})

    def test_valid_editorial_record_has_no_unsatisfied_checks(self):
        bundle = build_editorial_example(self.root / "valid", case="valid")
        result = verify_bundle(bundle)
        checks = self.check_map(result)
        self.assertTrue(result.valid)
        self.assertEqual(set(checks), set(EDITORIAL_CHECK_IDS))
        self.assertNotIn("not_satisfied", {item.status for item in checks.values()})
        self.assertIn("unverifiable", {item.status for item in checks.values()})
        self.assertEqual(checks["reviewer.identity_bound"].status, "unverifiable")

    def test_missing_reviewer_and_responsibility_are_not_satisfied(self):
        bundle = build_editorial_example(self.root / "missing-reviewer", case="missing-reviewer")
        checks = self.check_map(verify_bundle(bundle))
        self.assertEqual(checks["review.substantive_recorded"].status, "not_satisfied")
        self.assertEqual(checks["responsibility.named"].status, "not_satisfied")

    def test_review_after_publication_is_prominent_finding(self):
        bundle = build_editorial_example(self.root / "post-publication", case="post-publication")
        result = verify_bundle(bundle)
        checks = self.check_map(result)
        self.assertFalse(result.valid)
        self.assertEqual(checks["review.timing"].status, "not_satisfied")
        self.assertIn("after publication", checks["review.timing"].reason.lower())
        self.assertIn("EDITORIAL_REVIEW_AFTER_PUBLICATION", {item.code for item in result.findings})

    def test_review_before_latest_generation_is_not_satisfied(self):
        bundle = build_editorial_example(self.root / "regenerated", case="valid")
        profile = json.loads((bundle / "editorial-record.json").read_text(encoding="utf-8"))
        profile["generation_events"].append(
            {
                "system_id": "rewrite-agent",
                "system_name": "Rewrite Agent",
                "model": "producer-supplied",
                "model_version": "unknown",
                "occurred_at": "2026-08-02T08:50:00Z",
            }
        )
        evaluation = evaluate_editorial_profile(bundle, profile, core_integrity_valid=True)
        checks = {item.check_id: item for item in evaluation.checks}
        self.assertEqual(checks["review.timing"].status, "not_satisfied")
        self.assertIn("latest recorded generation", checks["review.timing"].reason.lower())

    def test_outputs_are_offline_structured_and_do_not_change_bundle(self):
        bundle = build_editorial_example(self.root / "output-source", case="valid")
        before = {path.relative_to(bundle).as_posix() for path in bundle.rglob("*") if path.is_file()}
        result = verify_bundle(bundle)
        html_path = self.root / "result" / "verification-result.html"
        json_path = self.root / "result" / "verification-result.json"
        write_verification_outputs(result, html_path=html_path, json_path=json_path)
        after = {path.relative_to(bundle).as_posix() for path in bundle.rglob("*") if path.is_file()}

        html = html_path.read_text(encoding="utf-8")
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(before, after)
        self.assertTrue(verify_bundle(bundle).valid)
        self.assertIn("Verification is not truth", html)
        self.assertIn('role="tablist"', html)
        self.assertIn("Plain language", html)
        self.assertIn("Technical detail", html)
        self.assertNotIn("http", html.lower())
        self.assertNotIn("fetch(", html.lower())
        self.assertNotIn("@font-face", html.lower())
        self.assertIn("assurance_boundary", payload)
        self.assertIn("limitations", payload)
        self.assertEqual(payload["editorial_check_set_version"], "0.1")
        self.assertEqual(payload["bundle"], "output-source")
        self.assertNotIn(str(self.root), html)
        self.assertNotIn(str(self.root), json_path.read_text(encoding="utf-8"))

    def test_verification_output_never_makes_legal_determination(self):
        bundle = build_editorial_example(self.root / "wording", case="valid")
        html_path = self.root / "wording-result.html"
        write_verification_outputs(verify_bundle(bundle), html_path=html_path)
        rendered = html_path.read_text(encoding="utf-8").lower()
        banned = (
            "article 50 compliant",
            "exemption satisfied",
            "no labelling required",
            "no labeling required",
        )
        self.assertFalse([phrase for phrase in banned if phrase in rendered])

    def test_editorial_artifact_path_cannot_escape_bundle(self):
        bundle = build_editorial_example(self.root / "path-source", case="valid")
        profile_path = bundle / "editorial-record.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["item"]["published_artifact"] = "../../outside.txt"
        profile["item"]["content_hash"] = sha256_file(bundle / "artifacts" / "published-item.txt")
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        result = verify_bundle(bundle)
        self.assertFalse(result.valid)
        self.assertEqual(result.editorial_profile_state, "unavailable")
        self.assertFalse(any(item.status == "satisfied" for item in result.editorial_checks))

    def test_policy_failure_does_not_become_integrity_failure(self):
        bundle = build_editorial_example(self.root / "policy-failure", case="policy-failure")
        result = verify_bundle(bundle)
        checks = self.check_map(result)
        self.assertFalse(result.valid)
        self.assertTrue(result.integrity_valid)
        self.assertEqual(checks["record.integrity"].status, "satisfied")
        html = render_verification_report(result)
        self.assertIn("Signed-file integrity", html)
        self.assertIn("status-valid", html)
        self.assertNotIn("One or more integrity errors were found", html)
        self.assertIn("Overall verification is <span class=\"status status-overall-fail\">FAIL</span>", html)
        self.assertIn("declared policy, trust, or record-structure check failed", html)

    def test_missing_profile_has_explicit_not_evaluated_state(self):
        bundle = build_two_agent_example(self.root / "no-profile")
        result = verify_bundle(bundle)
        html = render_verification_report(result)
        self.assertEqual(result.editorial_profile_state, "absent")
        self.assertIn("No editorial profile was evaluated", html)
        self.assertNotIn("No unresolved editorial checks were reported", html)

    def test_early_failure_marks_present_profile_unavailable(self):
        bundle = build_editorial_example(self.root / "early-failure", case="valid")
        (bundle / "public-key.pem").unlink()
        result = verify_bundle(bundle)
        html = render_verification_report(result)
        self.assertEqual(result.editorial_profile_state, "unavailable")
        self.assertIn("Editorial profile unavailable", html)
        self.assertNotIn("contains no signed Editorial Responsibility Record", html)

    def test_plain_integrity_result_names_unpinned_signer(self):
        bundle = build_editorial_example(self.root / "unpinned", case="valid")
        result = verify_bundle(bundle)
        self.assertFalse(result.signer_pinned)
        html = render_verification_report(result)
        self.assertIn("signer identity is not independently established", html)
        self.assertIn(result.signer_fingerprint, html)

    def test_failed_signer_checks_are_explicit_in_human_report(self):
        bundle = build_editorial_example(self.root / "signer-failure", case="valid")
        for expected_key in ("0" * 64, "malformed"):
            with self.subTest(expected_key=expected_key):
                result = verify_bundle(bundle, expected_key=expected_key)
                html = render_verification_report(result)
                self.assertFalse(result.valid)
                self.assertIn("independent signer check FAILED", html)
                self.assertIn(result.signer_fingerprint, html)
                self.assertNotIn("signer identity is not independently established", html)

    def test_signed_unsupported_editorial_profile_cannot_pass(self):
        key = self.root / "unsupported-profile-private.pem"
        bundle = build_editorial_example(
            self.root / "unsupported-profile",
            case="valid",
            private_key_path=key,
        )
        profile_path = bundle / "editorial-record.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["profile_version"] = "0.2"
        write_json(profile_path, profile)

        envelope_path = bundle / "attestation.dsse.json"
        statement, fingerprint = verify_envelope(
            json.loads(envelope_path.read_text(encoding="utf-8")),
            bundle / "public-key.pem",
        )
        editorial_subject = next(
            item for item in statement["subject"] if item["name"] == "editorial-record.json"
        )
        editorial_subject["digest"]["sha256"] = sha256_file(profile_path)
        write_json(envelope_path, sign_statement(statement, key, fingerprint))

        result = verify_bundle(bundle)
        html = render_verification_report(result)
        self.assertFalse(result.valid)
        self.assertEqual(result.editorial_profile_state, "unavailable")
        self.assertIn("INVALID_EDITORIAL_PROFILE", {item.code for item in result.findings})
        self.assertIn("Overall verification is <span class=\"status status-overall-fail\">FAIL</span>", html)

    def test_producer_text_cannot_inject_reserved_assurance_phrase(self):
        bundle = build_editorial_example(self.root / "producer-wording", case="valid")
        result = verify_bundle(bundle)
        result.editorial_record["item_title"] = "Article 50 compliant"
        result.editorial_responsibility["person_or_entity"] = "Exemption satisfied"
        html = render_verification_report(result).lower()
        self.assertNotIn("article 50 compliant", html)
        self.assertNotIn("exemption satisfied", html)
        self.assertIn("reserved assurance phrase removed", html)

    def test_incomplete_substantive_review_is_not_satisfied(self):
        bundle = build_editorial_example(self.root / "incomplete-review", case="valid")
        profile = json.loads((bundle / "editorial-record.json").read_text(encoding="utf-8"))
        profile["review_events"] = [{"review_type": "substantive", "changes_made": False}]
        evaluation = evaluate_editorial_profile(bundle, profile, core_integrity_valid=True)
        checks = {item.check_id: item for item in evaluation.checks}
        self.assertEqual(checks["review.substantive_recorded"].status, "not_satisfied")

    def test_change_evidence_requires_sha256_digest(self):
        bundle = build_editorial_example(self.root / "bad-change-hash", case="valid")
        profile = json.loads((bundle / "editorial-record.json").read_text(encoding="utf-8"))
        profile["review_events"][0].pop("post_review_content_hash")
        profile["review_events"][0]["diff_hash"] = "x"
        evaluation = evaluate_editorial_profile(bundle, profile, core_integrity_valid=True)
        checks = {item.check_id: item for item in evaluation.checks}
        self.assertEqual(checks["review.change_evidence"].status, "not_satisfied")

    def test_sequential_review_hashes_compare_only_latest_change_to_publication(self):
        bundle = build_editorial_example(self.root / "sequential-reviews", case="valid")
        profile = json.loads((bundle / "editorial-record.json").read_text(encoding="utf-8"))
        final_review = profile["review_events"][0]
        final_review["occurred_at"] = "2026-08-02T08:40:00Z"
        profile["review_events"].insert(
            0,
            {
                **final_review,
                "reviewer_id": "copy-editor-01",
                "reviewer_display_name": "Asha Patel",
                "occurred_at": "2026-08-02T08:20:00Z",
                "post_review_content_hash": "1" * 64,
            },
        )
        evaluation = evaluate_editorial_profile(bundle, profile, core_integrity_valid=True)
        checks = {item.check_id: item for item in evaluation.checks}
        self.assertEqual(checks["review.change_evidence"].status, "satisfied")

    def test_bundle_folder_name_is_treated_as_producer_controlled(self):
        bundle = build_editorial_example(self.root / "Article 50 compliant", case="valid")
        html = render_verification_report(verify_bundle(bundle)).lower()
        self.assertNotIn("article 50 compliant", html)
        self.assertIn("reserved assurance phrase removed", html)


if __name__ == "__main__":
    unittest.main()
