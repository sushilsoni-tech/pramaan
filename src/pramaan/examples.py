import tempfile
from pathlib import Path

from .bundle import Recorder
from .canonical import sha256_file


SYSTEM = {"actor_id": "pramaan-runtime", "type": "system", "name": "Pramaan Runtime"}
RESEARCH_AGENT = {"actor_id": "research-agent", "type": "agent", "name": "Research Agent"}
REVIEW_AGENT = {"actor_id": "review-agent", "type": "agent", "name": "Review Agent"}
HUMAN = {"actor_id": "reviewer-01", "type": "human", "name": "Human Reviewer"}


def default_policy(policy_id: str = "two-party-review-v0.1") -> dict:
    return {
        "policy_version": "0.1",
        "policy_id": policy_id,
        "material_claims_require_evidence": True,
        "required_validations": [{"name": "citation_check", "status": "passed"}],
        "required_approvals": [{"role": "human_reviewer", "status": "approved"}],
    }


def build_two_agent_example(output_dir: Path) -> Path:
    with tempfile.TemporaryDirectory(prefix="pramaan-example-") as temp:
        source = Path(temp) / "source-note.txt"
        source.write_text(
            "The independent test completed on 2026-07-30. All four required checks passed.\n",
            encoding="utf-8",
        )
        recorder = Recorder("two-agent-demo-001", "small-ai-vendor", "Small AI Vendor")
        times = [
            "2026-07-30T09:00:00Z",
            "2026-07-30T09:02:00Z",
            "2026-07-30T09:05:00Z",
            "2026-07-30T09:08:00Z",
            "2026-07-30T09:12:00Z",
            "2026-07-30T09:15:00Z",
        ]
        recorder.record("run.started", SYSTEM, {"summary": "Two-agent evidence review started"}, occurred_at=times[0])
        recorder.add_artifact("evidence-test-note", source, RESEARCH_AGENT, "text/plain")
        recorder.events[-1]["occurred_at"] = times[1]
        recorder.record(
            "claim.asserted",
            RESEARCH_AGENT,
            {
                "claim_id": "claim-checks-passed",
                "text": "All four required checks passed on 2026-07-30.",
                "material": True,
                "evidence_refs": ["evidence-test-note"],
            },
            occurred_at=times[2],
        )
        recorder.record(
            "validation.completed",
            REVIEW_AGENT,
            {
                "validation_id": "validation-citation-001",
                "name": "citation_check",
                "status": "passed",
                "target_refs": ["claim-checks-passed"],
            },
            occurred_at=times[3],
        )
        recorder.record(
            "approval.recorded",
            HUMAN,
            {
                "approval_id": "approval-001",
                "role": "human_reviewer",
                "status": "approved",
                "target_refs": ["claim-checks-passed"],
            },
            occurred_at=times[4],
        )
        recorder.record("run.completed", SYSTEM, {"summary": "Reviewed output released"}, occurred_at=times[5])
        return recorder.finalize(output_dir, default_policy())


def editorial_policy() -> dict:
    return {
        "policy_version": "0.1",
        "policy_id": "editorial-record-demo-v0.1",
        "material_claims_require_evidence": True,
        "required_validations": [{"name": "citation_check", "status": "passed"}],
        "required_approvals": [],
    }


def build_editorial_example(
    output_dir: Path,
    case: str = "valid",
    private_key_path: Path | None = None,
) -> Path:
    if case not in {"valid", "missing-reviewer", "post-publication", "policy-failure"}:
        raise ValueError(f"unsupported editorial example case: {case}")
    with tempfile.TemporaryDirectory(prefix="pramaan-editorial-example-") as temp:
        published = Path(temp) / "published-item.txt"
        published.write_text(
            "Council releases its independently reviewed community resilience update.\n",
            encoding="utf-8",
        )
        recorder = Recorder("editorial-demo-001", "small-publisher", "Harbour Community Brief")
        recorder.record("run.started", SYSTEM, {"summary": "Editorial workflow started"}, occurred_at="2026-08-02T08:00:00Z")
        recorder.add_artifact("published-item", published, RESEARCH_AGENT, "text/plain")
        recorder.events[-1]["occurred_at"] = "2026-08-02T08:02:00Z"
        recorder.record(
            "claim.asserted",
            RESEARCH_AGENT,
            {
                "claim_id": "published-statement",
                "text": "Community resilience update released.",
                "material": True,
                "evidence_refs": ["published-item"],
            },
            occurred_at="2026-08-02T08:05:00Z",
        )
        recorder.record(
            "validation.completed",
            REVIEW_AGENT,
            {
                "validation_id": "citation-review-001",
                "name": "citation_check",
                "status": "passed",
                "target_refs": ["published-statement"],
            },
            occurred_at="2026-08-02T08:25:00Z",
        )
        recorder.record("run.completed", SYSTEM, {"summary": "Item published"}, occurred_at="2026-08-02T09:00:00Z")

        review_time = "2026-08-02T09:15:00Z" if case == "post-publication" else "2026-08-02T08:30:00Z"
        reviews = [] if case == "missing-reviewer" else [
            {
                "reviewer_id": "editor-01",
                "reviewer_display_name": "Maya Chen",
                "review_type": "substantive",
                "scope_reviewed": "whole item",
                "changes_made": True,
                "post_review_content_hash": sha256_file(published),
                "occurred_at": review_time,
                "competence_basis": "Managing editor with responsibility for public-interest reporting",
                "identity_binding": "self_asserted",
            }
        ]
        responsibility = None if case == "missing-reviewer" else {
            "person_or_entity": "Maya Chen, Managing Editor",
            "identifier": "editor-01",
            "declared_at": "2026-08-02T08:45:00Z",
        }
        recorder.add_profile(
            "editorial-record.json",
            {
                "profile": "editorial-responsibility",
                "profile_version": "0.1",
                "check_set_version": "0.1",
                "item": {
                    "item_id": "community-resilience-update-2026-08",
                    "item_title": "Community Resilience Update",
                    "publication_context": "Harbour Community Brief / Public updates",
                    "published_artifact": "artifacts/published-item.txt",
                    "content_hash": sha256_file(published),
                    "published_at": "2026-08-02T09:00:00Z",
                },
                "generation_events": [
                    {
                        "system_id": "research-agent",
                        "system_name": "Research Agent",
                        "model": "producer-supplied",
                        "model_version": "unknown",
                        "occurred_at": "2026-08-02T08:05:00Z",
                    }
                ],
                "review_events": reviews,
                "editorial_responsibility": responsibility,
                "disclosure_state": "unknown",
            },
        )
        policy = editorial_policy()
        if case == "policy-failure":
            policy["required_approvals"] = [{"role": "publisher", "status": "approved"}]
        return recorder.finalize(output_dir, policy, private_key_path=private_key_path)
