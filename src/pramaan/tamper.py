import json
import shutil
from pathlib import Path

from .canonical import canonical_json_bytes


TAMPER_CASES = {"modified-event", "missing-artifact", "broken-evidence-link", "missing-approval"}


def create_tampered_copy(source: Path, output: Path, case: str) -> Path:
    if case not in TAMPER_CASES:
        raise ValueError(f"unsupported tamper case: {case}")
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    shutil.copytree(source, output)

    events_path = output / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if case == "modified-event":
        claim = next(event for event in events if event["type"] == "claim.asserted")
        claim["data"]["text"] = "This claim was modified after signing."
    elif case == "missing-artifact":
        evidence = next(event for event in events if event["type"] == "evidence.registered")
        (output / evidence["data"]["artifact_path"]).unlink()
        return output
    elif case == "broken-evidence-link":
        claim = next(event for event in events if event["type"] == "claim.asserted")
        claim["data"]["evidence_refs"] = ["evidence-that-does-not-exist"]
    elif case == "missing-approval":
        events = [event for event in events if event["type"] != "approval.recorded"]
        for sequence, event in enumerate(events, start=1):
            event["sequence"] = sequence

    events_path.write_bytes(b"".join(canonical_json_bytes(event) + b"\n" for event in events))
    return output

