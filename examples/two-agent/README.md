# Two-Agent Example

This example records a research agent, a review agent, one evidence artifact, one material claim, a citation validation, and a human approval.

```powershell
python -m pip install .
pramaan example two-agent outputs/pramaan-product-demo/two-agent-valid
pramaan verify outputs/pramaan-product-demo/two-agent-valid
pramaan tamper outputs/pramaan-product-demo/two-agent-valid --case missing-approval --output outputs/pramaan-product-demo/two-agent-missing-approval
pramaan verify outputs/pramaan-product-demo/two-agent-missing-approval
```

The invalid copy is expected to fail verification.
