# Changelog

All notable changes to Pramaan will be documented here.

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
