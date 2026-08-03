from html import escape
from pathlib import Path


def _event_summary(event: dict) -> str:
    data = event.get("data", {})
    if not isinstance(data, dict):
        data = {}
    event_type = event.get("type", "unknown")
    if event_type == "evidence.registered":
        return f"Registered evidence {data.get('evidence_id', '')}: {data.get('artifact_path', '')}"
    if event_type == "claim.asserted":
        return f"Asserted claim {data.get('claim_id', '')}: {data.get('text', '')}"
    if event_type == "validation.completed":
        return f"Validation {data.get('name', '')}: {data.get('status', '')}"
    if event_type == "approval.recorded":
        return f"Approval by {data.get('role', '')}: {data.get('status', '')}"
    if event_type == "exception.recorded":
        return f"Exception {data.get('code', '')}: {data.get('description', '')}"
    return str(data.get("summary", event_type))


def render_report(descriptor: dict, events: list[dict], policy: dict) -> str:
    events = [event for event in events if isinstance(event, dict)]
    rows = []
    for event in events:
        actor = event.get("actor")
        if not isinstance(actor, dict):
            actor = {}
        actor_name = actor.get("name") or actor.get("actor_id") or "Unknown actor"
        rows.append(
            "<tr>"
            f"<td>{event.get('sequence', '')}</td>"
            f"<td><code>{escape(str(event.get('type', '')))}</code></td>"
            f"<td>{escape(str(actor_name))}</td>"
            f"<td>{escape(str(_event_summary(event)))}</td>"
            f"<td>{escape(str(event.get('occurred_at', '')))}</td>"
            "</tr>"
        )

    claims = [
        event
        for event in events
        if event.get("type") == "claim.asserted"
        and isinstance(event.get("data"), dict)
        and event["data"].get("material") is True
    ]
    evidence = [event for event in events if event.get("type") == "evidence.registered"]
    validations = [event for event in events if event.get("type") == "validation.completed"]
    approvals = [event for event in events if event.get("type") == "approval.recorded"]

    evidence_rule = policy["material_claims_require_evidence"]
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pramaan Record - {escape(descriptor['run_id'])}</title>
  <style>
    :root {{ color-scheme: light; --ink:#17202a; --muted:#5c6875; --line:#d8dee5; --bg:#f4f6f8; --panel:#fff; --accent:#176b5b; --warn:#8a4b08; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Segoe UI,Arial,sans-serif; color:var(--ink); background:var(--bg); line-height:1.45; }}
    main {{ width:min(1180px,calc(100vw - 32px)); margin:0 auto; padding:24px 0 48px; }}
    header {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-start; padding-bottom:18px; border-bottom:1px solid var(--line); }}
    h1,h2,p {{ margin:0; letter-spacing:0; }} h1 {{ font-size:26px; }} h2 {{ font-size:17px; margin-bottom:10px; }}
    .eyebrow {{ color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; }}
    .status {{ color:var(--warn); font-weight:700; border:1px solid #d8b26b; background:#fff8eb; padding:5px 9px; border-radius:6px; }}
    .summary {{ display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); gap:10px; margin:16px 0; }}
    .metric {{ background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:12px; }}
    .metric strong {{ display:block; font-size:22px; }} .metric span {{ color:var(--muted); font-size:12px; }}
    section {{ margin-top:20px; }}
    .notice {{ border-left:4px solid var(--warn); background:#fff8eb; padding:12px; color:#5e3705; }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); font-size:13px; }}
    th,td {{ padding:9px 10px; text-align:left; vertical-align:top; border-bottom:1px solid var(--line); }}
    th {{ color:var(--muted); font-size:12px; background:#fafbfc; }}
    code {{ font-family:Consolas,monospace; font-size:12px; }}
    .meta {{ color:var(--muted); margin-top:6px; }}
    @media (max-width:760px) {{ header {{ display:block; }} .status {{ display:inline-block; margin-top:10px; }} .summary {{ grid-template-columns:repeat(2,1fr); }} table {{ display:block; overflow-x:auto; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <div><p class="eyebrow">Pramaan self-attested workflow record</p><h1>{escape(descriptor['run_id'])}</h1><p class="meta">Producer: {escape(descriptor['producer']['name'])} | Policy: {escape(policy['policy_id'])}</p></div>
    <span class="status">Verification required</span>
  </header>
  <div class="summary">
    <div class="metric"><strong>{len(events)}</strong><span>Recorded events</span></div>
    <div class="metric"><strong>{len(evidence)}</strong><span>Evidence artifacts</span></div>
    <div class="metric"><strong>{len(claims)}</strong><span>Material claims</span></div>
    <div class="metric"><strong>{len(approvals)}</strong><span>Approval events</span></div>
  </div>
  <div class="notice"><strong>Verification is not truth.</strong> This producer-supplied record can be checked for integrity and declared-policy completeness. It does not prove that unrecorded actions did not occur, that evidence is authentic, or that approval was meaningful.</div>
  <section><h2>Workflow reconstruction</h2>
    <table><thead><tr><th>#</th><th>Event</th><th>Actor</th><th>Recorded action</th><th>Producer time</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
  </section>
  <section><h2>Declared requirements</h2>
    <table><thead><tr><th>Requirement</th><th>Declared policy</th><th>Recorded events</th></tr></thead><tbody>
      <tr><td>Evidence links</td><td>Material claims require evidence: {str(evidence_rule).lower()}</td><td>{len(claims)} material claims</td></tr>
      <tr><td>Validations</td><td>{escape(', '.join(item['name'] for item in policy['required_validations']) or 'None')}</td><td>{len(validations)} validation events</td></tr>
      <tr><td>Approvals</td><td>{escape(', '.join(item['role'] for item in policy['required_approvals']) or 'None')}</td><td>{len(approvals)} approval events</td></tr>
    </tbody></table>
  </section>
</main>
</body>
</html>
"""
    return html


def generate_report(path: Path, descriptor: dict, events: list[dict], policy: dict) -> None:
    html = render_report(descriptor, events, policy)
    path.write_bytes(html.encode("utf-8"))
