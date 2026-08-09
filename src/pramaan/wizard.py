import base64
import binascii
import json
import re
import secrets
import tempfile
import uuid
import webbrowser
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .bundle import Recorder
from .canonical import sha256_bytes, sha256_file
from .verify import verify_bundle
from .verification_report import write_verification_outputs
from .wizard_ui import render_wizard_html


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_REQUEST_BYTES = 15 * 1024 * 1024
REVIEW_SCOPES = {
    "facts_claims": "Facts and claims",
    "sources_citations": "Sources and citations",
    "quotes_attributions": "Quotes and attributions",
    "numbers_calculations": "Numbers and calculations",
    "legal_contractual": "Legal or contractual sensitivity",
    "tone_framing": "Tone and framing",
    "whole_item": "Whole item line by line",
}
SUBSTANTIVE_CONTENT_SCOPES = set(REVIEW_SCOPES) - {"tone_framing"}
DISCLOSURE_STATES = {
    "item": "labelled",
    "elsewhere": "labelled",
    "not_disclosed": "not_labelled",
    "not_published": "unknown",
}


class RecordCreationError(ValueError):
    pass


@dataclass
class CreatedRecord:
    record_id: str
    record_dir: Path
    bundle_dir: Path
    report_path: Path
    result_json_path: Path
    zip_path: Path
    title: str
    stored_file_name: str
    file_hash: str
    valid: bool
    integrity_valid: bool
    signer_fingerprint: str | None
    created_at: str
    editorial_counts: dict[str, int]


def _text(data: dict, key: str, *, required: bool = True, maximum: int = 300) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        value = ""
    value = value.strip()
    if required and not value:
        raise RecordCreationError(f"{key} is required")
    if len(value) > maximum:
        raise RecordCreationError(f"{key} must be {maximum} characters or fewer")
    return value


def _time(data: dict, key: str) -> tuple[str, datetime]:
    value = _text(data, key, maximum=64)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecordCreationError(f"{key} must be an ISO 8601 date and time") from exc
    if parsed.tzinfo is None:
        raise RecordCreationError(f"{key} must include a timezone offset")
    return value, parsed


def _slug(value: str, maximum: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug[:maximum].rstrip("-") or "record")


def _safe_filename(value: object) -> str:
    if not isinstance(value, str):
        raise RecordCreationError("file_name is required")
    supplied = Path(value.replace("\\", "/")).name
    suffix = Path(supplied).suffix[:16]
    stem = _slug(Path(supplied).stem, 72)
    suffix = re.sub(r"[^A-Za-z0-9.]", "", suffix)
    return f"{stem}{suffix.lower()}" if suffix else stem


def _policy() -> dict:
    return {
        "policy_version": "0.1",
        "policy_id": "editorial-wizard-v0.1",
        "material_claims_require_evidence": True,
        "required_validations": [],
        "required_approvals": [],
    }


def _decode_file(data: dict) -> tuple[str, bytes]:
    filename = _safe_filename(data.get("file_name"))
    encoded = data.get("file_base64")
    if not isinstance(encoded, str) or not encoded:
        raise RecordCreationError("publication file is required")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RecordCreationError("publication file is not valid base64 data") from exc
    if not content:
        raise RecordCreationError("publication file is empty")
    if len(content) > MAX_FILE_BYTES:
        raise RecordCreationError("publication file must be 10 MB or smaller")
    declared_hash = data.get("file_hash")
    actual_hash = sha256_bytes(content)
    if not isinstance(declared_hash, str) or declared_hash != actual_hash:
        raise RecordCreationError("publication file changed after selection; re-select it")
    return filename, content


def create_editorial_record(
    data: dict,
    output_root: Path,
    private_key_path: Path,
) -> CreatedRecord:
    if not isinstance(data, dict):
        raise RecordCreationError("request body must be a JSON object")
    filename, content = _decode_file(data)
    title = _text(data, "title", maximum=200)
    context = _text(data, "publication_context", maximum=200)
    ai_system = _text(data, "ai_system", maximum=120)
    ai_model = _text(data, "ai_model", required=False, maximum=120) or "not recorded"
    contribution = _text(data, "ai_contribution", maximum=120)
    generation_at, generation_time = _time(data, "generation_at")
    disclosure = _text(data, "disclosure_state", maximum=30)
    if disclosure not in DISCLOSURE_STATES:
        raise RecordCreationError("disclosure_state is unsupported")
    publication_at = None
    publication_time = None
    if disclosure != "not_published":
        publication_at, publication_time = _time(data, "publication_at")
        if publication_time > datetime.now(timezone.utc).astimezone(publication_time.tzinfo) + timedelta(minutes=1):
            raise RecordCreationError("publication time cannot be in the future")
        if publication_time < generation_time:
            raise RecordCreationError("publication time cannot be before AI generation finished")

    review_state = _text(data, "review_state", maximum=20)
    if review_state not in {"complete", "none", "partial"}:
        raise RecordCreationError("review_state must be complete, none, or partial")

    review_events = []
    partial_review_note = None
    if review_state == "complete":
        reviewer_name = _text(data, "reviewer_name", maximum=160)
        reviewer_role = _text(data, "reviewer_role", required=False, maximum=120)
        review_at, review_time = _time(data, "review_at")
        if review_time < generation_time:
            raise RecordCreationError("review time cannot be before AI generation finished")
        if publication_time is not None and publication_time < review_time:
            raise RecordCreationError("publication time cannot be before review finished")
        competence_basis = _text(data, "competence_basis", maximum=300)
        if len(competence_basis) < 10:
            raise RecordCreationError("competence_basis must be at least 10 characters")
        scopes = data.get("review_scopes")
        if not isinstance(scopes, list) or not scopes:
            raise RecordCreationError("at least one review scope is required")
        if any(scope not in REVIEW_SCOPES for scope in scopes):
            raise RecordCreationError("review_scopes contains an unsupported value")
        if not any(scope in SUBSTANTIVE_CONTENT_SCOPES for scope in scopes):
            raise RecordCreationError("substantive review requires at least one content review scope")
        changes_made = data.get("changes_made")
        if not isinstance(changes_made, bool):
            raise RecordCreationError("changes_made must be true or false")
        change_summary = _text(data, "change_summary", required=False, maximum=500)
        if changes_made and len(change_summary) < 10:
            raise RecordCreationError("change_summary must be at least 10 characters when changes were made")
        review_duration = data.get("review_duration_minutes")
        if not isinstance(review_duration, (int, float)) or isinstance(review_duration, bool):
            raise RecordCreationError("review_duration_minutes must be a number")
        if review_duration < 1 or review_duration > 10080:
            raise RecordCreationError("review_duration_minutes must be between 1 and 10080")
        elapsed_review_window = (review_time - generation_time).total_seconds() / 60
        # datetime-local captures minutes, not seconds. Allow one minute of
        # tolerance so an honest same-minute review is not a dead end.
        if review_duration > elapsed_review_window + 1:
            raise RecordCreationError("review duration cannot be longer than the time between AI generation and review")
        review_events.append(
            {
                "reviewer_id": _slug(reviewer_name),
                "reviewer_display_name": (
                    f"{reviewer_name}, {reviewer_role}" if reviewer_role else reviewer_name
                ),
                "review_type": "substantive",
                "scope_reviewed": "; ".join(REVIEW_SCOPES[scope] for scope in scopes),
                "changes_made": changes_made,
                "post_review_content_hash": sha256_bytes(content) if changes_made else None,
                "change_evidence_basis": "no_pre_review_baseline" if changes_made else "not_applicable",
                "change_summary": change_summary if changes_made else None,
                "review_duration_minutes": review_duration,
                "occurred_at": review_at,
                "competence_basis": competence_basis,
                "identity_binding": "self_asserted",
            }
        )
    elif review_state == "partial":
        partial_review_note = _text(data, "partial_review_note", maximum=200)

    responsibility_name = _text(data, "responsibility_name", maximum=180)
    responsibility_role = _text(data, "responsibility_role", maximum=40)
    if responsibility_role not in {"author", "editor", "publisher", "organization", "other"}:
        raise RecordCreationError("responsibility_role is unsupported")
    correction_contact = _text(data, "correction_contact", required=False, maximum=200)
    if data.get("declaration_confirmed") is not True:
        raise RecordCreationError("the accuracy declaration must be confirmed")

    record_id = f"{_slug(title, 32)}-{uuid.uuid4().hex[:8]}"
    record_dir = output_root.resolve() / record_id
    bundle_dir = record_dir / "bundle"
    report_path = record_dir / "verification-result.html"
    result_json_path = record_dir / "verification-result.json"
    zip_path = record_dir / f"{record_id}.zip"
    private_key_path = private_key_path.resolve()

    with tempfile.TemporaryDirectory(prefix="pramaan-wizard-") as temp:
        source = Path(temp) / filename
        source.write_bytes(content)
        ai_actor = {"actor_id": _slug(ai_system), "type": "agent", "name": ai_system}
        recorder = Recorder(record_id, _slug(responsibility_name), responsibility_name)
        recorder.record(
            "run.started",
            {"actor_id": "pramaan-wizard", "type": "system", "name": "Pramaan Wizard"},
            {"summary": "Editorial responsibility capture started"},
            occurred_at=generation_at,
        )
        recorder.add_artifact("published-item", source, ai_actor)
        recorder.events[-1]["occurred_at"] = generation_at
        if publication_at is not None:
            recorder.record(
                "run.completed",
                {"actor_id": _slug(responsibility_name), "type": "human", "name": responsibility_name},
                {"summary": "Publication responsibility recorded"},
                occurred_at=publication_at,
            )
        profile = {
            "profile": "editorial-responsibility",
            "profile_version": "0.1",
            "check_set_version": "0.1",
            "item": {
                "item_id": record_id,
                "item_title": title,
                "publication_context": context,
                "published_artifact": f"artifacts/{filename}",
                "content_hash": sha256_bytes(content),
                "published_at": publication_at,
            },
            "generation_events": [
                {
                    "system_id": _slug(ai_system),
                    "system_name": ai_system,
                    "model": ai_system,
                    "model_version": ai_model,
                    "contribution": contribution,
                    "occurred_at": generation_at,
                }
            ],
            "review_events": review_events,
            "review_state": review_state,
            "partial_review_note": partial_review_note,
            "editorial_responsibility": {
                "person_or_entity": responsibility_name,
                "identifier": _slug(responsibility_name),
                "relationship": responsibility_role,
                "correction_contact": correction_contact or None,
                "declared_at": publication_at,
            },
            "disclosure_state": DISCLOSURE_STATES[disclosure],
        }
        recorder.add_profile("editorial-record.json", profile)
        recorder.finalize(bundle_dir, _policy(), private_key_path=private_key_path)

    result = verify_bundle(bundle_dir)
    if not result.integrity_valid:
        raise RuntimeError("created bundle failed signed-file integrity verification")
    write_verification_outputs(result, html_path=report_path, json_path=result_json_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle_dir))

    payload = result.to_dict()
    return CreatedRecord(
        record_id=record_id,
        record_dir=record_dir,
        bundle_dir=bundle_dir,
        report_path=report_path,
        result_json_path=result_json_path,
        zip_path=zip_path,
        title=title,
        stored_file_name=filename,
        file_hash=sha256_file(bundle_dir / "artifacts" / filename),
        valid=result.valid,
        integrity_valid=result.integrity_valid,
        signer_fingerprint=result.signer_fingerprint,
        created_at=payload["verified_at"],
        editorial_counts=payload["editorial_summary"],
    )


class WizardApplication:
    def __init__(self, output_root: Path, private_key_path: Path, token: str | None = None):
        self.output_root = output_root.resolve()
        self.private_key_path = private_key_path.resolve()
        self.token = token or secrets.token_urlsafe(24)
        self.records: dict[str, CreatedRecord] = {}
        self.output_root.mkdir(parents=True, exist_ok=True)

    def handler_class(self):
        application = self
        prefix = f"/session/{self.token}"

        class WizardHandler(BaseHTTPRequestHandler):
            server_version = "PramaanWizard/0.1"

            def _headers(
                self,
                status: int,
                content_type: str,
                length: int | None = None,
                disposition: str | None = None,
            ) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                    "img-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
                )
                if length is not None:
                    self.send_header("Content-Length", str(length))
                if disposition is not None:
                    self.send_header("Content-Disposition", disposition)
                self.end_headers()

            def _json(self, status: int, payload: dict) -> None:
                body = json.dumps(payload).encode("utf-8")
                self._headers(status, "application/json; charset=utf-8", len(body))
                self.wfile.write(body)

            def do_GET(self) -> None:
                path = urlparse(self.path).path.rstrip("/")
                if path == prefix:
                    body = render_wizard_html(prefix).encode("utf-8")
                    self._headers(HTTPStatus.OK, "text/html; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                match = re.fullmatch(re.escape(prefix) + r"/records/([a-z0-9-]+)/(report|download)", path)
                if not match or match.group(1) not in application.records:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
                record = application.records[match.group(1)]
                target = record.report_path if match.group(2) == "report" else record.zip_path
                content_type = "text/html; charset=utf-8" if match.group(2) == "report" else "application/zip"
                body = target.read_bytes()
                disposition = (
                    f'attachment; filename="{record.zip_path.name}"'
                    if match.group(2) == "download"
                    else None
                )
                self._headers(HTTPStatus.OK, content_type, len(body), disposition)
                self.wfile.write(body)

            def do_POST(self) -> None:
                if urlparse(self.path).path != f"{prefix}/create":
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
                if self.headers.get("X-Pramaan-Session") != application.token:
                    self._json(HTTPStatus.FORBIDDEN, {"error": "invalid local session"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request is too large"})
                    return
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                    record = create_editorial_record(data, application.output_root, application.private_key_path)
                except (json.JSONDecodeError, UnicodeDecodeError, RecordCreationError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                except OSError as exc:
                    self._json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"error": f"record creation failed locally: {exc}"},
                    )
                    return
                except (RuntimeError, ValueError):
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "record creation failed locally"})
                    return
                application.records[record.record_id] = record
                self._json(
                    HTTPStatus.CREATED,
                    {
                        "record_id": record.record_id,
                        "title": record.title,
                        "stored_file_name": record.stored_file_name,
                        "file_hash": record.file_hash,
                        "created_at": record.created_at,
                        "valid": record.valid,
                        "integrity_valid": record.integrity_valid,
                        "signer_fingerprint": record.signer_fingerprint,
                        "editorial_counts": record.editorial_counts,
                        "report_url": f"{prefix}/records/{record.record_id}/report",
                        "download_url": f"{prefix}/records/{record.record_id}/download",
                    },
                )

            def log_message(self, format: str, *args) -> None:
                return

        return WizardHandler

    def server(self, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
        return ThreadingHTTPServer((host, port), self.handler_class())


def run_wizard(
    output_root: Path,
    private_key_path: Path,
    port: int = 8766,
    open_browser: bool = True,
) -> None:
    application = WizardApplication(output_root, private_key_path)
    try:
        server = application.server(port=port)
    except OSError:
        if port == 0:
            raise
        print(f"Port {port} is unavailable; selecting a free local port.")
        server = application.server(port=0)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/session/{application.token}/"
    print(f"Pramaan Create Record wizard: {url}")
    print(f"Records will be saved under: {application.output_root}")
    print("Press Ctrl+C to stop the local wizard.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
