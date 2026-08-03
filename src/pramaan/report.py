import json
from html import escape
from pathlib import Path


def _event_data(event: dict) -> dict:
    data = event.get("data", {})
    return data if isinstance(data, dict) else {}


def _event_summary(event: dict) -> str:
    data = _event_data(event)
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


def _plain_list(values: list[str], empty: str = "none") -> str:
    cleaned = [str(value) for value in values if value not in (None, "")]
    return ", ".join(cleaned) if cleaned else empty


def _fingerprint_groups(value: str) -> str:
    return " ".join(value[index : index + 16] for index in range(0, len(value), 16))


def render_report(descriptor: dict, events: list[dict], policy: dict) -> str:
    events = [event for event in events if isinstance(event, dict)]
    producer = descriptor["producer"]
    producer_name = str(producer["name"])
    fingerprint = str(descriptor["public_key_fingerprint"])

    claims = [
        event
        for event in events
        if event.get("type") == "claim.asserted" and _event_data(event).get("material") is True
    ]
    evidence = [event for event in events if event.get("type") == "evidence.registered"]
    validations = [event for event in events if event.get("type") == "validation.completed"]
    approvals = [event for event in events if event.get("type") == "approval.recorded"]

    artifact_paths = [_event_data(event).get("artifact_path", "") for event in evidence]
    validation_entries = [
        f"{_event_data(event).get('name', 'unnamed')} ({_event_data(event).get('status', 'status not recorded')})"
        for event in validations
    ]
    approval_entries = [
        f"{_event_data(event).get('role', 'unnamed role')} ({_event_data(event).get('status', 'status not recorded')})"
        for event in approvals
    ]
    required_validations = [
        f"{item['name']} must be {item['status']}" for item in policy["required_validations"]
    ]
    required_approvals = [
        f"{item['role']} must be {item['status']}" for item in policy["required_approvals"]
    ]

    rows = []
    for event in events:
        actor = event.get("actor")
        if not isinstance(actor, dict):
            actor = {}
        actor_name = actor.get("name") or actor.get("actor_id") or "Unknown actor"
        raw_data = json.dumps(_event_data(event), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        rows.append(
            "<tr>"
            f"<td>{escape(str(event.get('sequence', '')))}</td>"
            f"<td><code>{escape(str(event.get('type', '')))}</code></td>"
            f"<td>{escape(str(actor_name))}</td>"
            f"<td>{escape(str(_event_summary(event)))}</td>"
            f"<td>{escape(str(event.get('occurred_at', '')))}</td>"
            f"<td><details><summary>View data</summary><pre>{escape(raw_data)}</pre></details></td>"
            "</tr>"
        )

    policy_rows = [
        "<tr><td>Evidence for material statements</td>"
        f"<td>{'Required' if policy['material_claims_require_evidence'] else 'Not required'}</td>"
        "<td>Only by <code>pramaan verify</code></td></tr>"
    ]
    policy_rows.extend(
        f"<tr><td>Validation</td><td>{escape(item['name'])} must be {escape(item['status'])}</td>"
        "<td>Only by <code>pramaan verify</code></td></tr>"
        for item in policy["required_validations"]
    )
    policy_rows.extend(
        f"<tr><td>Approval</td><td>{escape(item['role'])} must be {escape(item['status'])}</td>"
        "<td>Only by <code>pramaan verify</code></td></tr>"
        for item in policy["required_approvals"]
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pramaan Record - {escape(str(descriptor['run_id']))}</title>
  <style>
    :root {{ --ink:#182028; --muted:#596673; --line:#cfd6dc; --bg:#f4f6f7; --panel:#ffffff; --accent:#176b5b; --accent-soft:#e7f2ef; --stage:#e8ecef; --stage-ink:#394650; --caution:#8a4b08; --caution-bg:#fff8eb; --code:#101820; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Segoe UI,Arial,sans-serif; color:var(--ink); background:var(--bg); line-height:1.6; }}
    main {{ width:min(1180px,calc(100vw - 32px)); margin:0 auto; padding:24px 0 56px; }}
    header {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-start; padding-bottom:16px; border-bottom:1px solid var(--line); }}
    h1,h2,h3,p {{ margin-top:0; letter-spacing:0; }}
    h1 {{ margin-bottom:4px; font-size:26px; line-height:1.25; }}
    h2 {{ margin-bottom:10px; font-size:18px; }}
    h3 {{ margin-bottom:6px; font-size:16px; }}
    p,li {{ font-size:16px; }}
    .eyebrow {{ margin-bottom:4px; color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; }}
    .meta {{ margin-bottom:0; color:var(--muted); font-size:14px; }}
    .stage {{ flex:none; color:var(--stage-ink); font-size:13px; font-weight:700; border:1px solid #c4cdd4; background:var(--stage); padding:5px 9px; border-radius:4px; }}
    .tablist {{ display:inline-flex; margin:18px 0 4px; border:1px solid var(--line); border-radius:6px; overflow:hidden; background:var(--panel); }}
    .tablist button {{ appearance:none; border:0; border-right:1px solid var(--line); background:transparent; color:var(--muted); padding:8px 12px; font:600 14px Segoe UI,Arial,sans-serif; cursor:pointer; }}
    .tablist button:last-child {{ border-right:0; }}
    .tablist button[aria-selected="true"] {{ color:var(--ink); background:var(--accent-soft); }}
    .tablist button:focus-visible {{ outline:2px solid var(--accent); outline-offset:-3px; }}
    [hidden] {{ display:none !important; }}
    .summary-view {{ width:min(720px,100%); }}
    section {{ padding:22px 0; border-bottom:1px solid var(--line); }}
    section:last-child {{ border-bottom:0; }}
    .lead {{ font-size:17px; }}
    .decision {{ border-left:4px solid var(--accent); padding:2px 0 2px 14px; }}
    .decision strong {{ display:block; margin-bottom:4px; font-size:18px; }}
    .steps {{ margin:0; padding-left:22px; }}
    .steps li {{ margin:0 0 16px; padding-left:5px; }}
    .command {{ margin:10px 0; padding:14px; overflow-x:auto; border:1px solid #37424b; border-radius:4px; background:var(--code); color:#f7f9fa; font:14px/1.5 Consolas,monospace; user-select:all; }}
    .fingerprint {{ padding:11px 12px; overflow-wrap:anywhere; border:1px solid var(--line); background:var(--panel); font:14px/1.6 Consolas,monospace; }}
    .sender-summary {{ margin:0; padding-left:20px; }}
    .sender-summary li {{ margin-bottom:7px; }}
    .boundary {{ border-left:4px solid var(--caution); padding-left:14px; }}
    .boundary strong {{ color:#683a08; }}
    .technical-view p,.technical-view li {{ font-size:14px; }}
    .identifier-grid {{ display:grid; grid-template-columns:180px minmax(0,1fr); gap:0; border-top:1px solid var(--line); }}
    .identifier-grid dt,.identifier-grid dd {{ margin:0; padding:9px 10px; border-bottom:1px solid var(--line); }}
    .identifier-grid dt {{ color:var(--muted); font-weight:600; }}
    .identifier-grid dd {{ overflow-wrap:anywhere; background:var(--panel); }}
    .table-wrap {{ overflow-x:auto; border:1px solid var(--line); }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel); font-size:13px; }}
    th,td {{ padding:9px 10px; text-align:left; vertical-align:top; border-bottom:1px solid var(--line); }}
    tr:last-child td {{ border-bottom:0; }}
    th {{ color:var(--muted); font-size:12px; background:#f8fafb; }}
    code,pre {{ font-family:Consolas,monospace; font-size:12px; }}
    details summary {{ color:var(--accent); cursor:pointer; white-space:nowrap; }}
    details pre {{ max-width:460px; margin:8px 0 0; padding:8px; overflow:auto; background:var(--bg); white-space:pre-wrap; overflow-wrap:anywhere; }}
    .technical-note {{ color:var(--muted); }}
    @media (prefers-color-scheme:dark) {{
      :root {{ --ink:#edf2f5; --muted:#aeb8c1; --line:#46515a; --bg:#151a1e; --panel:#1d2429; --accent:#70c5b3; --accent-soft:#203d37; --stage:#2a3339; --stage-ink:#e2e8ec; --caution:#efb35f; --caution-bg:#332817; --code:#090d10; }}
      .boundary strong {{ color:#efc07e; }} th {{ background:#222a30; }}
    }}
    @media (max-width:760px) {{ header {{ display:block; }} .stage {{ display:inline-block; margin-top:12px; }} .identifier-grid {{ grid-template-columns:1fr; }} .identifier-grid dt {{ padding-bottom:2px; border-bottom:0; }} .identifier-grid dd {{ padding-top:2px; }} }}
    @media print {{ @page {{ margin:18mm; }} body {{ background:#fff; color:#000; }} main {{ width:100%; padding:0; }} .tablist {{ display:none; }} [hidden] {{ display:block !important; }} .command {{ break-inside:avoid; }} .technical-view {{ break-before:page; }} }}
  </style>
  <noscript><style>.tablist{{display:none}} #technical-view[hidden]{{display:block!important}}</style></noscript>
</head>
<body>
<main>
  <header>
    <div>
      <p class="eyebrow">Workflow record from {escape(producer_name)}</p>
      <h1>{escape(str(descriptor['run_id']))}</h1>
      <p class="meta">Created {escape(str(descriptor['created_at']))} | Not independently checked</p>
    </div>
    <span class="stage">Ready for independent check</span>
  </header>

  <div class="tablist" role="tablist" aria-label="Report audience">
    <button id="summary-tab" type="button" role="tab" aria-selected="true" aria-controls="summary-view">Summary</button>
    <button id="technical-tab" type="button" role="tab" aria-selected="false" aria-controls="technical-view">Technical detail</button>
  </div>

  <div id="summary-view" class="summary-view" role="tabpanel" aria-labelledby="summary-tab">
    <section>
      <h2>What this is</h2>
      <p class="lead">{escape(producer_name)} says AI agents were used to complete work for you. This page records what those agents did, what evidence was attached, what checks were recorded, and what approval was recorded.</p>
      <p>The sender created this page as part of the package. It is useful context, but it is not an independent verdict.</p>
    </section>

    <section>
      <div class="decision">
        <strong>Can I accept it yet? Not yet.</strong>
        <p>First run Pramaan's check on your own computer. Until then, treat this page as information supplied by the sender, not information independently confirmed.</p>
      </div>
    </section>

    <section>
      <h2>What to do next</h2>
      <ol class="steps">
        <li><strong>Ask {escape(producer_name)} for their fingerprint through a separate trusted channel.</strong><br>A fingerprint is a 64-character code identifying the signing key. Obtain it by phone, in person, or through an account you already know belongs to the sender.</li>
        <li><strong>Run this check on your own computer.</strong>
          <pre class="command">pramaan verify &lt;the-folder-you-received&gt; --expected-key &lt;the-64-character-fingerprint&gt;</pre>
        </li>
        <li><strong>Use the result printed by the command.</strong><br>It prints <code>PASS</code> or <code>FAIL</code> and names every problem found. That result is the answer, not this page.</li>
      </ol>
      <h3>The fingerprint written inside this package</h3>
      <div class="fingerprint">{escape(_fingerprint_groups(fingerprint))}</div>
      <p class="technical-note">This is only what the package says about itself. It matters only if it matches the fingerprint you obtained separately.</p>
    </section>

    <section>
      <h2>What the sender says happened</h2>
      <ul class="sender-summary">
        <li>{len(events)} workflow steps were recorded in order.</li>
        <li>{len(evidence)} evidence file(s) were attached: {escape(_plain_list(artifact_paths))}.</li>
        <li>{len(claims)} statement(s) were marked as important enough to require checking.</li>
        <li>{len(validations)} check(s) were recorded: {escape(_plain_list(validation_entries))}.</li>
        <li>{len(approvals)} approval(s) were recorded: {escape(_plain_list(approval_entries))}.</li>
      </ul>
      <p>These are the sender's entries. The independent check tests whether the files are unchanged and whether the entries satisfy the included rules.</p>
    </section>

    <section>
      <h2>What rules were included</h2>
      <p>The sender included a rule set called <code>{escape(str(policy['policy_id']))}</code>:</p>
      <ul>
        <li>Important statements need attached evidence: <strong>{'yes' if policy['material_claims_require_evidence'] else 'no'}</strong>.</li>
        <li>Required checks: <strong>{escape(_plain_list(required_validations))}</strong>.</li>
        <li>Required approvals: <strong>{escape(_plain_list(required_approvals))}</strong>.</li>
      </ul>
      <p>{escape(producer_name)} supplied these rules. Pramaan can check whether the record meets them; it cannot decide whether the rules were demanding enough for your purpose.</p>
    </section>

    <section class="boundary">
      <h2>What even a PASS cannot prove</h2>
      <ul>
        <li><strong>The record is complete.</strong> Actions the sender did not record leave no trace here.</li>
        <li><strong>The evidence is genuine.</strong> Pramaan can detect changes to attached files, not whether their contents are accurate.</li>
        <li><strong>A person truly reviewed the work.</strong> Version 0.1 records approval but does not authenticate the person or the quality of their review.</li>
        <li><strong>The timestamps are trusted.</strong> They were supplied by the sender's system.</li>
        <li><strong>The AI's work is correct.</strong> Pramaan does not judge truth, legality, or fitness for purpose.</li>
        <li><strong>Who signed it.</strong> Identity is established only when you use <code>--expected-key</code> with a fingerprint obtained separately.</li>
      </ul>
    </section>

    <section>
      <h2>If the check says FAIL</h2>
      <p>A <code>FAIL</code> means the package does not match its own signature or its own included rules. It is a reason to ask {escape(producer_name)} about the named problem, not a conclusion about anyone's intent.</p>
    </section>
  </div>

  <div id="technical-view" class="technical-view" role="tabpanel" aria-labelledby="technical-tab" hidden>
    <section>
      <h2>Record identifiers</h2>
      <dl class="identifier-grid">
        <dt>Run ID</dt><dd><code>{escape(str(descriptor['run_id']))}</code></dd>
        <dt>Specification</dt><dd><code>{escape(str(descriptor['spec_version']))}</code></dd>
        <dt>Producer</dt><dd>{escape(producer_name)} (<code>{escape(str(producer['id']))}</code>)</dd>
        <dt>Created at</dt><dd><code>{escape(str(descriptor['created_at']))}</code></dd>
        <dt>Policy</dt><dd><code>{escape(str(policy['policy_id']))}</code> version <code>{escape(str(policy['policy_version']))}</code></dd>
        <dt>Embedded key fingerprint</dt><dd><code>{escape(fingerprint)}</code></dd>
      </dl>
    </section>

    <section>
      <h2>Declared policy requirements</h2>
      <p class="technical-note">Presence here is not satisfaction. Only the independent verifier evaluates coverage and status.</p>
      <div class="table-wrap"><table><thead><tr><th>Requirement type</th><th>Included rule</th><th>Verified by</th></tr></thead><tbody>{''.join(policy_rows)}</tbody></table></div>
    </section>

    <section>
      <h2>Recorded event timeline</h2>
      <div class="table-wrap"><table><thead><tr><th>#</th><th>Event</th><th>Actor</th><th>Recorded action</th><th>Producer time</th><th>Raw data</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
    </section>

    <section>
      <h2>What the verifier will check</h2>
      <ul>
        <li>DSSE signature and the fingerprint of the included Ed25519 public key.</li>
        <li>Signed file digests and the absence of unsigned extra files.</li>
        <li>Event structure, sequence, and registered artifact digests.</li>
        <li>Evidence links for every material claim when the policy requires them.</li>
        <li>Required validation names, statuses, and material-claim coverage.</li>
        <li>Required approval roles, statuses, and material-claim coverage.</li>
        <li>Whether this report can be reproduced exactly from the signed events and policy.</li>
      </ul>
    </section>

    <section class="boundary">
      <h2>Technical assurance boundary</h2>
      <ul>
        <li>The producer controls capture and policy; verification cannot detect omitted real-world actions.</li>
        <li>Approval events are assertions, not authenticated identity or proof of meaningful review.</li>
        <li>Producer timestamps are not trusted timestamps.</li>
        <li>Completeness is relative only to the included producer-supplied policy.</li>
        <li>Verification does not establish truth, legality, correctness, or source authenticity.</li>
        <li>An unpinned signature proves integrity against the included key, not the identity of its owner.</li>
      </ul>
    </section>
  </div>
</main>
<script>
  (() => {{
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
    const panels = tabs.map((tab) => document.getElementById(tab.getAttribute('aria-controls')));
    tabs.forEach((tab, index) => tab.addEventListener('click', () => {{
      tabs.forEach((item, itemIndex) => {{
        const selected = itemIndex === index;
        item.setAttribute('aria-selected', String(selected));
        panels[itemIndex].hidden = !selected;
      }});
    }}));
  }})();
</script>
</body>
</html>
"""
    return html


def generate_report(path: Path, descriptor: dict, events: list[dict], policy: dict) -> None:
    html = render_report(descriptor, events, policy)
    path.write_bytes(html.encode("utf-8"))
