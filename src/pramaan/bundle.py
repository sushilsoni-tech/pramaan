import json
import mimetypes
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .canonical import canonical_json_bytes, sha256_file, write_json
from .crypto import generate_keypair, sign_statement
from .report import generate_report


SPEC_VERSION = "0.1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://github.com/sushilsoni-tech/pramaan#attestation-run-v0.1"
EVENT_TYPES = {
    "run.started",
    "evidence.registered",
    "claim.asserted",
    "validation.completed",
    "approval.recorded",
    "run.completed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Recorder:
    def __init__(self, run_id: str, producer_id: str, producer_name: str):
        self.run_id = run_id
        self.producer = {"id": producer_id, "name": producer_name}
        self.events: list[dict] = []
        self.artifacts: dict[str, Path] = {}

    def record(self, event_type: str, actor: dict, data: dict, occurred_at: str | None = None) -> str:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event type: {event_type}")
        event_id = f"evt-{uuid.uuid4()}"
        self.events.append(
            {
                "event_id": event_id,
                "sequence": len(self.events) + 1,
                "type": event_type,
                "occurred_at": occurred_at or utc_now(),
                "actor": actor,
                "data": data,
            }
        )
        return event_id

    def add_artifact(self, evidence_id: str, source_path: Path, actor: dict, media_type: str | None = None) -> str:
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        target_name = f"artifacts/{source_path.name}"
        if target_name in self.artifacts:
            raise ValueError(f"duplicate artifact name: {source_path.name}")
        self.artifacts[target_name] = source_path
        return self.record(
            "evidence.registered",
            actor,
            {
                "evidence_id": evidence_id,
                "artifact_path": target_name,
                "sha256": sha256_file(source_path),
                "media_type": media_type or mimetypes.guess_type(source_path.name)[0] or "application/octet-stream",
            },
        )

    def finalize(self, output_dir: Path, policy: dict, private_key_path: Path | None = None) -> Path:
        if output_dir.exists() and any(output_dir.iterdir()):
            raise ValueError(f"output directory is not empty: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "artifacts").mkdir(exist_ok=True)

        for relative_name, source in self.artifacts.items():
            target = output_dir / relative_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        events_path = output_dir / "events.jsonl"
        events_path.write_bytes(b"".join(canonical_json_bytes(event) + b"\n" for event in self.events))
        write_json(output_dir / "policy.json", policy)

        public_path = output_dir / "public-key.pem"
        ephemeral_key_dir = None
        if private_key_path is None:
            ephemeral_key_dir = tempfile.TemporaryDirectory(prefix="pramaan-signing-")
            private_key_path = Path(ephemeral_key_dir.name) / "producer-private.pem"
        if private_key_path.exists():
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from .crypto import public_key_fingerprint

            key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("private key must be Ed25519")
            public_path.write_bytes(
                key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
            fingerprint = public_key_fingerprint(public_path)
        else:
            fingerprint = generate_keypair(private_key_path, public_path)

        descriptor = {
            "spec_version": SPEC_VERSION,
            "run_id": self.run_id,
            "producer": self.producer,
            "created_at": utc_now(),
            "public_key_fingerprint": fingerprint,
        }
        write_json(output_dir / "bundle.json", descriptor)
        generate_report(output_dir / "report.html", descriptor, self.events, policy)

        subject_names = ["bundle.json", "events.jsonl", "policy.json", "report.html", *sorted(self.artifacts)]
        statement = {
            "_type": STATEMENT_TYPE,
            "subject": [
                {"name": name, "digest": {"sha256": sha256_file(output_dir / name)}} for name in subject_names
            ],
            "predicateType": PREDICATE_TYPE,
            "predicate": {
                "spec_version": SPEC_VERSION,
                "run_id": self.run_id,
                "producer": self.producer,
                "created_at": descriptor["created_at"],
                "assurance": "producer-self-attested",
            },
        }
        write_json(output_dir / "attestation.dsse.json", sign_statement(statement, private_key_path, fingerprint))
        if ephemeral_key_dir is not None:
            ephemeral_key_dir.cleanup()
        return output_dir


def load_events(path: Path) -> list[dict]:
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on events.jsonl line {line_number}: {exc}") from exc
    return events
