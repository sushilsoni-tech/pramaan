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

## Create A Record Without Code

Start the local wizard:

```powershell
python -m pip install .
pramaan wizard
```

The wizard opens in your browser and stays on `127.0.0.1`. Select the final publication file, describe the AI contribution, choose whether human review was complete, absent, or partial, and name the person or entity accepting responsibility. Pramaan creates a signed bundle, verifies it immediately, provides a local plain-language report, and offers a downloadable ZIP containing only the signed bundle. If the item is not published yet, the wizard records that state without inventing a publication time.

The wizard does not call an AI API, upload the publication, or send the record anywhere. It stores records under `./pramaan-records` by default and keeps a persistent signing key under `~/.pramaan/keys`. Keep that private key private; share the signer fingerprint separately when another person needs to verify your identity. Recipients should unzip the downloaded bundle and run `pramaan verify <unzipped-folder>` rather than relying on a report supplied by the producer.

A record with no or partial substantive review is still signed and downloadable, but its overall editorial verification result is `FAIL`. This preserves the declaration without presenting incomplete review as satisfied.

## Try Verification First

Before creating your own record, verify the included samples:

```powershell
python -m pip install .
pramaan verify samples/editorial-pass
pramaan verify samples/editorial-fail-missing-reviewer
```

The first sample exits `0` with overall `PASS`. The second sample has intact signed files but exits nonzero with overall `FAIL` because no substantive human review and no responsible person are recorded.

This is the product boundary in one minute: Pramaan can show whether a signed record is intact and internally consistent; it still does not prove that the underlying content is true or that the producer recorded everything that happened.

## Article

Read the public product essay: [Human-Reviewed AI Content Needs Evidence, Not Just a Promise](docs/articles/human-reviewed-ai-content-needs-proof.md).

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

## Editorial Responsibility Profile

The optional editorial profile records one AI-assisted publication, its generation and review events, the exact published content hash, and the person or entity named as editorially responsible. Pramaan reports what the signed record contains; it does not decide whether a review was meaningful or make a legal or regulatory determination.

Build and verify the example:

```powershell
pramaan example editorial editorial-bundle --case valid
pramaan verify editorial-bundle `
  --result-html editorial-verification.html `
  --result-json editorial-verification.json
```

Open `editorial-verification.html` for the verifier-generated two-audience result. Its plain-language view is intended for founders, editors, clients, and general reviewers; the technical view contains the fixed check set, review chain, identity assurance, and core verifier findings.

The result files must be written outside `editorial-bundle`. They are created after verification and are intentionally not producer-signed bundle inputs.

Two adverse examples are included:

```powershell
pramaan example editorial missing-reviewer-bundle --case missing-reviewer
pramaan example editorial late-review-bundle --case post-publication
pramaan example editorial policy-failure-bundle --case policy-failure
```

A `not_satisfied` editorial check makes the JSON `valid` field false and the verifier exits nonzero, while `integrity_valid` continues to report signed-file integrity separately. The policy-failure example demonstrates the inverse distinction: intact signed files with an unsatisfied declared reconstruction policy.

## What The Verifier Checks

- DSSE signature over an in-toto-style statement
- signed subject digests
- event structure and sequence
- registered artifact presence and digests
- evidence references for material claims
- required validations and their status
- required approval roles and status
- identical or backwards-moving producer event timestamps
- optional editorial responsibility records using a versioned seven-check set
- published-content hashes, declared substantive review, review timing, change evidence, named responsibility, identity binding, and signed record integrity

Pramaan v0.1 produces a standards-conformant DSSE signature payload, but intentionally accepts only one Ed25519 signature whose key ID is the SHA-256 fingerprint of the included public key. It does not yet consume arbitrary multi-signature DSSE envelopes or third-party key-ID conventions.

## Assurance Boundary

- The producer is self-attesting. A valid bundle does not prove that every real-world action was recorded.
- Approval events assert that approval occurred; v0.1 does not authenticate the human or prove meaningful review.
- Editorial reviewer identities are self-asserted in editorial profile v0.1. Reviewer-held signatures are not yet supported and are reported as `unverifiable`.
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

Pramaan `0.1.0` is the published validation prototype. The current development line is `0.2.0.dev0`. The product is considered validated only when a bundle crosses a real organisational trust boundary and changes whether an external reviewer accepts the producer's claimed workflow.

Version 0.1 ships a complete demonstration producer and verifier. The optional editorial profile, local Create Record wizard, and verifier-generated result surface are under active `0.2.0.dev0` validation. The wizard is the first supported producer experience; the Python `Recorder` API remains experimental while real cross-organisation workflows shape the integration contract.

## License

Apache License 2.0.
