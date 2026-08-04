# Changelog

All notable changes to Pramaan will be documented here.

## Unreleased

### Added

- optional Editorial Responsibility Record profile for one published item;
- versioned seven-check editorial evaluator with `satisfied`, `not_satisfied`, and `unverifiable` outcomes;
- verifier-generated offline HTML and JSON outputs with plain-language and technical views;
- realistic monotonic demo timestamps plus warnings for identical or backwards-moving producer timestamps;
- editorial examples for a valid record, a missing reviewer, and a review recorded after publication.

### Security

- verifier-owned result files are rejected when targeted inside a signed bundle;
- editorial artifact paths are confined to the bundle and symlinks are rejected;
- reviewer identity remains `unverifiable` until independently bound rather than trusting a producer-supplied label.
- editorial timing is evaluated against the latest generation event, preventing an unreviewed regeneration from satisfying the timing check;
- policy completeness and signed-file integrity are reported independently;
- profile content is evaluated only after its signed digest matches;
- missing or unsupported profiles render an explicit not-evaluated state;
- producer-controlled fields are labelled and reserved assurance phrases are removed from verifier-owned surfaces;
- `not_satisfied` editorial checks make machine-readable `valid` false and produce a nonzero process exit;
- change-evidence fields must contain valid SHA-256 digests, and post-review content digests must match the declared publication digest.
- sequential review rounds compare only the latest changed review's post-review digest with the final publication;
- verifier input folder names are treated as potentially producer-controlled text.

## 0.1.0 - 2026-08-03

### Added

- portable signed workflow-record bundle;
- Ed25519 DSSE envelope with an in-toto-style statement;
- material claim, evidence, validation, and approval events;
- declared reconstruction policy;
- independent CLI verification with pinned and unpinned signer disclosure;
- deterministic static HTML reconstruction report;
- tamper demonstration and machine-readable verification output;
- 21 adversarial and integration tests.
- Two-audience offline report with a plain-language customer summary and technical detail view.

### Security

- signed-subject coverage is mandatory;
- POSIX and Windows path escape attempts are rejected;
- symlinked and unsigned extra files are rejected;
- reports are re-derived and byte-compared during verification;
- invalid policies fail closed.
