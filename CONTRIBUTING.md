# Contributing to Pramaan

Pramaan is intentionally narrow. Contributions should strengthen portable, independent verification without turning the project into a general observability platform.

## Good Contributions

- false-PASS and path-confinement tests;
- clearer assurance-boundary wording;
- interoperability improvements for DSSE, in-toto, and OpenTelemetry;
- fixes that reduce integration effort for small AI teams;
- deterministic verification and report-generation improvements.

## Out of Scope for v0.1

- hosted dashboards;
- enterprise identity systems;
- framework-specific integration matrices;
- automated truth or legality judgments;
- claims-processing or other vertical workflow logic.

## Development

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
```

Open an issue before a large change. Pull requests should explain the assurance claim affected, the failure mode, and the test proving the behavior.

