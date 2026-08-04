from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

from .canonical import sha256_file


EDITORIAL_PROFILE = "editorial-responsibility"
EDITORIAL_PROFILE_VERSION = "0.1"
EDITORIAL_CHECK_SET_VERSION = "0.1"
EDITORIAL_CHECK_IDS = (
    "review.substantive_recorded",
    "responsibility.named",
    "review.timing",
    "content.hash_matches",
    "review.change_evidence",
    "reviewer.identity_bound",
    "record.integrity",
)
EDITORIAL_STATUSES = {"satisfied", "not_satisfied", "unverifiable"}
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@dataclass
class EditorialCheck:
    check_id: str
    label: str
    status: str
    ran: bool
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EditorialEvaluation:
    record: dict = field(default_factory=dict)
    checks: list[EditorialCheck] = field(default_factory=list)
    review_chain: list[dict] = field(default_factory=list)
    responsibility: dict | None = None
    findings: list[tuple[str, str]] = field(default_factory=list)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _safe_artifact(bundle_dir: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or ".." in posix.parts or windows.drive or windows.root:
        return None
    candidate = bundle_dir / value
    if candidate.is_symlink() or not candidate.resolve(strict=False).is_relative_to(bundle_dir):
        return None
    return candidate


def _check(check_id: str, label: str, status: str, ran: bool, reason: str) -> EditorialCheck:
    if status not in EDITORIAL_STATUSES:
        raise ValueError(f"unsupported editorial status: {status}")
    return EditorialCheck(check_id, label, status, ran, reason)


def unavailable_editorial_evaluation(reason: str, core_integrity_valid: bool) -> EditorialEvaluation:
    evaluation = EditorialEvaluation()
    for check_id, label in (
        (EDITORIAL_CHECK_IDS[0], "Substantive review recorded"),
        (EDITORIAL_CHECK_IDS[1], "Editorial responsibility named"),
        (EDITORIAL_CHECK_IDS[2], "Review occurred before publication"),
        (EDITORIAL_CHECK_IDS[3], "Published content hash matches"),
        (EDITORIAL_CHECK_IDS[4], "Change evidence digest recorded"),
        (EDITORIAL_CHECK_IDS[5], "Reviewer identity is independently bound"),
    ):
        evaluation.checks.append(_check(check_id, label, "unverifiable", False, reason))
    evaluation.checks.append(_check(
        EDITORIAL_CHECK_IDS[6],
        "Signed record integrity",
        "satisfied" if core_integrity_valid else "not_satisfied",
        True,
        "All signed subject digests match."
        if core_integrity_valid
        else "One or more signed files failed integrity verification.",
    ))
    return evaluation


def evaluate_editorial_profile(bundle_dir: Path, profile: dict, core_integrity_valid: bool) -> EditorialEvaluation:
    evaluation = EditorialEvaluation()
    if profile.get("profile") != EDITORIAL_PROFILE or profile.get("profile_version") != EDITORIAL_PROFILE_VERSION:
        evaluation.findings.append(("INVALID_EDITORIAL_PROFILE", "Editorial profile name or version is unsupported"))
        return evaluation
    if profile.get("check_set_version") != EDITORIAL_CHECK_SET_VERSION:
        evaluation.findings.append(("INVALID_EDITORIAL_PROFILE", "Editorial check-set version is unsupported"))
        return evaluation

    item = profile.get("item") if isinstance(profile.get("item"), dict) else {}
    generations = [item for item in profile.get("generation_events", []) if isinstance(item, dict)] if isinstance(profile.get("generation_events"), list) else []
    reviews = [item for item in profile.get("review_events", []) if isinstance(item, dict)] if isinstance(profile.get("review_events"), list) else []
    responsibility = profile.get("editorial_responsibility")
    if not isinstance(responsibility, dict):
        responsibility = {}

    evaluation.record = {
        "profile": EDITORIAL_PROFILE,
        "profile_version": EDITORIAL_PROFILE_VERSION,
        "check_set_version": EDITORIAL_CHECK_SET_VERSION,
        "item_id": item.get("item_id"),
        "item_title": item.get("item_title"),
        "publication_context": item.get("publication_context"),
        "content_hash": item.get("content_hash"),
        "published_artifact": item.get("published_artifact"),
        "published_at": item.get("published_at"),
        "disclosure_state": profile.get("disclosure_state")
        if profile.get("disclosure_state") in {"labelled", "not_labelled", "unknown"}
        else "unknown",
    }
    if profile.get("disclosure_state") not in {"labelled", "not_labelled", "unknown"}:
        evaluation.findings.append(("INVALID_EDITORIAL_PROFILE_FIELD", "Disclosure state is unsupported and was treated as unknown"))
    evaluation.responsibility = responsibility or None

    substantive_fields = ("reviewer_id", "reviewer_display_name", "scope_reviewed", "occurred_at", "competence_basis")
    substantive = [
        review
        for review in reviews
        if review.get("review_type") == "substantive"
        and all(isinstance(review.get(key), str) and review.get(key) for key in substantive_fields)
    ]
    if substantive:
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[0],
            "Substantive review recorded",
            "satisfied",
            True,
            "The producer declared at least one review as substantive; Pramaan cannot assess its quality or substance in fact.",
        ))
    else:
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[0],
            "Substantive review recorded",
            "not_satisfied",
            True,
            "No complete review event declared as substantive is present in the signed record.",
        ))

    if all(isinstance(responsibility.get(key), str) and responsibility.get(key) for key in ("person_or_entity", "identifier")):
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[1],
            "Editorial responsibility named",
            "satisfied",
            True,
            "The signed record names a responsible person or entity and an identifier; both remain producer-supplied assertions.",
        ))
    else:
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[1],
            "Editorial responsibility named",
            "not_satisfied",
            True,
            "The signed record does not contain both a responsible person or entity and an identifier.",
        ))

    generation_times = [_parse_time(item.get("occurred_at")) for item in generations if isinstance(item, dict)]
    review_times = [_parse_time(item.get("occurred_at")) for item in reviews if isinstance(item, dict)]
    publication_time = _parse_time(item.get("published_at"))
    if not generations or not reviews or publication_time is None or any(value is None for value in generation_times + review_times):
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[2],
            "Review occurred before publication",
            "unverifiable",
            False,
            "Generation, review, and publication timestamps were not all available as parseable values.",
        ))
    else:
        latest_generation = max(generation_times)
        if any(value > publication_time for value in review_times):
            evaluation.checks.append(_check(
                EDITORIAL_CHECK_IDS[2],
                "Review occurred before publication",
                "not_satisfied",
                True,
                "At least one recorded review occurred after publication.",
            ))
            evaluation.findings.append(("EDITORIAL_REVIEW_AFTER_PUBLICATION", "A recorded review postdates publication"))
        elif any(value < latest_generation for value in review_times):
            evaluation.checks.append(_check(
                EDITORIAL_CHECK_IDS[2],
                "Review occurred before publication",
                "not_satisfied",
                True,
                "At least one recorded review predates the latest recorded generation event.",
            ))
        else:
            evaluation.checks.append(_check(
                EDITORIAL_CHECK_IDS[2],
                "Review occurred before publication",
                "satisfied",
                True,
                "Recorded review times fall after generation and no later than publication; producer timestamps are not independently trusted.",
            ))

    artifact_name = item.get("published_artifact")
    expected_hash = item.get("content_hash")
    artifact_path = _safe_artifact(bundle_dir, artifact_name)
    if not isinstance(expected_hash, str) or artifact_path is None or not artifact_path.is_file():
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[3],
            "Published content hash matches",
            "unverifiable",
            False,
            "A resolvable published artifact and declared content hash were not both supplied.",
        ))
    elif sha256_file(artifact_path) == expected_hash:
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[3],
            "Published content hash matches",
            "satisfied",
            True,
            "The supplied published artifact matches the content hash in the signed editorial record.",
        ))
    else:
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[3],
            "Published content hash matches",
            "not_satisfied",
            True,
            "The supplied published artifact does not match the declared content hash.",
        ))

    changed_reviews = [review for review in reviews if review.get("changes_made") is True]
    if not reviews:
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[4],
            "Change evidence digest recorded",
            "unverifiable",
            False,
            "No review event is available to establish whether changes were made.",
        ))
    elif any(not isinstance(review.get("changes_made"), bool) for review in reviews):
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[4],
            "Change evidence digest recorded",
            "unverifiable",
            False,
            "At least one review does not state whether changes were made.",
        ))
    elif changed_reviews and not all(
        any(
            isinstance(value, str) and SHA256_PATTERN.fullmatch(value)
            for value in (review.get("diff_hash"), review.get("post_review_content_hash"))
        )
        for review in changed_reviews
    ):
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[4],
            "Change evidence digest recorded",
            "not_satisfied",
            True,
            "A review declares changes but supplies no valid SHA-256 diff or post-review content digest.",
        ))
    elif changed_reviews and any(_parse_time(review.get("occurred_at")) is None for review in changed_reviews):
        evaluation.checks.append(_check(
            EDITORIAL_CHECK_IDS[4],
            "Change evidence digest recorded",
            "unverifiable",
            False,
            "A changed review has no parseable timestamp, so the latest changed review cannot be identified.",
        ))
    else:
        latest_changed = max(changed_reviews, key=lambda review: _parse_time(review["occurred_at"])) if changed_reviews else None
        latest_post_hash = latest_changed.get("post_review_content_hash") if latest_changed else None
        if (
            isinstance(latest_post_hash, str)
            and SHA256_PATTERN.fullmatch(latest_post_hash)
            and isinstance(expected_hash, str)
            and latest_post_hash != expected_hash
        ):
            evaluation.checks.append(_check(
                EDITORIAL_CHECK_IDS[4],
                "Change evidence digest recorded",
                "not_satisfied",
                True,
                "The latest changed review's post-review content digest does not match the declared published content digest.",
            ))
        else:
            evaluation.checks.append(_check(
                EDITORIAL_CHECK_IDS[4],
                "Change evidence digest recorded",
                "satisfied",
                True,
                "Every changed review records a valid SHA-256 digest, and the latest post-review content digest matches the publication when supplied; a digest alone does not establish change quality.",
            ))

    evaluation.checks.append(_check(
        EDITORIAL_CHECK_IDS[5],
        "Reviewer identity is independently bound",
        "unverifiable",
        False,
        "Editorial profile 0.1 records reviewer identity as self-asserted and does not support reviewer-held signatures.",
    ))
    evaluation.checks.append(_check(
        EDITORIAL_CHECK_IDS[6],
        "Signed record integrity",
        "satisfied" if core_integrity_valid else "not_satisfied",
        True,
        "The editorial record is covered by the producer signature and all signed subject digests match."
        if core_integrity_valid
        else "The bundle has one or more integrity errors; see the core verifier findings.",
    ))

    for generation in generations:
        if not isinstance(generation, dict):
            continue
        evaluation.review_chain.append({
            "kind": "generation",
            "actor_id": generation.get("system_id"),
            "display_name": generation.get("system_name"),
            "action": "Generated or manipulated the item",
            "binding": "self-asserted",
            "occurred_at": generation.get("occurred_at"),
        })
    for review in reviews:
        if not isinstance(review, dict):
            continue
        evaluation.review_chain.append({
            "kind": "review",
            "actor_id": review.get("reviewer_id"),
            "display_name": review.get("reviewer_display_name"),
            "action": f"Declared {review.get('review_type', 'unspecified')} review of {review.get('scope_reviewed', 'unspecified scope')}",
            "binding": "self-asserted",
            "occurred_at": review.get("occurred_at"),
        })
    evaluation.review_chain.append({
        "kind": "publication",
        "actor_id": responsibility.get("identifier"),
        "display_name": responsibility.get("person_or_entity"),
        "action": "Published item",
        "binding": "self-asserted",
        "occurred_at": item.get("published_at"),
    })
    def chain_order(entry: dict) -> tuple[bool, float]:
        parsed = _parse_time(entry.get("occurred_at"))
        return parsed is None, parsed.timestamp() if parsed is not None else float("inf")

    evaluation.review_chain.sort(key=chain_order)
    return evaluation
