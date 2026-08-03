import tempfile
from pathlib import Path

from .bundle import Recorder


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
        recorder.record("run.started", SYSTEM, {"summary": "Two-agent evidence review started"})
        recorder.add_artifact("evidence-test-note", source, RESEARCH_AGENT, "text/plain")
        recorder.record(
            "claim.asserted",
            RESEARCH_AGENT,
            {
                "claim_id": "claim-checks-passed",
                "text": "All four required checks passed on 2026-07-30.",
                "material": True,
                "evidence_refs": ["evidence-test-note"],
            },
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
        )
        recorder.record("run.completed", SYSTEM, {"summary": "Reviewed output released"})
        return recorder.finalize(output_dir, default_policy())


