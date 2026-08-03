# Pramaan

Pramaan turns an AI-agent workflow run into a portable record bundle that a second person can independently verify for required evidence links, validations, and human approvals.

Pramaan is not an observability dashboard and does not determine whether an AI output is true. It verifies that a producer-supplied record is internally consistent, has not changed since signing, and satisfies its declared reconstruction policy.

## Who It Is For

Pramaan is built for small AI vendors and teams that deliver agent-produced work to customers, partners, reviewers, or security teams outside their own infrastructure.

The core exchange is deliberately simple:

```text
Small AI vendor produces a workflow record
                -> sends bundle + signer fingerprint
Customer verifies it on their own machine
                -> sees a named PASS or FAIL
```

## Ten-Minute Demo

Install from this repository, then run the demonstration:

```powershell
python -m pip install .
pramaan example two-agent demo-bundle
pramaan verify demo-bundle
pramaan tamper demo-bundle --case missing-approval --output demo-tampered
pramaan verify demo-tampered
```

The first verification passes. The second names the changed event record and the missing required approval.

Open `report.html` inside the bundle to inspect the reconstructed workflow without running a server. The report always says verification is required; only the CLI can issue a PASS.

## What The Verifier Checks

- DSSE signature over an in-toto-style statement
- signed subject digests
- event structure and sequence
- registered artifact presence and digests
- evidence references for material claims
- required validations and their status
- required approval roles and status

Pramaan v0.1 produces a standards-conformant DSSE signature payload, but intentionally accepts only one Ed25519 signature whose key ID is the SHA-256 fingerprint of the included public key. It does not yet consume arbitrary multi-signature DSSE envelopes or third-party key-ID conventions.

## Assurance Boundary

- The producer is self-attesting. A valid bundle does not prove that every real-world action was recorded.
- Approval events assert that approval occurred; v0.1 does not authenticate the human or prove meaningful review.
- Producer timestamps are not trusted timestamps.
- Completeness is measured only against the policy included in the bundle.
- Verification does not establish truth, legality, correctness, or source authenticity.
- The signature proves the bundle has not changed since signing by the included key. Trusting that key requires an external fingerprint or identity check.

For a real two-party exchange, obtain the producer's key fingerprint through a separate trusted channel and verify with:

```powershell
pramaan verify received-bundle --expected-key <64-character-fingerprint>
```

An unpinned PASS proves only that the bundle matches the key included inside it. A pinned PASS additionally proves that the included key matches the fingerprint obtained through your separate trusted channel.

## Product Boundary

Pramaan uses established telemetry and attestation concepts. It does not replace OpenTelemetry, model evaluation tools, or production monitoring. Its product boundary is the portable bundle and the second party's independent completeness verification.

## Development

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution scope and [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Status

Pramaan `0.1.0` is a validation prototype. The product is considered validated only when a bundle crosses a real organisational trust boundary and changes whether an external reviewer accepts the producer's claimed workflow.

Version 0.1 ships a complete demonstration producer and verifier. The Python `Recorder` API is intentionally not yet documented as a stable integration contract; early adopters should treat it as experimental while real cross-organisation workflows shape the first supported producer interface.

## License

Apache License 2.0.
