# Editorial Responsibility Example

This example records one AI-assisted publication, its human review, and the person named as editorially responsible.

```powershell
pramaan example editorial editorial-bundle --case valid
pramaan verify editorial-bundle `
  --result-html editorial-verification.html `
  --result-json editorial-verification.json
```

Open `editorial-verification.html` directly in a browser. It is a verifier-generated output and must remain outside the signed bundle.

The editorial checks describe only the signed producer record. They do not establish content accuracy, meaningful review, authenticated reviewer identity, complete disclosure, or legal compliance.
