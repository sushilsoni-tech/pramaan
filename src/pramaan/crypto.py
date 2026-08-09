import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .canonical import canonical_json_bytes, sha256_bytes


PAYLOAD_TYPE = "application/vnd.in-toto+json"


def secure_private_key_permissions(private_path: Path) -> None:
    if os.name != "posix":
        return
    os.chmod(private_path, 0o600)


def _mkdir_private_parent(parent: Path) -> bool:
    if parent.exists():
        return False
    parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(parent, 0o700)
    return True


def _write_private_key(private_path: Path, data: bytes) -> None:
    if os.name != "posix":
        private_path.write_bytes(data)
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(private_path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    except Exception:
        try:
            private_path.unlink()
        finally:
            raise


def pae(payload_type: str, payload: bytes) -> bytes:
    type_bytes = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(type_bytes), type_bytes, len(payload), payload)


def generate_keypair(private_path: Path, public_path: Path) -> str:
    private_key = Ed25519PrivateKey.generate()
    _mkdir_private_parent(private_path.parent)
    _write_private_key(
        private_path,
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )
    secure_private_key_permissions(private_path)
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return public_key_fingerprint(public_path)


def public_key_fingerprint(public_path: Path) -> str:
    public_key = serialization.load_pem_public_key(public_path.read_bytes())
    if not isinstance(public_key, Ed25519PublicKey):
        raise ValueError("public key must be Ed25519")
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return sha256_bytes(raw)


def sign_statement(statement: dict, private_path: Path, keyid: str) -> dict:
    private_key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("private key must be Ed25519")
    payload = canonical_json_bytes(statement)
    signature = private_key.sign(pae(PAYLOAD_TYPE, payload))
    return {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode("ascii"),
        "signatures": [{"keyid": keyid, "sig": base64.b64encode(signature).decode("ascii")}],
    }


def verify_envelope(envelope: dict, public_path: Path) -> tuple[dict, str]:
    if envelope.get("payloadType") != PAYLOAD_TYPE:
        raise ValueError("unsupported DSSE payload type")
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or len(signatures) != 1:
        raise ValueError("exactly one DSSE signature is required")

    payload = base64.b64decode(envelope["payload"], validate=True)
    signature = base64.b64decode(signatures[0]["sig"], validate=True)
    public_key = serialization.load_pem_public_key(public_path.read_bytes())
    if not isinstance(public_key, Ed25519PublicKey):
        raise ValueError("public key must be Ed25519")
    public_key.verify(signature, pae(PAYLOAD_TYPE, payload))
    fingerprint = public_key_fingerprint(public_path)
    if signatures[0].get("keyid") != fingerprint:
        raise ValueError("signature key ID does not match the included public key")

    import json

    return json.loads(payload.decode("utf-8")), fingerprint
