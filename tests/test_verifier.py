import json
import tempfile
import unittest
from pathlib import Path

from pramaan.bundle import Recorder
from pramaan.canonical import canonical_json_bytes, sha256_file, write_json
from pramaan.crypto import generate_keypair, sign_statement, verify_envelope
from pramaan.examples import HUMAN, RESEARCH_AGENT, REVIEW_AGENT, SYSTEM, build_two_agent_example, default_policy
from pramaan.tamper import create_tampered_copy
from pramaan.verify import verify_bundle


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pramaan-tests-")
        self.root = Path(self.temp.name)
        self.valid = self.root / "valid"
        build_two_agent_example(self.valid)

    def tearDown(self):
        self.temp.cleanup()

    def codes(self, result):
        return {finding.code for finding in result.findings}

    def test_valid_bundle_passes_with_explicit_assurance_warning(self):
        result = verify_bundle(self.valid)
        self.assertTrue(result.valid)
        self.assertIn("VERIFIED", self.codes(result))
        self.assertIn("SELF_ATTESTATION_LIMIT", self.codes(result))

    def test_modified_event_is_detected(self):
        tampered = create_tampered_copy(self.valid, self.root / "modified", "modified-event")
        result = verify_bundle(tampered)
        self.assertFalse(result.valid)
        self.assertIn("SUBJECT_DIGEST_MISMATCH", self.codes(result))

    def test_missing_artifact_is_detected(self):
        tampered = create_tampered_copy(self.valid, self.root / "missing-artifact", "missing-artifact")
        result = verify_bundle(tampered)
        self.assertFalse(result.valid)
        self.assertIn("MISSING_SUBJECT", self.codes(result))
        self.assertIn("MISSING_ARTIFACT", self.codes(result))

    def test_broken_evidence_link_is_named(self):
        tampered = create_tampered_copy(self.valid, self.root / "broken-link", "broken-evidence-link")
        result = verify_bundle(tampered)
        self.assertFalse(result.valid)
        self.assertIn("BROKEN_EVIDENCE_LINK", self.codes(result))

    def test_missing_required_approval_is_named(self):
        tampered = create_tampered_copy(self.valid, self.root / "missing-approval", "missing-approval")
        result = verify_bundle(tampered)
        self.assertFalse(result.valid)
        self.assertIn("MISSING_REQUIRED_APPROVAL", self.codes(result))

    def test_wrong_independent_signer_fingerprint_fails(self):
        result = verify_bundle(self.valid, expected_key="0" * 64)
        self.assertFalse(result.valid)
        self.assertFalse(result.signer_pinned)
        self.assertIn("UNTRUSTED_SIGNER", self.codes(result))

    def test_non_string_summary_returns_finding_not_traceback(self):
        events_path = self.valid / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        events[0]["data"]["summary"] = 123
        events_path.write_bytes(b"".join(canonical_json_bytes(event) + b"\n" for event in events))
        result = verify_bundle(self.valid)
        self.assertFalse(result.valid)
        self.assertIn("SUBJECT_DIGEST_MISMATCH", self.codes(result))

    def test_private_key_is_not_in_bundle(self):
        self.assertFalse(any(path.name.endswith("private.pem") for path in self.valid.rglob("*")))
        self.assertFalse(any(path.name.endswith("producer-private.pem") for path in self.root.iterdir()))

    def test_legitimately_signed_broken_link_still_fails_completeness(self):
        source = self.root / "source.txt"
        source.write_text("Source evidence.\n", encoding="utf-8")
        recorder = Recorder("broken-link-run", "vendor", "Vendor")
        recorder.record("run.started", SYSTEM, {"summary": "Started"})
        recorder.add_artifact("evidence-real", source, RESEARCH_AGENT)
        recorder.record(
            "claim.asserted",
            RESEARCH_AGENT,
            {"claim_id": "claim-1", "text": "Material claim", "material": True, "evidence_refs": ["evidence-absent"]},
        )
        recorder.record(
            "validation.completed",
            REVIEW_AGENT,
            {"validation_id": "v-1", "name": "citation_check", "status": "passed", "target_refs": ["claim-1"]},
        )
        recorder.record(
            "approval.recorded",
            HUMAN,
            {"approval_id": "a-1", "role": "human_reviewer", "status": "approved", "target_refs": ["claim-1"]},
        )
        recorder.record("run.completed", SYSTEM, {"summary": "Completed"})
        bundle = recorder.finalize(self.root / "signed-broken", default_policy())
        result = verify_bundle(bundle)
        self.assertFalse(result.valid)
        self.assertIn("BROKEN_EVIDENCE_LINK", self.codes(result))

    def test_legitimately_signed_missing_approval_still_fails_policy(self):
        source = self.root / "source-approval.txt"
        source.write_text("Source evidence.\n", encoding="utf-8")
        recorder = Recorder("missing-approval-run", "vendor", "Vendor")
        recorder.record("run.started", SYSTEM, {"summary": "Started"})
        recorder.add_artifact("evidence-1", source, RESEARCH_AGENT)
        recorder.record(
            "claim.asserted",
            RESEARCH_AGENT,
            {"claim_id": "claim-1", "text": "Material claim", "material": True, "evidence_refs": ["evidence-1"]},
        )
        recorder.record(
            "validation.completed",
            REVIEW_AGENT,
            {"validation_id": "v-1", "name": "citation_check", "status": "passed", "target_refs": ["claim-1"]},
        )
        recorder.record("run.completed", SYSTEM, {"summary": "Completed"})
        bundle = recorder.finalize(self.root / "signed-no-approval", default_policy())
        result = verify_bundle(bundle)
        self.assertFalse(result.valid)
        self.assertIn("MISSING_REQUIRED_APPROVAL", self.codes(result))

    def test_duplicate_event_id_is_detected_even_when_digest_also_fails(self):
        events_path = self.valid / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        events[1]["event_id"] = events[0]["event_id"]
        events_path.write_bytes(b"".join(canonical_json_bytes(event) + b"\n" for event in events))
        result = verify_bundle(self.valid)
        self.assertFalse(result.valid)
        self.assertIn("DUPLICATE_EVENT_ID", self.codes(result))

    def test_signed_subject_list_must_cover_events(self):
        key = self.root / "coverage-private.pem"
        bundle = self.root / "coverage"
        from pramaan.examples import build_two_agent_example

        # Build explicitly so the test can re-sign a deliberately incomplete statement.
        source = self.root / "coverage-source.txt"
        source.write_text("Evidence.\n", encoding="utf-8")
        recorder = Recorder("coverage-run", "vendor", "Vendor")
        recorder.record("run.started", SYSTEM, {"summary": "Started"})
        recorder.add_artifact("evidence-1", source, RESEARCH_AGENT)
        recorder.record("claim.asserted", RESEARCH_AGENT, {"claim_id": "claim-1", "text": "Claim", "material": True, "evidence_refs": ["evidence-1"]})
        recorder.record("validation.completed", REVIEW_AGENT, {"validation_id": "v-1", "name": "citation_check", "status": "passed", "target_refs": ["claim-1"]})
        recorder.record("approval.recorded", HUMAN, {"approval_id": "a-1", "role": "human_reviewer", "status": "approved", "target_refs": ["claim-1"]})
        recorder.record("run.completed", SYSTEM, {"summary": "Completed"})
        recorder.finalize(bundle, default_policy(), private_key_path=key)
        statement, fingerprint = verify_envelope(json.loads((bundle / "attestation.dsse.json").read_text(encoding="utf-8")), bundle / "public-key.pem")
        statement["subject"] = [item for item in statement["subject"] if item["name"] != "events.jsonl"]
        write_json(bundle / "attestation.dsse.json", sign_statement(statement, key, fingerprint))
        result = verify_bundle(bundle)
        self.assertFalse(result.valid)
        self.assertIn("UNATTESTED_FILE", self.codes(result))

    def test_policy_boolean_string_is_rejected(self):
        source = self.root / "typed-policy-source.txt"
        source.write_text("Evidence.\n", encoding="utf-8")
        recorder = Recorder("typed-policy", "vendor", "Vendor")
        recorder.record("run.started", SYSTEM, {"summary": "Started"})
        recorder.add_artifact("evidence-1", source, RESEARCH_AGENT)
        recorder.record("claim.asserted", RESEARCH_AGENT, {"claim_id": "claim-1", "text": "Claim", "material": True, "evidence_refs": []})
        recorder.record("validation.completed", REVIEW_AGENT, {"validation_id": "v-1", "name": "citation_check", "status": "passed", "target_refs": ["claim-1"]})
        recorder.record("approval.recorded", HUMAN, {"approval_id": "a-1", "role": "human_reviewer", "status": "approved", "target_refs": ["claim-1"]})
        recorder.record("run.completed", SYSTEM, {"summary": "Completed"})
        policy = default_policy()
        policy["material_claims_require_evidence"] = "true"
        bundle = recorder.finalize(self.root / "typed-policy", policy)
        result = verify_bundle(bundle)
        self.assertFalse(result.valid)
        self.assertIn("INVALID_POLICY_SCHEMA", self.codes(result))

    def test_windows_drive_path_is_rejected(self):
        recorder = Recorder("windows-path", "vendor", "Vendor")
        recorder.record("run.started", SYSTEM, {"summary": "Started"})
        recorder.record(
            "evidence.registered",
            RESEARCH_AGENT,
            {"evidence_id": "outside", "artifact_path": "C:/Windows/win.ini", "sha256": "0" * 64, "media_type": "text/plain"},
        )
        recorder.record("claim.asserted", RESEARCH_AGENT, {"claim_id": "claim-1", "text": "Claim", "material": True, "evidence_refs": ["outside"]})
        recorder.record("validation.completed", REVIEW_AGENT, {"validation_id": "v-1", "name": "citation_check", "status": "passed", "target_refs": ["claim-1"]})
        recorder.record("approval.recorded", HUMAN, {"approval_id": "a-1", "role": "human_reviewer", "status": "approved", "target_refs": ["claim-1"]})
        recorder.record("run.completed", SYSTEM, {"summary": "Completed"})
        result = verify_bundle(recorder.finalize(self.root / "windows-path", default_policy()))
        self.assertFalse(result.valid)
        self.assertIn("UNSAFE_ARTIFACT_PATH", self.codes(result))

    def test_signed_but_stale_report_is_rejected(self):
        key = self.root / "report-private.pem"
        source = self.root / "report-source.txt"
        source.write_text("Evidence.\n", encoding="utf-8")
        recorder = Recorder("report-run", "vendor", "Vendor")
        recorder.record("run.started", SYSTEM, {"summary": "Started"})
        recorder.add_artifact("evidence-1", source, RESEARCH_AGENT)
        recorder.record("claim.asserted", RESEARCH_AGENT, {"claim_id": "claim-1", "text": "Claim", "material": True, "evidence_refs": ["evidence-1"]})
        recorder.record("validation.completed", REVIEW_AGENT, {"validation_id": "v-1", "name": "citation_check", "status": "passed", "target_refs": ["claim-1"]})
        recorder.record("approval.recorded", HUMAN, {"approval_id": "a-1", "role": "human_reviewer", "status": "approved", "target_refs": ["claim-1"]})
        recorder.record("run.completed", SYSTEM, {"summary": "Completed"})
        bundle = recorder.finalize(self.root / "stale-report", default_policy(), private_key_path=key)
        report_path = bundle / "report.html"
        report_path.write_text(report_path.read_text(encoding="utf-8").replace("1</strong><span>Approval events", "9</strong><span>Approval events"), encoding="utf-8")
        statement, fingerprint = verify_envelope(json.loads((bundle / "attestation.dsse.json").read_text(encoding="utf-8")), bundle / "public-key.pem")
        for subject in statement["subject"]:
            if subject["name"] == "report.html":
                subject["digest"]["sha256"] = sha256_file(report_path)
        write_json(bundle / "attestation.dsse.json", sign_statement(statement, key, fingerprint))
        result = verify_bundle(bundle)
        self.assertFalse(result.valid)
        self.assertIn("REPORT_NOT_DERIVED_FROM_EVENTS", self.codes(result))

    def test_malformed_event_returns_finding_not_traceback(self):
        events_path = self.valid / "events.jsonl"
        events_path.write_bytes(canonical_json_bytes([]) + b"\n")
        result = verify_bundle(self.valid)
        self.assertFalse(result.valid)
        self.assertIn("INVALID_EVENT", self.codes(result))

    def test_unhashable_evidence_reference_returns_finding(self):
        events_path = self.valid / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        claim = next(event for event in events if event.get("type") == "claim.asserted")
        claim["data"]["evidence_refs"] = [[]]
        events_path.write_bytes(b"".join(canonical_json_bytes(event) + b"\n" for event in events))
        result = verify_bundle(self.valid)
        self.assertFalse(result.valid)
        self.assertIn("BROKEN_EVIDENCE_LINK", self.codes(result))

    def test_non_dict_actor_returns_finding(self):
        events_path = self.valid / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        events[0]["actor"] = []
        events_path.write_bytes(b"".join(canonical_json_bytes(event) + b"\n" for event in events))
        result = verify_bundle(self.valid)
        self.assertFalse(result.valid)
        self.assertIn("INVALID_ACTOR", self.codes(result))

    def test_signed_non_object_statement_returns_finding(self):
        private_key = self.root / "array-private.pem"
        public_key = self.valid / "public-key.pem"
        fingerprint = generate_keypair(private_key, public_key)
        write_json(self.valid / "attestation.dsse.json", sign_statement([], private_key, fingerprint))
        result = verify_bundle(self.valid)
        self.assertFalse(result.valid)
        self.assertIn("INVALID_ATTESTATION_STATEMENT", self.codes(result))

    def test_unsigned_extra_file_is_rejected(self):
        (self.valid / "review-me-instead.html").write_text("Unsigned alternative report", encoding="utf-8")
        result = verify_bundle(self.valid)
        self.assertFalse(result.valid)
        self.assertIn("UNREGISTERED_BUNDLE_FILE", self.codes(result))


if __name__ == "__main__":
    unittest.main()
