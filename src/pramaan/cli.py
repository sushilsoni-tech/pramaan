import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .examples import build_two_agent_example
from .tamper import TAMPER_CASES, create_tampered_copy
from .verify import verify_bundle


def _print_result(result, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result.to_dict(), indent=2))
        return
    print(f"Pramaan verification: {'PASS' if result.valid else 'FAIL'}")
    print(f"Bundle: {result.bundle}")
    if result.signer_fingerprint:
        print(f"Signer fingerprint: {result.signer_fingerprint}")
        print(f"Signer trust: {'PINNED - matched independently expected key' if result.signer_pinned else 'UNPINNED - valid only against the key included in this bundle'}")
    if result.policy_summary:
        summary = result.policy_summary
        print(
            "Policy enforced: "
            f"evidence_links={'on' if summary['material_claims_require_evidence'] else 'off'}, "
            f"material_claims={summary['material_claim_count']}, "
            f"required_validations={summary['required_validation_count']}, "
            f"required_approvals={summary['required_approval_count']}"
        )
    for finding in result.findings:
        marker = {"error": "ERROR", "warning": "WARN", "info": "OK"}.get(finding.severity, finding.severity.upper())
        print(f"[{marker}] {finding.code}: {finding.message}")
    print("Boundary: verification covers internal consistency and the declared policy, not truth or complete disclosure.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pramaan", description="Create and verify portable AI workflow records")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    example = subcommands.add_parser("example", help="Build a signed example bundle")
    example.add_argument("name", choices=["two-agent"])
    example.add_argument("output", type=Path)

    verify = subcommands.add_parser("verify", help="Verify a Pramaan bundle")
    verify.add_argument("bundle", type=Path)
    verify.add_argument("--expected-key", help="Independently obtained signer fingerprint")
    verify.add_argument("--json", action="store_true", help="Emit machine-readable verification output")

    tamper = subcommands.add_parser("tamper", help="Create an intentionally invalid demonstration copy")
    tamper.add_argument("bundle", type=Path)
    tamper.add_argument("--case", required=True, choices=sorted(TAMPER_CASES))
    tamper.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "example":
            output = build_two_agent_example(args.output)
            print(f"Created signed Pramaan bundle: {output.resolve()}")
            print(f"Open reconstruction report: {(output / 'report.html').resolve()}")
            return
        if args.command == "tamper":
            output = create_tampered_copy(args.bundle, args.output, args.case)
            print(f"Created intentionally invalid bundle: {output.resolve()}")
            return
        if args.command == "verify":
            result = verify_bundle(args.bundle, args.expected_key)
            _print_result(result, args.json)
            raise SystemExit(0 if result.valid else 1)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"pramaan: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
