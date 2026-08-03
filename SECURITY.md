# Security Policy

## Supported Version

Only the latest `0.1.x` release is supported during the validation period.

## Reporting A Vulnerability

Do not open a public issue for a suspected vulnerability that could cause a false PASS, signature confusion, unsafe file access, or disclosure of local files.

Use GitHub's private vulnerability reporting feature for this repository. Include:

- affected command and version;
- minimal malicious bundle or reproduction;
- expected and actual verifier result;
- whether the issue can produce PASS, escape the bundle directory, or misstate signer trust.

The maintainer will acknowledge a complete report as capacity allows. This is an early open-source project and does not offer a security service-level agreement.

If private vulnerability reporting is unavailable, open a public issue containing no vulnerability details and ask the maintainer to establish a private reporting channel.

## Assurance Boundary

Pramaan verifies a producer-supplied record against a declared policy. It does not prove that the producer recorded every action, that evidence is true, that a human meaningfully reviewed the output, or that timestamps are trusted.
