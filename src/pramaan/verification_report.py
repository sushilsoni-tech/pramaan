import json
import re
from collections import Counter
from html import escape
from pathlib import Path

from .verify import INTEGRITY_FAILURE_CODES, LIMITATIONS, VerificationResult


RESERVED_ASSURANCE_PHRASES = (
    "article 50 compliant",
    "exemption satisfied",
    "no labelling required",
    "no labeling required",
)


def _value(value: object, fallback: str = "not recorded") -> str:
    return escape(str(value)) if value not in (None, "") else fallback


def _producer_value(value: object, fallback: str = "not recorded") -> str:
    if value in (None, ""):
        return fallback
    text = str(value)
    for phrase in RESERVED_ASSURANCE_PHRASES:
        text = re.sub(re.escape(phrase), "[reserved assurance phrase removed]", text, flags=re.IGNORECASE)
    return escape(text)


def _status(value: str) -> str:
    return f'<span class="status status-{escape(value)}">{escape(value)}</span>'


def _review_fact(label: str, value: object, suffix: str = "") -> str:
    if value in (None, ""):
        return ""
    return f"{label}: {_producer_value(value)}{suffix}."


def render_verification_report(result: VerificationResult) -> str:
    metadata = result.bundle_metadata or {}
    producer = metadata.get("producer") if isinstance(metadata.get("producer"), dict) else {}
    record = result.editorial_record or {}
    responsibility = result.editorial_responsibility or {}
    checks = result.editorial_checks
    counts = Counter(item.status for item in checks)
    declared_title = record.get("item_title") or metadata.get("run_id") or "not recorded"
    integrity = "valid" if result.integrity_valid else "invalid"
    overall = "PASS" if result.valid else "FAIL"
    review_state = record.get("review_state")
    declared_review = next(
        (item for item in result.review_chain if item.get("kind") == "review"),
        None,
    )
    if review_state == "none":
        review_declaration = "<p><strong>No substantive human review is claimed for this item.</strong></p>"
    elif review_state == "partial":
        review_declaration = (
            "<p><strong>The producer declared partial or incomplete review.</strong> "
            f"Not reviewed: {_producer_value(record.get('partial_review_note'))}</p>"
        )
    elif review_state == "complete":
        review_declaration = "<p><strong>The producer declared complete substantive review.</strong></p>"
        if declared_review:
            review_facts = " ".join(
                item
                for item in (
                    _review_fact(
                        "Producer-declared reviewer",
                        declared_review.get("display_name") or declared_review.get("actor_id"),
                    ),
                    _review_fact("Scope", declared_review.get("scope_reviewed")),
                    _review_fact(
                        "Time spent",
                        declared_review.get("review_duration_minutes"),
                        " minutes",
                    ),
                    _review_fact("Basis", declared_review.get("competence_basis")),
                )
                if item
            )
            review_declaration += (
                f"<p>{review_facts}</p>"
                if review_facts
                else "<p>No reviewer details were recorded.</p>"
            )
    else:
        review_declaration = ""

    check_rows = "".join(
        "<tr>"
        f"<td><code>{escape(item.check_id)}</code><br>{escape(item.label)}</td>"
        f"<td>{_status(item.status)}</td>"
        f"<td>{'yes' if item.ran else 'no - unavailable'}</td>"
        f"<td>{escape(item.reason)}</td>"
        "</tr>"
        for item in checks
    ) or '<tr><td colspan="4">No editorial profile was present in this bundle.</td></tr>'

    finding_rows = "".join(
        "<tr>"
        f"<td>{escape(item.severity)}</td>"
        f"<td><code>{escape(item.code)}</code></td>"
        f"<td>{_producer_value(item.message)}</td>"
        "</tr>"
        for item in result.findings
    )
    chain_rows = "".join(
        "<tr>"
        f"<td>{_producer_value(item.get('occurred_at'))}</td>"
        f"<td>{_producer_value(item.get('kind'))}</td>"
        f"<td>{_producer_value(item.get('display_name') or item.get('actor_id'))}<br><code>{_producer_value(item.get('actor_id'))}</code></td>"
        f"<td>{_producer_value(item.get('action'))}</td>"
        f"<td>{_producer_value(item.get('scope_reviewed'))}</td>"
        f"<td>{_producer_value(item.get('review_duration_minutes'))}</td>"
        f"<td>{_producer_value(item.get('competence_basis'))}</td>"
        f"<td><span class=\"binding\">{_producer_value(item.get('binding'))}</span></td>"
        "</tr>"
        for item in result.review_chain
    ) or '<tr><td colspan="8">No editorial review chain was available.</td></tr>'

    satisfied = [item for item in checks if item.status == "satisfied"]
    unresolved = [item for item in checks if item.status != "satisfied"]
    satisfied_items = "".join(
        f"<li><strong>{escape(item.label)}.</strong> {escape(item.reason)}</li>" for item in satisfied
    ) or "<li>No editorial check was satisfied.</li>"
    unresolved_items = "".join(
        f"<li><strong>{escape(item.label)} - {_status(item.status)}.</strong> {escape(item.reason)}</li>"
        for item in unresolved
    ) or "<li>No unresolved editorial checks were reported.</li>"
    limitation_items = "".join(f"<li>{escape(item)}</li>" for item in LIMITATIONS)
    responsibility_text = (
        f"{_producer_value(responsibility.get('person_or_entity'))} "
        f"(<code>{_producer_value(responsibility.get('identifier'))}</code>)"
        if responsibility
        else "No responsible person or entity was recorded."
    )

    if result.valid:
        overall_detail = (
            "No error finding or not_satisfied editorial check was reported. "
            "Unverifiable checks and assurance limitations still remain and are listed below."
        )
    else:
        overall_reasons = []
        if not result.integrity_valid:
            overall_reasons.append("At least one signed-file integrity check failed.")
        if counts["not_satisfied"]:
            overall_reasons.append("At least one editorial record check is not_satisfied.")
        if any(
            item.severity == "error"
            and item.code != "EDITORIAL_CHECKS_NOT_SATISFIED"
            and item.code not in INTEGRITY_FAILURE_CODES
            for item in result.findings
        ):
            overall_reasons.append("At least one declared policy, trust, or record-structure check failed.")
        overall_detail = " ".join(overall_reasons) or "One or more verifier error findings were reported."

    signer_codes = {item.code for item in result.findings}
    fingerprint_text = escape(result.signer_fingerprint or "not established")
    if "UNTRUSTED_SIGNER" in signer_codes:
        signer_detail = "The independent signer check FAILED: the supplied expected fingerprint did not match the signing key in this bundle."
    elif "MALFORMED_EXPECTED_KEY" in signer_codes:
        signer_detail = "The independent signer check FAILED: the supplied expected fingerprint was malformed."
    elif result.signer_pinned:
        signer_detail = "The signing key matched the independently supplied expected fingerprint."
    elif result.signer_fingerprint:
        signer_detail = "The signature matched the key included in the bundle, but signer identity is not independently established."
    else:
        signer_detail = "The signer fingerprint was not established because verification stopped before signature validation completed."

    if result.editorial_profile_state == "absent":
        editorial_summary = "Editorial profile not present"
        editorial_plain = "<p><strong>No editorial profile was evaluated.</strong> This bundle contains no signed Editorial Responsibility Record, so this page makes no editorial findings.</p>"
    elif result.editorial_profile_state == "unavailable":
        editorial_summary = "Editorial profile unavailable"
        editorial_plain = (
            "<p><strong>The editorial profile was not evaluated.</strong> "
            f"{escape(result.editorial_profile_reason or 'The profile could not be used safely.')}</p>"
            f"<h3>Checks left unresolved</h3><ul>{unresolved_items}</ul>"
            "<p class=\"note\">The core signed-file integrity result is reported separately above.</p>"
        )
    else:
        editorial_summary = f"{counts['satisfied']} satisfied, {counts['not_satisfied']} not_satisfied, {counts['unverifiable']} unverifiable"
        editorial_plain = (
            review_declaration
            +
            f"<h3>Satisfied</h3><ul>{satisfied_items}</ul>"
            f"<h3>Open or missing</h3><ul>{unresolved_items}</ul>"
            f"<ul class=\"legend\"><li>{_status('satisfied')}<span>The check ran and the recorded condition was present.</span></li><li>{_status('not_satisfied')}<span>The check ran and the recorded condition was absent or contradicted.</span></li><li>{_status('unverifiable')}<span>The required information was unavailable or could not support a conclusion.</span></li></ul>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pramaan Editorial Responsibility Record</title>
<style>
:root {{--ink:#182028;--muted:#56636e;--line:#cfd6dc;--soft:#e8ecef;--bg:#f4f6f7;--panel:#fff;--accent:#176b5b;--accent-soft:#e7f2ef;--caution:#8a4b08;--caution-bg:#fff7e9;--ok:#14513f;--ok-bg:#e9f3ee;--integrity:#245b78;--integrity-bg:#e8f1f6;--integrity-bad:#713358;--integrity-bad-bg:#f5e9f0;--bad:#75201a;--bad-bg:#f9e9e7;--open:#6a4610;--open-bg:#fbf2e2;--mono:Consolas,monospace;--sans:"Segoe UI",Arial,sans-serif}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 var(--sans)}} main{{width:min(1120px,calc(100vw - 32px));margin:auto;padding:24px 0 56px}} h1,h2,h3,p{{margin-top:0;letter-spacing:0}} h1{{font-size:26px;margin-bottom:4px}} h2{{font-size:19px;margin-bottom:10px}} h3{{font-size:15px}} header{{padding-bottom:16px;border-bottom:1px solid var(--line)}} .eyebrow{{margin-bottom:4px;color:var(--muted);font-size:12px;font-weight:700;text-transform:uppercase}} .declared-title{{margin:0 0 10px;color:var(--muted)}} .meta{{display:flex;flex-wrap:wrap;gap:5px 18px;margin:0;padding:0;list-style:none;color:var(--muted)}} .meta li{{font-size:13px}} .boundary{{margin:20px 0 4px;padding:14px 16px;border:1px solid var(--caution);border-left-width:5px;background:var(--caution-bg)}} .boundary h2{{color:var(--caution);font-size:17px;margin-bottom:5px}} .boundary p:last-child{{margin-bottom:0}} .tablist{{display:inline-flex;margin:22px 0 0;border:1px solid var(--line);border-radius:6px;overflow:hidden;background:var(--panel)}} .tablist button{{border:0;border-right:1px solid var(--line);background:transparent;color:var(--muted);padding:9px 14px;font:600 14px var(--sans);cursor:pointer}} .tablist button:last-child{{border-right:0}} .tablist button[aria-selected=true]{{color:var(--ink);background:var(--accent-soft);box-shadow:inset 0 -3px var(--accent)}} .tablist button:focus-visible{{outline:2px solid var(--accent);outline-offset:-4px}} [hidden]{{display:none!important}} .panel{{padding-top:4px}} #plain-panel{{max-width:74ch}} .panel-title{{margin:22px 0 0;padding-bottom:6px;color:var(--muted);font-size:13px;font-weight:700;text-transform:uppercase;border-bottom:1px solid var(--line)}} section{{padding:22px 0;border-bottom:1px solid var(--line)}} section:last-child{{border-bottom:0}} .verdict{{padding-left:14px;border-left:4px solid var(--accent)}} .verdict.overall-fail{{border-left-color:var(--bad)}} .verdict.integrity-fail{{border-left-color:var(--integrity-bad)}} .verdict strong{{font-size:17px}} .note{{color:var(--muted);font-size:14px}} .status,.binding{{display:inline-block;padding:1px 7px;border:1px solid var(--line);border-radius:3px;font:600 12px/1.55 var(--mono);white-space:nowrap}} .status-satisfied,.status-overall-pass{{color:var(--ok);background:var(--ok-bg)}} .status-valid{{color:var(--integrity);background:var(--integrity-bg)}} .status-not_satisfied,.status-overall-fail{{color:var(--bad);background:var(--bad-bg)}} .status-invalid{{color:var(--integrity-bad);background:var(--integrity-bad-bg)}} .status-unverifiable{{color:var(--open);background:var(--open-bg)}} .kv{{display:grid;grid-template-columns:210px minmax(0,1fr);margin:0;border-top:1px solid var(--line)}} .kv dt,.kv dd{{margin:0;padding:9px 10px;border-bottom:1px solid var(--line)}} .kv dt{{color:var(--muted);font-weight:600}} .kv dd{{background:var(--panel);overflow-wrap:anywhere}} .table-wrap{{overflow-x:auto;border:1px solid var(--line)}} table{{width:100%;min-width:650px;border-collapse:collapse;background:var(--panel);font-size:13px}} th,td{{padding:9px 10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--soft)}} th{{color:var(--muted);font-size:12px;background:#f8fafb}} tr:last-child td{{border-bottom:0}} code{{font:13px var(--mono);overflow-wrap:anywhere}} li{{margin-bottom:8px}} .legend{{padding-left:0;list-style:none}} .legend li{{display:grid;grid-template-columns:150px 1fr;gap:10px;padding:8px 0;border-bottom:1px solid var(--soft)}}
@media(prefers-color-scheme:dark){{:root{{--ink:#edf2f5;--muted:#abb6bf;--line:#46515a;--soft:#364048;--bg:#151a1e;--panel:#1d2429;--accent:#79ccba;--accent-soft:#1e3a35;--caution:#e0ad67;--caution-bg:#2c2416;--ok:#9fdcc6;--ok-bg:#1b3229;--integrity:#acd5ea;--integrity-bg:#203440;--integrity-bad:#efb6d5;--integrity-bad-bg:#382332;--bad:#f2ada4;--bad-bg:#33201e;--open:#f0c78c;--open-bg:#332a17}} th{{background:#222a30}}}}
@media(max-width:760px){{h1{{font-size:22px}}.tablist{{display:flex;width:100%}}.tablist button{{flex:1}}.kv{{grid-template-columns:1fr}}.kv dt{{padding-bottom:0;border-bottom:0}}.kv dd{{padding-top:2px}}.legend li{{grid-template-columns:1fr}}}}
@media print{{@page{{margin:16mm}}body{{background:#fff;color:#000}}main{{width:100%;padding:0}}.tablist{{display:none}}.panel[hidden]{{display:block!important}}#technical-panel{{break-before:page}}.boundary,.status,.binding{{color:#000!important;background:#fff!important;border-color:#000!important}}section,tr,.table-wrap{{break-inside:avoid}}}}
</style>
<noscript><style>.tablist{{display:none}}.panel[hidden]{{display:block!important}}</style></noscript>
</head>
<body><main>
<header><p class="eyebrow">Verification result generated by pramaan verify</p><h1>Editorial Responsibility Record</h1><p class="declared-title">Producer-declared item: {_producer_value(declared_title)}</p>
<ul class="meta"><li>Verified at <strong>{escape(result.verified_at)}</strong></li><li>Verifier <strong>{escape(result.verifier_version)}</strong></li><li>Overall <span class="status status-overall-{overall.lower()}">{overall}</span></li><li>Signed-file integrity {_status(integrity)}</li><li>Editorial review <strong>{escape(editorial_summary)}</strong></li></ul></header>
<aside class="boundary" role="note"><h2>Verification is not truth</h2><p>This page reports what a producer-supplied record contains and whether that record is internally consistent. It does not establish that the content is accurate, that a review was meaningful, or that omitted actions did not occur.</p><p>This result makes no regulatory determination and is not legal advice.</p></aside>
<div class="tablist" role="tablist" aria-label="Level of detail"><button id="plain-tab" role="tab" aria-selected="true" aria-controls="plain-panel" tabindex="0">Plain language</button><button id="technical-tab" role="tab" aria-selected="false" aria-controls="technical-panel" tabindex="-1">Technical detail</button></div>
<div id="plain-panel" class="panel" role="tabpanel" aria-labelledby="plain-tab"><p class="panel-title">Plain language</p>
<section><h2>Overall verification result</h2><div class="verdict {'overall-fail' if not result.valid else ''}"><strong>Overall verification is <span class="status status-overall-{overall.lower()}">{overall}</span>.</strong><p>{escape(overall_detail)}</p></div></section>
<section><h2>Are the signed files intact?</h2><div class="verdict {'integrity-fail' if not result.integrity_valid else ''}"><strong>Signed-file integrity is {_status(integrity)}.</strong><p>{'The files covered by the producer signature match their recorded digests.' if result.integrity_valid else 'One or more signed files failed an integrity check. Review the technical findings before relying on this package.'}</p></div><p class="note">{escape(signer_detail)}</p><p class="note">Computed signer fingerprint: <code>{fingerprint_text}</code></p><p class="note">This is a mechanical conclusion about signed bytes. It is separate from policy completeness and says nothing about whether the publication is accurate or the review was good.</p></section>
<section><h2>Who is named as responsible?</h2><p>{responsibility_text}</p><p class="note">This identity is self-asserted by the producer. Pramaan 0.1 does not independently bind a reviewer-held key to the review.</p></section>
<section><h2>What the editorial checks found</h2>{editorial_plain}</section>
<section><h2>What this page cannot tell you</h2><ul>{limitation_items}</ul></section>
</div>
<div id="technical-panel" class="panel" role="tabpanel" aria-labelledby="technical-tab" hidden><p class="panel-title">Technical detail</p>
<section><h2>Verification metadata</h2><dl class="kv"><dt>Bundle folder <span class="note">(verifier input name; may be producer-chosen)</span></dt><dd><code>{_producer_value(Path(result.bundle).name)}</code></dd><dt>Run ID <span class="note">(producer-declared)</span></dt><dd><code>{_producer_value(metadata.get('run_id'))}</code></dd><dt>Producer <span class="note">(producer-declared)</span></dt><dd>{_producer_value(producer.get('name'))} (<code>{_producer_value(producer.get('id'))}</code>)</dd><dt>Item ID <span class="note">(producer-declared)</span></dt><dd><code>{_producer_value(record.get('item_id'))}</code></dd><dt>Published artifact <span class="note">(producer-declared, digest checked)</span></dt><dd><code>{_producer_value(record.get('published_artifact'))}</code></dd><dt>Content hash <span class="note">(producer-declared, checked when available)</span></dt><dd><code>{_producer_value(record.get('content_hash'))}</code></dd><dt>Review state <span class="note">(producer-declared)</span></dt><dd><code>{_producer_value(record.get('review_state'))}</code></dd><dt>Partial review note <span class="note">(producer-declared)</span></dt><dd>{_producer_value(record.get('partial_review_note'))}</dd><dt>Disclosure state <span class="note">(producer-declared)</span></dt><dd><code>{_producer_value(record.get('disclosure_state'))}</code></dd><dt>Profile state</dt><dd><code>{escape(result.editorial_profile_state)}</code></dd><dt>Check set</dt><dd><code>{_value(result.editorial_check_set_version)}</code></dd><dt>Signer fingerprint</dt><dd><code>{fingerprint_text}</code></dd><dt>Signer pinned</dt><dd><code>{str(result.signer_pinned).lower()}</code></dd></dl></section>
<section><h2>Checks performed</h2><div class="table-wrap"><table><thead><tr><th>Check</th><th>Status</th><th>Ran?</th><th>Reason</th></tr></thead><tbody>{check_rows}</tbody></table></div></section>
<section><h2>Review chain</h2><p class="note">Times, scope, duration, and competence basis are producer-supplied and are not independently verified.</p><div class="table-wrap"><table><thead><tr><th>Time</th><th>Kind</th><th>Actor</th><th>Action</th><th>Scope</th><th>Minutes</th><th>Competence basis</th><th>Identity</th></tr></thead><tbody>{chain_rows}</tbody></table></div></section>
<section><h2>Core verifier findings</h2><p class="note">Messages may quote producer-declared identifiers or file names; selected high-risk assurance phrases are filtered, and producer-controlled values remain labelled.</p><div class="table-wrap"><table><thead><tr><th>Severity</th><th>Code</th><th>Message</th></tr></thead><tbody>{finding_rows}</tbody></table></div></section>
<section><h2>Assurance boundary</h2><ul>{limitation_items}</ul></section>
</div>
<script>(()=>{{const tabs=[...document.querySelectorAll('[role=tab]')];const panels=tabs.map(t=>document.getElementById(t.getAttribute('aria-controls')));function select(i){{tabs.forEach((t,n)=>{{const on=n===i;t.setAttribute('aria-selected',String(on));t.tabIndex=on?0:-1;panels[n].hidden=!on}});tabs[i].focus()}}tabs.forEach((t,i)=>{{t.addEventListener('click',()=>select(i));t.addEventListener('keydown',e=>{{let n=i;if(e.key==='ArrowRight')n=(i+1)%tabs.length;else if(e.key==='ArrowLeft')n=(i-1+tabs.length)%tabs.length;else if(e.key==='Home')n=0;else if(e.key==='End')n=tabs.length-1;else return;e.preventDefault();select(n)}})}})}})();</script>
</main></body></html>"""


def _outside_bundle(result: VerificationResult, path: Path) -> Path:
    resolved = path.resolve()
    bundle = Path(result.bundle).resolve()
    if resolved.is_relative_to(bundle):
        raise ValueError("verification outputs must be written outside the signed bundle")
    return resolved


def write_verification_outputs(
    result: VerificationResult,
    html_path: Path | None = None,
    json_path: Path | None = None,
) -> None:
    if html_path is None and json_path is None:
        raise ValueError("at least one verification output path is required")
    if html_path is not None:
        resolved_html = _outside_bundle(result, html_path)
        resolved_html.parent.mkdir(parents=True, exist_ok=True)
        resolved_html.write_bytes(render_verification_report(result).encode("utf-8"))
    if json_path is not None:
        resolved_json = _outside_bundle(result, json_path)
        resolved_json.parent.mkdir(parents=True, exist_ok=True)
        resolved_json.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
