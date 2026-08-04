import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm

from . import __version__
from .bundle import EVENT_TYPES, PREDICATE_TYPE, SPEC_VERSION, STATEMENT_TYPE, load_events, utc_now
from .canonical import sha256_file
from .crypto import verify_envelope
from .editorial import (
    EDITORIAL_CHECK_SET_VERSION,
    EditorialCheck,
    evaluate_editorial_profile,
    unavailable_editorial_evaluation,
)
from .report import render_report


CORE_SUBJECTS = {"bundle.json", "events.jsonl", "policy.json", "report.html"}
INTEGRITY_FAILURE_CODES = {
    "MISSING_OR_UNSAFE_PUBLIC_KEY",
    "INVALID_ATTESTATION_SIGNATURE",
    "KEY_FINGERPRINT_MISMATCH",
    "INVALID_ATTESTATION_STATEMENT",
    "ATTESTATION_RUN_MISMATCH",
    "MISSING_ATTESTED_SUBJECTS",
    "INVALID_ATTESTED_SUBJECT",
    "DUPLICATE_ATTESTED_SUBJECT",
    "UNSAFE_SUBJECT_PATH",
    "MISSING_SUBJECT",
    "SUBJECT_DIGEST_MISMATCH",
    "UNATTESTED_FILE",
    "UNREGISTERED_BUNDLE_FILE",
    "REPORT_NOT_DERIVED_FROM_EVENTS",
    "UNSAFE_ARTIFACT_PATH",
    "MISSING_ARTIFACT",
    "ARTIFACT_DIGEST_MISMATCH",
}
LIMITATIONS = [
    "The producer may omit actions or evidence, and omitted material cannot be detected.",
    "Content hashes establish byte identity, not accuracy or authenticity.",
    "A recorded review does not prove that the review was meaningful or competent.",
    "Producer timestamps are not independently trusted timestamps.",
    "A valid signature establishes identity only when its fingerprint is checked independently.",
    "The verifier makes no regulatory or legal determination.",
]


@dataclass
class Finding:
    code: str
    severity: str
    message: str


@dataclass
class VerificationResult:
    bundle: str
    verified_at: str = field(default_factory=utc_now)
    verifier_version: str = __version__
    valid: bool = True
    integrity_valid: bool = False
    signer_fingerprint: str | None = None
    signer_pinned: bool = False
    policy_summary: dict | None = None
    findings: list[Finding] = field(default_factory=list)
    bundle_metadata: dict | None = None
    editorial_check_set_version: str | None = None
    editorial_profile_state: str = "absent"
    editorial_profile_reason: str | None = None
    editorial_record: dict | None = None
    editorial_checks: list[EditorialCheck] = field(default_factory=list)
    review_chain: list[dict] = field(default_factory=list)
    editorial_responsibility: dict | None = None

    def add(self, code: str, severity: str, message: str) -> None:
        self.findings.append(Finding(code, severity, message))
        if severity == "error":
            self.valid = False

    def to_dict(self) -> dict:
        editorial_counts = {
            status: sum(1 for item in self.editorial_checks if item.status == status)
            for status in ("satisfied", "not_satisfied", "unverifiable")
        }
        return {
            "bundle": Path(self.bundle).name,
            "verified_at": self.verified_at,
            "verifier_version": self.verifier_version,
            "valid": self.valid,
            "integrity_valid": self.integrity_valid,
            "signer_fingerprint": self.signer_fingerprint,
            "signer_pinned": self.signer_pinned,
            "policy_summary": self.policy_summary,
            "bundle_metadata": self.bundle_metadata,
            "findings": [asdict(item) for item in self.findings],
            "editorial_check_set_version": self.editorial_check_set_version,
            "editorial_profile_state": self.editorial_profile_state,
            "editorial_profile_reason": self.editorial_profile_reason,
            "editorial_record": self.editorial_record,
            "editorial_checks": [item.to_dict() for item in self.editorial_checks],
            "editorial_summary": {
                **editorial_counts,
                "has_not_satisfied": editorial_counts["not_satisfied"] > 0,
            },
            "review_chain": self.review_chain,
            "editorial_responsibility": self.editorial_responsibility,
            "assurance_boundary": "Internal consistency and declared-policy satisfaction only; not truth or complete disclosure.",
            "limitations": LIMITATIONS,
        }


def _safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return (
        not posix.is_absolute()
        and ".." not in posix.parts
        and not windows.drive
        and not windows.root
    )


def _inside_bundle(bundle_dir: Path, value: str) -> tuple[bool, Path]:
    candidate = bundle_dir / value
    resolved = candidate.resolve(strict=False)
    return resolved.is_relative_to(bundle_dir) and not candidate.is_symlink(), candidate


def _load_json(path: Path, label: str, result: VerificationResult) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        result.add(f"MISSING_{label.upper()}", "error", f"Required file is missing: {path.name}")
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        result.add(f"INVALID_{label.upper()}", "error", f"{path.name} is not valid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        result.add(f"INVALID_{label.upper()}", "error", f"{path.name} must contain a JSON object")
        return None
    return value


def _validate_descriptor(descriptor: dict, result: VerificationResult) -> bool:
    valid = True
    required = {"spec_version", "run_id", "producer", "created_at", "public_key_fingerprint"}
    missing = sorted(required - descriptor.keys())
    extra = sorted(descriptor.keys() - required)
    if missing:
        result.add("INVALID_BUNDLE_SCHEMA", "error", f"bundle.json is missing fields: {', '.join(missing)}")
        valid = False
    if extra:
        result.add("INVALID_BUNDLE_SCHEMA", "error", f"bundle.json has unsupported fields: {', '.join(extra)}")
        valid = False
    if descriptor.get("spec_version") != SPEC_VERSION:
        result.add("UNSUPPORTED_SPEC_VERSION", "error", f"Expected spec version {SPEC_VERSION}")
        valid = False
    if not isinstance(descriptor.get("run_id"), str) or not descriptor.get("run_id"):
        result.add("INVALID_BUNDLE_SCHEMA", "error", "run_id must be a non-empty string")
        valid = False
    if not isinstance(descriptor.get("created_at"), str) or not descriptor.get("created_at"):
        result.add("INVALID_BUNDLE_SCHEMA", "error", "created_at must be a non-empty string")
        valid = False
    producer = descriptor.get("producer")
    if not isinstance(producer, dict) or set(producer) != {"id", "name"} or not all(
        isinstance(producer.get(key), str) and producer.get(key) for key in ("id", "name")
    ):
        result.add("INVALID_BUNDLE_SCHEMA", "error", "producer must contain only non-empty id and name strings")
        valid = False
    fingerprint = descriptor.get("public_key_fingerprint", "")
    if not isinstance(fingerprint, str) or re.fullmatch(r"[a-f0-9]{64}", fingerprint) is None:
        result.add("INVALID_BUNDLE_SCHEMA", "error", "public_key_fingerprint must be a SHA-256 hex digest")
        valid = False
    return valid


def _validate_policy(policy: dict, result: VerificationResult) -> bool:
    valid = True
    required = {"policy_version", "policy_id", "material_claims_require_evidence", "required_validations", "required_approvals"}
    missing = sorted(required - policy.keys())
    extra = sorted(policy.keys() - required)
    if missing:
        result.add("INVALID_POLICY_SCHEMA", "error", f"policy.json is missing fields: {', '.join(missing)}")
        valid = False
    if extra:
        result.add("INVALID_POLICY_SCHEMA", "error", f"policy.json has unsupported fields: {', '.join(extra)}")
        valid = False
    if policy.get("policy_version") != SPEC_VERSION:
        result.add("INVALID_POLICY_SCHEMA", "error", f"Expected policy version {SPEC_VERSION}")
        valid = False
    if not isinstance(policy.get("policy_id"), str) or not policy.get("policy_id"):
        result.add("INVALID_POLICY_SCHEMA", "error", "policy_id must be a non-empty string")
        valid = False
    if not isinstance(policy.get("material_claims_require_evidence"), bool):
        result.add("INVALID_POLICY_SCHEMA", "error", "material_claims_require_evidence must be a boolean")
        valid = False

    validations = policy.get("required_validations")
    if not isinstance(validations, list):
        result.add("INVALID_POLICY_SCHEMA", "error", "required_validations must be an array")
        valid = False
    else:
        for index, item in enumerate(validations):
            if (
                not isinstance(item, dict)
                or set(item) != {"name", "status"}
                or not isinstance(item.get("name"), str)
                or not item.get("name")
                or item.get("status") not in {"passed", "completed"}
            ):
                result.add("INVALID_POLICY_SCHEMA", "error", f"required_validations[{index}] is invalid")
                valid = False

    approvals = policy.get("required_approvals")
    if not isinstance(approvals, list):
        result.add("INVALID_POLICY_SCHEMA", "error", "required_approvals must be an array")
        valid = False
    else:
        for index, item in enumerate(approvals):
            if (
                not isinstance(item, dict)
                or set(item) != {"role", "status"}
                or not isinstance(item.get("role"), str)
                or not item.get("role")
                or item.get("status") != "approved"
            ):
                result.add("INVALID_POLICY_SCHEMA", "error", f"required_approvals[{index}] is invalid")
                valid = False
    return valid


def _validate_event_shape(events: list[object], result: VerificationResult) -> None:
    seen_ids = set()
    required = {"event_id", "sequence", "type", "occurred_at", "actor", "data"}
    for expected_sequence, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            result.add("INVALID_EVENT", "error", f"Event {expected_sequence} is not an object")
            continue
        missing = sorted(required - event.keys())
        if missing:
            result.add("INVALID_EVENT", "error", f"Event {expected_sequence} is missing: {', '.join(missing)}")
        if event.get("sequence") != expected_sequence:
            result.add("INVALID_EVENT_SEQUENCE", "error", f"Expected sequence {expected_sequence}, found {event.get('sequence')}")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            result.add("INVALID_EVENT", "error", f"Event {expected_sequence} has no event_id")
        elif event_id in seen_ids:
            result.add("DUPLICATE_EVENT_ID", "error", f"Duplicate event ID: {event_id}")
        seen_ids.add(event_id)
        if event.get("type") not in EVENT_TYPES:
            result.add("UNKNOWN_EVENT_TYPE", "error", f"Unsupported event type: {event.get('type')}")
        actor = event.get("actor")
        if not isinstance(actor, dict) or not actor.get("actor_id") or actor.get("type") not in {"agent", "human", "system"}:
            result.add("INVALID_ACTOR", "error", f"Event {event_id or expected_sequence} has an invalid actor")
        if not isinstance(event.get("data"), dict):
            result.add("INVALID_EVENT_DATA", "error", f"Event {event_id or expected_sequence} data must be an object")


def _check_event_times(events: list[object], result: VerificationResult) -> None:
    values = [event.get("occurred_at") for event in events if isinstance(event, dict)]
    if len(values) > 1 and len(set(values)) == 1:
        result.add(
            "UNCORROBORATED_EVENT_TIMESTAMPS",
            "warning",
            "All events share a single timestamp; sequence is not independently corroborated.",
        )
    parsed = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, str):
            result.add("INVALID_EVENT_TIMESTAMP", "error", f"Event {index} timestamp is not a string")
            return
        try:
            parsed.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            result.add("INVALID_EVENT_TIMESTAMP", "error", f"Event {index} timestamp is not valid ISO 8601")
            return
    if any(later < earlier for earlier, later in zip(parsed, parsed[1:])):
        result.add(
            "NON_MONOTONIC_EVENT_TIMESTAMPS",
            "warning",
            "Event timestamps move backwards relative to the recorded sequence.",
        )


def _artifact_paths(events: list[object]) -> set[str]:
    paths = set()
    for event in events:
        if not isinstance(event, dict) or event.get("type") != "evidence.registered":
            continue
        data = event.get("data")
        if isinstance(data, dict) and _safe_relative_path(data.get("artifact_path")):
            paths.add(data["artifact_path"])
    return paths


def _validate_semantics(bundle_dir: Path, events: list[object], policy: dict, result: VerificationResult) -> None:
    evidence = {}
    claims = []
    validations = []
    approvals = []

    for event in events:
        if not isinstance(event, dict):
            continue
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        if event.get("type") == "evidence.registered":
            evidence_id = data.get("evidence_id")
            artifact_path = data.get("artifact_path")
            digest = data.get("sha256")
            if not all(isinstance(value, str) and value for value in (evidence_id, artifact_path, digest)):
                result.add("INVALID_EVIDENCE_EVENT", "error", f"Evidence event {event.get('event_id')} is incomplete")
                continue
            if not _safe_relative_path(artifact_path):
                result.add("UNSAFE_ARTIFACT_PATH", "error", f"Unsafe artifact path: {artifact_path}")
                continue
            safe, artifact = _inside_bundle(bundle_dir, artifact_path)
            if not safe:
                result.add("UNSAFE_ARTIFACT_PATH", "error", f"Artifact escapes the bundle or is a symlink: {artifact_path}")
                continue
            if evidence_id in evidence:
                result.add("DUPLICATE_EVIDENCE_ID", "error", f"Duplicate evidence ID: {evidence_id}")
            evidence[evidence_id] = data
            if not artifact.is_file():
                result.add("MISSING_ARTIFACT", "error", f"Registered artifact is missing: {artifact_path}")
            elif sha256_file(artifact) != digest:
                result.add("ARTIFACT_DIGEST_MISMATCH", "error", f"Registered artifact changed: {artifact_path}")
        elif event.get("type") == "claim.asserted":
            if not isinstance(data.get("claim_id"), str) or not data.get("claim_id") or not isinstance(data.get("material"), bool):
                result.add("INVALID_CLAIM_EVENT", "error", f"Claim event {event.get('event_id')} is incomplete")
            claims.append(data)
        elif event.get("type") == "validation.completed":
            validations.append(data)
        elif event.get("type") == "approval.recorded":
            approvals.append(data)

    material_claim_ids = {claim.get("claim_id") for claim in claims if claim.get("material") is True and claim.get("claim_id")}
    all_claim_ids = {claim.get("claim_id") for claim in claims if claim.get("claim_id")}
    if policy["material_claims_require_evidence"]:
        for claim in claims:
            if claim.get("material") is not True:
                continue
            refs = claim.get("evidence_refs")
            if not isinstance(refs, list) or not refs:
                result.add("MISSING_EVIDENCE_LINK", "error", f"Material claim {claim.get('claim_id')} has no evidence reference")
                continue
            for evidence_id in refs:
                if not isinstance(evidence_id, str) or evidence_id not in evidence:
                    result.add("BROKEN_EVIDENCE_LINK", "error", f"Claim {claim.get('claim_id')} references unknown evidence {evidence_id}")

    for item in validations + approvals:
        refs = item.get("target_refs")
        if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in all_claim_ids for ref in refs):
            result.add("BROKEN_TARGET_REFERENCE", "error", "Validation or approval contains an absent or invalid claim target")

    def targets(item: dict) -> set[str]:
        refs = item.get("target_refs")
        if not isinstance(refs, list):
            return set()
        return {ref for ref in refs if isinstance(ref, str)}

    for required in policy["required_validations"]:
        matched = [item for item in validations if item.get("name") == required["name"] and item.get("status") == required["status"]]
        if not matched:
            result.add("MISSING_REQUIRED_VALIDATION", "error", f"Required validation is missing or unsatisfied: {required['name']}")
        elif material_claim_ids and not any(material_claim_ids.issubset(targets(item)) for item in matched):
            result.add("VALIDATION_COVERAGE_INCOMPLETE", "error", f"Validation {required['name']} does not cover every material claim")

    for required in policy["required_approvals"]:
        matched = [item for item in approvals if item.get("role") == required["role"] and item.get("status") == required["status"]]
        if not matched:
            result.add("MISSING_REQUIRED_APPROVAL", "error", f"Required approval is missing or unsatisfied for role: {required['role']}")
        elif material_claim_ids and not any(material_claim_ids.issubset(targets(item)) for item in matched):
            result.add("APPROVAL_COVERAGE_INCOMPLETE", "error", f"Approval role {required['role']} does not cover every material claim")


def _set_editorial_unavailable(result: VerificationResult, reason: str) -> None:
    result.editorial_profile_state = "unavailable"
    result.editorial_profile_reason = reason
    evaluation = unavailable_editorial_evaluation(reason, result.integrity_valid)
    result.editorial_check_set_version = EDITORIAL_CHECK_SET_VERSION
    result.editorial_checks = evaluation.checks


def verify_bundle(bundle_dir: Path, expected_key: str | None = None) -> VerificationResult:
    bundle_dir = bundle_dir.resolve()
    result = VerificationResult(bundle=str(bundle_dir))
    editorial_path = bundle_dir / "editorial-record.json"
    if editorial_path.exists() or editorial_path.is_symlink():
        _set_editorial_unavailable(
            result,
            "Bundle verification did not reach a digest-verified editorial profile, so its content was not evaluated.",
        )
    descriptor = _load_json(bundle_dir / "bundle.json", "bundle", result)
    policy = _load_json(bundle_dir / "policy.json", "policy", result)
    envelope = _load_json(bundle_dir / "attestation.dsse.json", "attestation", result)
    public_path = bundle_dir / "public-key.pem"
    if descriptor is None or policy is None or envelope is None or not public_path.is_file() or public_path.is_symlink():
        if not public_path.is_file() or public_path.is_symlink():
            result.add("MISSING_OR_UNSAFE_PUBLIC_KEY", "error", "public-key.pem is missing or is a symlink")
        return result

    descriptor_valid = _validate_descriptor(descriptor, result)
    policy_valid = _validate_policy(policy, result)
    result.bundle_metadata = {
        "run_id": descriptor.get("run_id"),
        "spec_version": descriptor.get("spec_version"),
        "producer": descriptor.get("producer"),
        "created_at": descriptor.get("created_at"),
    }
    try:
        statement, fingerprint = verify_envelope(envelope, public_path)
        result.signer_fingerprint = fingerprint
    except (ValueError, KeyError, TypeError, InvalidSignature, UnsupportedAlgorithm) as exc:
        result.add("INVALID_ATTESTATION_SIGNATURE", "error", f"Attestation signature verification failed: {exc}")
        return result

    if descriptor.get("public_key_fingerprint") != result.signer_fingerprint:
        result.add("KEY_FINGERPRINT_MISMATCH", "error", "bundle.json fingerprint does not match the included signing key")
    if expected_key is None:
        result.add("UNPINNED_SIGNER", "warning", "The signature is valid, but the included signing key was not checked against an independently obtained fingerprint")
    elif not re.fullmatch(r"[a-f0-9]{64}", expected_key):
        result.add("MALFORMED_EXPECTED_KEY", "error", "Expected signer fingerprint must contain exactly 64 lowercase hexadecimal characters")
    elif expected_key != result.signer_fingerprint:
        result.add("UNTRUSTED_SIGNER", "error", "Signer fingerprint does not match the independently expected key")
    else:
        result.signer_pinned = True

    if not isinstance(statement, dict):
        result.add("INVALID_ATTESTATION_STATEMENT", "error", "Attestation payload must be a JSON object")
        return result
    if statement.get("_type") != STATEMENT_TYPE or statement.get("predicateType") != PREDICATE_TYPE:
        result.add("INVALID_ATTESTATION_STATEMENT", "error", "Attestation statement type is unsupported")
    predicate = statement.get("predicate", {})
    if not isinstance(predicate, dict) or predicate.get("run_id") != descriptor.get("run_id"):
        result.add("ATTESTATION_RUN_MISMATCH", "error", "Attestation run ID does not match bundle.json")

    try:
        events = load_events(bundle_dir / "events.jsonl")
    except (FileNotFoundError, ValueError, UnicodeDecodeError) as exc:
        result.add("INVALID_EVENTS_FILE", "error", str(exc))
        events = []
    _validate_event_shape(events, result)
    _check_event_times(events, result)

    subjects = statement.get("subject")
    if not isinstance(subjects, list) or not subjects:
        result.add("MISSING_ATTESTED_SUBJECTS", "error", "Attestation has no signed subjects")
        subjects = []
    subject_names = set()
    verified_subject_names = set()
    for subject in subjects:
        if not isinstance(subject, dict):
            result.add("INVALID_ATTESTED_SUBJECT", "error", "Attested subject must be an object")
            continue
        name = subject.get("name", "")
        expected_digest = subject.get("digest", {}).get("sha256") if isinstance(subject.get("digest"), dict) else None
        if name in subject_names:
            result.add("DUPLICATE_ATTESTED_SUBJECT", "error", f"Duplicate attested subject: {name}")
        subject_names.add(name)
        if not _safe_relative_path(name):
            result.add("UNSAFE_SUBJECT_PATH", "error", f"Unsafe attested subject path: {name}")
            continue
        safe, subject_path = _inside_bundle(bundle_dir, name)
        if not safe:
            result.add("UNSAFE_SUBJECT_PATH", "error", f"Subject escapes the bundle or is a symlink: {name}")
        elif not subject_path.is_file():
            result.add("MISSING_SUBJECT", "error", f"Signed subject is missing: {name}")
        elif not isinstance(expected_digest, str) or sha256_file(subject_path) != expected_digest:
            result.add("SUBJECT_DIGEST_MISMATCH", "error", f"Signed subject changed after signing: {name}")
        else:
            verified_subject_names.add(name)

    required_subjects = CORE_SUBJECTS | _artifact_paths(events)
    for name in sorted(required_subjects - subject_names):
        result.add("UNATTESTED_FILE", "error", f"Required bundle file is not covered by the signature: {name}")

    allowed_files = subject_names | {"attestation.dsse.json", "public-key.pem"}
    for candidate in bundle_dir.rglob("*"):
        if not candidate.is_file() and not candidate.is_symlink():
            continue
        relative_name = candidate.relative_to(bundle_dir).as_posix()
        if relative_name not in allowed_files:
            result.add("UNREGISTERED_BUNDLE_FILE", "error", f"Bundle contains an unsigned, unregistered file: {relative_name}")

    material_claim_count = sum(
        1
        for event in events
        if isinstance(event, dict)
        and event.get("type") == "claim.asserted"
        and isinstance(event.get("data"), dict)
        and event["data"].get("material") is True
    )
    if policy_valid:
        result.policy_summary = {
            "policy_id": policy["policy_id"],
            "material_claims_require_evidence": policy["material_claims_require_evidence"],
            "material_claim_count": material_claim_count,
            "required_validation_count": len(policy["required_validations"]),
            "required_approval_count": len(policy["required_approvals"]),
        }
        if not policy["material_claims_require_evidence"] and not policy["required_validations"] and not policy["required_approvals"]:
            result.add("VACUOUS_POLICY", "warning", "The declared policy requires no evidence links, validations, or approvals")
        _validate_semantics(bundle_dir, events, policy, result)

    if descriptor_valid and policy_valid:
        try:
            expected_report = render_report(descriptor, events, policy).encode("utf-8")
            report_path = bundle_dir / "report.html"
            if report_path.is_symlink() or report_path.read_bytes() != expected_report:
                result.add("REPORT_NOT_DERIVED_FROM_EVENTS", "error", "report.html does not match the signed descriptor, events, and policy")
        except (KeyError, TypeError, AttributeError, OSError) as exc:
            result.add("REPORT_NOT_DERIVED_FROM_EVENTS", "error", f"report.html could not be reconstructed: {exc}")

    result.integrity_valid = not any(
        finding.severity == "error" and finding.code in INTEGRITY_FAILURE_CODES
        for finding in result.findings
    )

    if editorial_path.is_file() and "editorial-record.json" not in verified_subject_names:
        _set_editorial_unavailable(
            result,
            "The editorial profile was not covered by a matching signed digest, so its content was not evaluated.",
        )
    elif editorial_path.is_file():
        try:
            editorial_profile = json.loads(editorial_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            result.add("INVALID_EDITORIAL_PROFILE", "error", f"Editorial profile is unreadable: {exc}")
            _set_editorial_unavailable(
                result,
                "The signed editorial profile could not be parsed, so its content was not evaluated.",
            )
        else:
            if not isinstance(editorial_profile, dict):
                result.add("INVALID_EDITORIAL_PROFILE", "error", "Editorial profile must be a JSON object")
                _set_editorial_unavailable(
                    result,
                    "The signed editorial profile is not a JSON object, so its content was not evaluated.",
                )
            else:
                evaluation = evaluate_editorial_profile(bundle_dir, editorial_profile, result.integrity_valid)
                if evaluation.checks:
                    result.editorial_profile_state = "evaluated"
                    result.editorial_profile_reason = None
                    result.editorial_record = evaluation.record or None
                    result.editorial_checks = evaluation.checks
                    result.review_chain = evaluation.review_chain
                    result.editorial_responsibility = evaluation.responsibility
                else:
                    _set_editorial_unavailable(
                        result,
                        "The signed editorial profile name or version is unsupported, so its content was not evaluated.",
                    )
                result.editorial_check_set_version = EDITORIAL_CHECK_SET_VERSION
                for code, message in evaluation.findings:
                    severity = "error" if code == "INVALID_EDITORIAL_PROFILE" else "warning"
                    result.add(code, severity, message)

    if any(item.status == "not_satisfied" for item in result.editorial_checks):
        result.add(
            "EDITORIAL_CHECKS_NOT_SATISFIED",
            "error",
            "One or more editorial record checks are not satisfied; inspect the individual check results.",
        )

    result.add(
        "SELF_ATTESTATION_LIMIT",
        "warning",
        "The producer controls capture and policy. Verification does not prove truth, complete disclosure, authenticated approval, or trusted time.",
    )
    if result.valid:
        result.add("VERIFIED", "info", "Record is internally consistent and satisfies the explicitly reported reconstruction policy")
    return result
