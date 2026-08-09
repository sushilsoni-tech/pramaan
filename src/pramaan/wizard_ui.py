import json


def render_wizard_html(session_prefix: str) -> str:
    prefix = json.dumps(session_prefix)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Create a Pramaan record</title>
<style>
:root {{--ink:#182028;--muted:#58656f;--line:#cbd3d9;--soft:#eef1f3;--panel:#fff;--bg:#f5f7f8;--accent:#176b5b;--accent-soft:#e6f1ee;--bad:#8a241d;--bad-bg:#faeae8;--warn:#7b4b0b;--warn-bg:#fff7e6;--ok:#14513f;--ok-bg:#e7f2ed;--mono:Consolas,monospace;--sans:"Segoe UI",Arial,sans-serif}}
*{{box-sizing:border-box}} html{{background:var(--bg)}} body{{margin:0;color:var(--ink);font:15px/1.55 var(--sans);letter-spacing:0}} button,input,select,textarea{{font:inherit;letter-spacing:0}} button{{min-height:44px;cursor:pointer}} main{{width:min(680px,calc(100vw - 32px));margin:28px auto 96px}} .shell{{background:var(--panel);border:1px solid var(--line);border-radius:6px}} header{{position:sticky;top:0;z-index:3;padding:18px 22px 14px;background:var(--panel);border-bottom:1px solid var(--line)}} .header-row{{display:flex;align-items:baseline;justify-content:space-between;gap:16px}} h1{{margin:0;font-size:20px}} .step-count{{color:var(--muted);font-size:13px;font-weight:600}} progress{{display:block;width:100%;height:6px;margin-top:12px;accent-color:var(--accent)}} .step{{padding:24px 22px 8px}} h2{{font-size:20px;margin:0 0 18px}} h3{{font-size:15px;margin:24px 0 10px}} p{{margin:0 0 14px}} .intro{{color:var(--muted)}} .field{{margin:0 0 19px}} label,.group-label{{display:block;margin-bottom:6px;font-weight:650}} input[type=text],input[type=url],input[type=datetime-local],input[type=number],select,textarea{{width:100%;min-height:44px;padding:9px 10px;color:var(--ink);background:#fff;border:1px solid #9eabb4;border-radius:4px}} textarea{{min-height:88px;resize:vertical}} input:focus,select:focus,textarea:focus,button:focus-visible,a:focus-visible{{outline:2px solid #0b5f50;outline-offset:2px}} input[aria-invalid=true],select[aria-invalid=true],textarea[aria-invalid=true]{{border-color:var(--bad)}} .hint,.privacy{{margin:5px 0 0;color:var(--muted);font-size:13px}} .error{{display:none;margin:5px 0 0;color:var(--bad);font-size:13px;font-weight:600}} .error.show{{display:block}} .choice-list{{display:grid;gap:8px}} .choice{{display:flex;gap:9px;align-items:flex-start;padding:10px;border:1px solid var(--line);border-radius:4px}} .choice input{{margin-top:4px;flex:0 0 auto}} .choice label{{margin:0;font-weight:500}} .two{{display:grid;grid-template-columns:1fr 150px;gap:10px}} .file-box{{padding:16px;border:1px dashed #83919a;background:#fafbfb;border-radius:4px}} .file-facts{{display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}} .file-facts.show{{display:block}} code{{font:13px var(--mono);overflow-wrap:anywhere}} .actions{{display:flex;justify-content:space-between;gap:12px;padding:18px 22px;border-top:1px solid var(--line)}} .actions .right{{display:flex;gap:10px;margin-left:auto}} .button{{display:inline-flex;align-items:center;justify-content:center;padding:9px 16px;border:1px solid #89969f;border-radius:4px;background:#fff;color:var(--ink);text-decoration:none;font-weight:650}} .button.primary{{border-color:var(--accent);background:var(--accent);color:#fff}} .button:disabled{{cursor:not-allowed;opacity:.55}} .boundary{{margin:20px 0;padding:14px;border-left:4px solid var(--warn);background:var(--warn-bg)}} .boundary strong{{display:block;margin-bottom:5px}} .truth{{position:fixed;left:0;right:0;bottom:0;z-index:5;padding:10px 16px;text-align:center;color:#37434c;background:#fff;border-top:1px solid var(--line);font-size:13px}} .truth strong{{color:var(--warn)}} .summary{{margin:0}} .summary-row{{display:grid;grid-template-columns:145px 1fr auto;gap:10px;padding:10px 0;border-bottom:1px solid var(--soft)}} .summary-row dt,.summary-row dd{{margin:0}} .summary-row dt{{color:var(--muted);font-weight:650}} .edit{{min-height:0;padding:0;border:0;background:none;color:var(--accent);font-weight:650}} .working{{padding:18px 22px;border-top:1px solid var(--line)}} .working li{{margin:7px 0}} .result{{padding:28px 22px}} .result h2{{margin-bottom:8px}} .status{{display:inline-block;padding:2px 7px;border:1px solid currentColor;border-radius:3px;font:650 12px var(--mono)}} .status.ok{{color:var(--ok);background:var(--ok-bg)}} .status.open{{color:var(--bad);background:var(--bad-bg)}} .facts{{display:grid;grid-template-columns:130px 1fr;margin:20px 0;border-top:1px solid var(--line)}} .facts dt,.facts dd{{margin:0;padding:9px;border-bottom:1px solid var(--line)}} .facts dt{{color:var(--muted);font-weight:650}} .result-actions{{display:grid;grid-template-columns:1fr 1fr;gap:10px}} .local-note{{margin-top:18px;color:var(--muted);font-size:13px}} [hidden]{{display:none!important}} .soft-warning{{padding:10px;border:1px solid #d6b26e;background:var(--warn-bg);font-size:13px}}
@media(max-width:520px){{main{{width:100%;margin:0 0 88px}}.shell{{border-width:0 0 1px;border-radius:0}}header{{padding:14px 16px}}.header-row{{display:block}}.step-count{{display:block;margin-top:2px}}.step{{padding:20px 16px 6px}}.actions{{padding:15px 16px}}.two{{grid-template-columns:1fr}}.summary-row{{grid-template-columns:1fr auto}}.summary-row dd{{grid-column:1 / -1;grid-row:2}}.result-actions{{grid-template-columns:1fr}}.facts{{grid-template-columns:1fr}}.facts dt{{padding-bottom:0;border-bottom:0}}.facts dd{{padding-top:2px}}}}
@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important}}}}
</style>
</head>
<body>
<main>
<div class="shell" id="wizard">
<header><div class="header-row"><h1>Create record</h1><span class="step-count" id="step-count">Step 1 of 6</span></div><progress id="progress" max="6" value="1">1 of 6</progress></header>
<form id="record-form" novalidate>
<section class="step" data-step="1">
<h2>Choose the publication file</h2><p class="intro">Use the final version that was or will be published.</p>
<div class="field file-box" data-field="publication_file"><label for="publication-file">Publication file</label><input id="publication-file" type="file" required><p class="hint">Maximum 10 MB. The file stays on this computer.</p><p class="error" id="publication-file-error"></p><div class="file-facts" id="file-facts"><strong id="file-name"></strong><p><span id="file-size"></span> &middot; SHA-256 <code id="file-hash-short"></code></p></div></div>
</section>
<section class="step" data-step="2" hidden>
<h2>Identify the item</h2>
<div class="field"><label for="title">Title</label><input id="title" name="title" type="text" maxlength="200" required><p class="error"></p></div>
<div class="field"><label for="publication-context">Where this was published</label><input id="publication-context" name="publication_context" type="text" maxlength="200" required><p class="hint">Newsletter name, site, client publication, or outlet.</p><p class="error"></p></div>
</section>
<section class="step" data-step="3" hidden>
<h2>Record the AI contribution</h2>
<div class="field"><label for="ai-system">AI system used</label><input id="ai-system" name="ai_system" type="text" maxlength="120" list="ai-systems" required><datalist id="ai-systems"><option value="ChatGPT"><option value="Claude"><option value="Gemini"><option value="Microsoft Copilot"><option value="Perplexity"></datalist><p class="error"></p></div>
<div class="field"><label for="ai-model">Version or model identifier <span class="hint">(optional)</span></label><input id="ai-model" name="ai_model" type="text" maxlength="120"><p class="error"></p></div>
<div class="field"><label for="generation-at">Generation finished</label><div class="two"><input id="generation-at" name="generation_at" type="datetime-local" required><button class="button now" type="button" data-target="generation-at">Use current time</button></div><p class="hint time-zone"></p><p class="error"></p></div>
<fieldset class="field"><legend class="group-label">What the AI produced</legend><div class="choice-list">
<div class="choice"><input id="contribution-draft" name="ai_contribution" type="radio" value="Full first draft" required><label for="contribution-draft">Full first draft</label></div>
<div class="choice"><input id="contribution-sections" name="ai_contribution" type="radio" value="Sections or passages"><label for="contribution-sections">Sections or passages</label></div>
<div class="choice"><input id="contribution-edits" name="ai_contribution" type="radio" value="Edits to existing text"><label for="contribution-edits">Edits to existing text</label></div>
<div class="choice"><input id="contribution-research" name="ai_contribution" type="radio" value="Research or background only"><label for="contribution-research">Research or background only</label></div>
</div><p class="error"></p></fieldset>
</section>
<section class="step" data-step="4" hidden>
<h2>Describe the human review</h2>
<fieldset class="field"><legend class="group-label">Did a person substantively review this before publication?</legend><div class="choice-list">
<div class="choice"><input id="review-complete" name="review_state" type="radio" value="complete" required><label for="review-complete"><strong>Yes, complete substantive review</strong><br><span class="hint">A person considered the content, not only spelling or formatting.</span></label></div>
<div class="choice"><input id="review-none" name="review_state" type="radio" value="none"><label for="review-none"><strong>No</strong><br><span class="hint">The record will say no substantive human review is claimed.</span></label></div>
<div class="choice"><input id="review-partial" name="review_state" type="radio" value="partial"><label for="review-partial"><strong>Partial or incomplete review</strong><br><span class="hint">This will not be recorded as complete substantive review.</span></label></div>
</div><p class="error"></p></fieldset>
<div id="review-complete-fields" hidden aria-live="polite">
<div class="field"><label for="reviewer-name">Reviewer name</label><input id="reviewer-name" name="reviewer_name" type="text" maxlength="160" required><p class="error"></p></div>
<div class="field"><label for="reviewer-role">Reviewer role or affiliation <span class="hint">(optional)</span></label><input id="reviewer-role" name="reviewer_role" type="text" maxlength="120"><p class="error"></p></div>
<div class="field"><label for="review-at">Review finished</label><div class="two"><input id="review-at" name="review_at" type="datetime-local" required><button class="button now" type="button" data-target="review-at">Use current time</button></div><p class="error"></p></div>
<div class="field"><label for="review-duration">Time spent reviewing</label><div class="two"><input id="review-duration" name="review_duration" type="number" min="1" max="10080" inputmode="numeric" required><select id="review-duration-unit" aria-label="Review duration unit"><option value="minutes">minutes</option><option value="hours">hours</option></select></div><p class="error"></p></div>
<fieldset class="field" id="review-scopes"><legend class="group-label">What was reviewed?</legend><div class="choice-list">
<div class="choice"><input id="scope-facts" type="checkbox" value="facts_claims"><label for="scope-facts">Facts and claims</label></div>
<div class="choice"><input id="scope-sources" type="checkbox" value="sources_citations"><label for="scope-sources">Sources and citations</label></div>
<div class="choice"><input id="scope-quotes" type="checkbox" value="quotes_attributions"><label for="scope-quotes">Quotes and attributions</label></div>
<div class="choice"><input id="scope-numbers" type="checkbox" value="numbers_calculations"><label for="scope-numbers">Numbers and calculations</label></div>
<div class="choice"><input id="scope-sensitive" type="checkbox" value="legal_contractual"><label for="scope-sensitive">Legal or contractual sensitivity</label></div>
<div class="choice"><input id="scope-tone" type="checkbox" value="tone_framing"><label for="scope-tone">Tone and framing</label></div>
<div class="choice"><input id="scope-whole" type="checkbox" value="whole_item"><label for="scope-whole">Whole item line by line</label></div>
</div><p class="error"></p></fieldset>
<div class="field"><label for="competence-basis">Basis for reviewing this</label><textarea id="competence-basis" name="competence_basis" minlength="10" maxlength="300" required></textarea><p class="hint">Example: I have covered municipal budgets for six years.</p><p class="error"></p></div>
<fieldset class="field"><legend class="group-label">Were changes made after review?</legend><div class="choice-list"><div class="choice"><input id="changes-yes" name="changes_made" type="radio" value="yes" required><label for="changes-yes">Yes</label></div><div class="choice"><input id="changes-no" name="changes_made" type="radio" value="no"><label for="changes-no">No</label></div></div><p class="error"></p></fieldset>
<div class="field" id="change-summary-field" hidden><label for="change-summary">What changed?</label><textarea id="change-summary" name="change_summary" minlength="10" maxlength="500"></textarea><p class="error"></p></div>
</div>
<div id="review-partial-fields" hidden aria-live="polite"><div class="field"><label for="partial-review-note">What was not reviewed?</label><textarea id="partial-review-note" name="partial_review_note" maxlength="200" required></textarea><p class="error"></p></div></div>
</section>
<section class="step" data-step="5" hidden>
<h2>Name responsibility and publication</h2>
<div class="field"><label for="responsibility-name">Person or entity accepting editorial responsibility</label><input id="responsibility-name" name="responsibility_name" type="text" maxlength="180" required><p class="hint">This is producer-declared and will appear in the signed record.</p><p class="error"></p></div>
<div class="field"><label for="responsibility-role">Relationship to the item</label><select id="responsibility-role" name="responsibility_role" required><option value="">Select one</option><option value="author">Author</option><option value="editor">Editor</option><option value="publisher">Publisher</option><option value="organization">Organization</option><option value="other">Other</option></select><p class="error"></p></div>
<div class="field"><label for="correction-contact">Contact for corrections <span class="hint">(optional)</span></label><input id="correction-contact" name="correction_contact" type="text" maxlength="200"><p class="privacy">This will be inside the signed bundle if you share it.</p><p class="error"></p></div>
<div class="field"><label for="publication-at">Published</label><div class="two"><input id="publication-at" name="publication_at" type="datetime-local"><button class="button now" type="button" data-target="publication-at">Use current time</button></div><p class="error"></p></div>
<fieldset class="field"><legend class="group-label">Disclosure to readers</legend><div class="choice-list">
<div class="choice"><input id="disclosure-item" name="disclosure_state" type="radio" value="item" required><label for="disclosure-item">Disclosed in the published item</label></div>
<div class="choice"><input id="disclosure-elsewhere" name="disclosure_state" type="radio" value="elsewhere"><label for="disclosure-elsewhere">Disclosed elsewhere</label></div>
<div class="choice"><input id="disclosure-no" name="disclosure_state" type="radio" value="not_disclosed"><label for="disclosure-no">Not disclosed</label></div>
<div class="choice"><input id="disclosure-pending" name="disclosure_state" type="radio" value="not_published"><label for="disclosure-pending">Not yet published; disclosure not decided</label></div>
</div><p class="error"></p></fieldset>
</section>
<section class="step" data-step="6" hidden>
<h2>Review and create</h2><dl class="summary" id="summary"></dl>
<div class="boundary"><strong>What this record does and does not do</strong><p>This record stores facts you have declared, sealed so they cannot be changed later without detection.</p><p>Pramaan verifies that the file, the times, and your statements are exactly what you entered, and that no one has altered them since. It does not verify that your statements are accurate. It does not check the item for accuracy, and it does not certify compliance with any law, regulation, or platform policy.</p><p>You are responsible for what you declare here.</p></div>
<div class="field"><div class="choice"><input id="declaration-confirmed" type="checkbox"><label for="declaration-confirmed">I confirm these statements are accurate to the best of my knowledge.</label></div><p class="error"></p></div>
</section>
<div class="actions" id="actions"><button class="button" id="back" type="button" hidden>Back</button><div class="right"><button class="button primary" id="continue" type="button">Continue</button><button class="button primary" id="create" type="submit" hidden>Create signed record</button></div></div>
<div class="working" id="working" hidden aria-live="polite"><strong>Creating the record on this computer</strong><ol><li>Hashing file</li><li>Building signed bundle</li><li>Verifying signature and checks</li><li>Preparing report and download</li></ol></div>
</form>
<section class="result" id="result" hidden aria-live="polite"><h2 id="result-title"></h2><p id="result-status"></p><dl class="facts"><dt>Title</dt><dd id="result-item-title"></dd><dt>Stored file</dt><dd><code id="result-file-name"></code></dd><dt>File hash</dt><dd><code id="result-hash"></code></dd><dt>Record ID</dt><dd><code id="result-id"></code></dd><dt>Signer fingerprint</dt><dd><code id="result-fingerprint"></code></dd><dt>Verified at</dt><dd id="result-created"></dd></dl><div class="result-actions"><a class="button primary" id="report-link" target="_blank" rel="noopener">Open local report</a><a class="button primary" id="download-link">Download signed bundle (.zip)</a></div><p class="local-note">The report is your local copy. The download contains the signed bundle only. Ask recipients to run Pramaan verification on the bundle, and send the signer fingerprint separately when they need to confirm the record came from the same signing identity.</p><button class="edit" id="another" type="button">Create another record</button></section>
</div>
</main>
<footer class="truth"><strong>You are recording what you did.</strong> Pramaan seals it; it does not check whether it is true.</footer>
<script>
(()=>{{
const PREFIX={prefix};
const TOKEN=PREFIX.split('/').pop();
const form=document.getElementById('record-form');
const steps=[...document.querySelectorAll('.step')];
const count=document.getElementById('step-count');
const progress=document.getElementById('progress');
const back=document.getElementById('back');
const next=document.getElementById('continue');
const create=document.getElementById('create');
let current=1,file=null,fileHash='';
const zone=Intl.DateTimeFormat().resolvedOptions().timeZone||'local time';
document.querySelectorAll('.time-zone').forEach(e=>e.textContent=`Times recorded in ${{zone}}.`);
function localNow(){{const d=new Date();d.setMinutes(d.getMinutes()-d.getTimezoneOffset());return d.toISOString().slice(0,16)}}
document.querySelectorAll('.now').forEach(b=>b.addEventListener('click',()=>{{document.getElementById(b.dataset.target).value=localNow()}}));
function fieldError(el,message){{const box=el.closest('.field,fieldset');const out=box?.querySelector('.error');if(out){{out.textContent=message;out.classList.toggle('show',!!message)}}if('setAttribute' in el)el.setAttribute('aria-invalid',message?'true':'false')}}
function clearErrors(step){{step.querySelectorAll('.error').forEach(e=>{{e.textContent='';e.classList.remove('show')}});step.querySelectorAll('[aria-invalid]').forEach(e=>e.setAttribute('aria-invalid','false'))}}
function radio(name){{return document.querySelector(`input[name="${{name}}"]:checked`)?.value||''}}
function value(name){{return form.elements[name]?.value?.trim()||''}}
function validateStep(number){{
 const step=steps[number-1];clearErrors(step);let first=null;
 for(const el of step.querySelectorAll('input[required],select[required],textarea[required]')){{
  if(el.disabled)continue;
  if(el.type==='radio'){{if(!radio(el.name)){{fieldError(el,`${{el.closest('fieldset')?.querySelector('legend')?.textContent||'This choice'}} is required.`);first=first||el}}}}
  else if(!el.value.trim()){{fieldError(el,`${{el.labels?.[0]?.textContent||'This field'}} is required.`);first=first||el}}
 }}
 if(number===1&&!file){{fieldError(document.getElementById('publication-file'),'Publication file is required.');first=document.getElementById('publication-file')}}
 if(number===4&&radio('review_state')==='complete'){{
  const scopes=[...document.querySelectorAll('#review-scopes input:checked')];
  const contentScopes=new Set(['facts_claims','sources_citations','quotes_attributions','numbers_calculations','legal_contractual','whole_item']);
  if(!scopes.length||!scopes.some(scope=>contentScopes.has(scope.value))){{fieldError(document.getElementById('review-scopes'),'Select at least one content review scope; tone and framing alone is not substantive review.');first=first||document.getElementById('scope-facts')}}
  if(!radio('changes_made')){{fieldError(document.getElementById('changes-yes'),'Whether changes were made is required.');first=first||document.getElementById('changes-yes')}}
  if(value('competence_basis').length<10){{fieldError(document.getElementById('competence-basis'),'Basis for reviewing must be at least 10 characters.');first=first||document.getElementById('competence-basis')}}
  if(radio('changes_made')==='yes'&&value('change_summary').length<10){{fieldError(document.getElementById('change-summary'),'What changed must be at least 10 characters.');first=first||document.getElementById('change-summary')}}
  const generation=new Date(value('generation_at')),review=new Date(value('review_at'));
  if(review<generation){{fieldError(document.getElementById('review-at'),'Review finished is before the AI finished generating. One of these times is wrong.');first=first||document.getElementById('review-at')}}
  const duration=Number(value('review_duration')||0);
  const durationMinutes=document.getElementById('review-duration-unit').value==='hours'?duration*60:duration;
  if(durationMinutes>((review-generation)/60000)+1){{fieldError(document.getElementById('review-duration'),'Review time spent is longer than the time between AI generation and review.');first=first||document.getElementById('review-duration')}}
 }}
 if(number===4&&radio('review_state')==='partial'&&!value('partial_review_note')){{fieldError(document.getElementById('partial-review-note'),'What was not reviewed is required.');first=first||document.getElementById('partial-review-note')}}
if(number===5){{
  const notPublished=radio('disclosure_state')==='not_published';
  if(!notPublished&&!value('publication_at')){{fieldError(document.getElementById('publication-at'),'Published date is required unless the item is not yet published.');first=first||document.getElementById('publication-at')}}
  if(!notPublished&&value('publication_at')){{
   const generation=new Date(value('generation_at')),published=new Date(value('publication_at'));
   const review=radio('review_state')==='complete'?new Date(value('review_at')):null;
   if(published>new Date(Date.now()+60000)){{fieldError(document.getElementById('publication-at'),'Published cannot be in the future. Choose not yet published if this has not gone out.');first=first||document.getElementById('publication-at')}}
   if(published<generation){{fieldError(document.getElementById('publication-at'),'Published is before the AI finished generating. One of these times is wrong.');first=first||document.getElementById('publication-at')}}
   if(review&&published<review){{fieldError(document.getElementById('publication-at'),'Published is before the review finished. One of these times is wrong.');first=first||document.getElementById('publication-at')}}
  }}
 }}
 if(first){{first.focus();return false}}return true
}}
function showStep(n){{current=n;steps.forEach((s,i)=>s.hidden=i!==n-1);count.textContent=`Step ${{n}} of 6`;progress.value=n;progress.setAttribute('value',String(n));progress.textContent=`${{n}} of 6`;progress.setAttribute('aria-label',`Step ${{n}} of 6`);back.hidden=n===1;next.hidden=n===6;create.hidden=n!==6;create.disabled=n!==6;if(n===6)renderSummary();scrollTo({{top:0,behavior:'smooth'}})}}
next.addEventListener('click',()=>{{if(validateStep(current))showStep(current+1)}});back.addEventListener('click',()=>showStep(current-1));
document.querySelectorAll('input[name=review_state]').forEach(el=>el.addEventListener('change',()=>{{const complete=radio('review_state')==='complete',partial=radio('review_state')==='partial';document.getElementById('review-complete-fields').hidden=!complete;document.getElementById('review-partial-fields').hidden=!partial;document.querySelectorAll('#review-complete-fields input,#review-complete-fields textarea').forEach(x=>x.disabled=!complete);document.querySelectorAll('#review-partial-fields textarea').forEach(x=>x.disabled=!partial)}}));
document.querySelectorAll('input[name=changes_made]').forEach(el=>el.addEventListener('change',()=>{{document.getElementById('change-summary-field').hidden=radio('changes_made')!=='yes'}}));
function updatePublicationRequirement(){{const pending=radio('disclosure_state')==='not_published';const input=document.getElementById('publication-at');const nowButton=document.querySelector('[data-target="publication-at"]');input.disabled=pending;input.required=!pending;if(nowButton)nowButton.disabled=pending;if(pending)input.value=''}}
document.querySelectorAll('input[name=disclosure_state]').forEach(el=>el.addEventListener('change',updatePublicationRequirement));
async function hashFile(selected){{const digest=await crypto.subtle.digest('SHA-256',await selected.arrayBuffer());return [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('')}}
document.getElementById('publication-file').addEventListener('change',async e=>{{file=e.target.files[0]||null;fileHash='';document.getElementById('file-facts').classList.remove('show');if(!file)return;if(file.size>10*1024*1024){{file=null;fieldError(e.target,'Publication file must be 10 MB or smaller.');return}}try{{fileHash=await hashFile(file)}}catch(error){{file=null;fieldError(e.target,'The file could not be read. Re-select it to continue.');return}}document.getElementById('file-name').textContent=file.name;document.getElementById('file-size').textContent=`${{(file.size/1024).toFixed(1)}} KB`;document.getElementById('file-hash-short').textContent=fileHash.slice(0,16)+'...';document.getElementById('file-facts').classList.add('show');fieldError(e.target,'')}});
function dateIso(name){{return new Date(value(name)).toISOString()}}
function safe(text){{return String(text).replace(/[&<>"']/g,ch=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]))}}
function summaryRow(label,text,step){{return `<div class="summary-row"><dt>${{safe(label)}}</dt><dd>${{safe(text)}}</dd><button class="edit" type="button" data-edit="${{step}}">Edit</button></div>`}}
function renderSummary(){{const review={{complete:'Complete substantive review',none:'No substantive human review claimed',partial:'Partial or incomplete review'}}[radio('review_state')];document.getElementById('summary').innerHTML=summaryRow('File',file?.name||'',1)+summaryRow('Item',value('title')+' / '+value('publication_context'),2)+summaryRow('AI contribution',value('ai_system')+' / '+radio('ai_contribution'),3)+summaryRow('Human review',review,4)+summaryRow('Responsibility',value('responsibility_name')+' / '+value('responsibility_role'),5);document.querySelectorAll('[data-edit]').forEach(b=>b.addEventListener('click',()=>showStep(Number(b.dataset.edit))))}}
async function fileBase64(selected){{const bytes=new Uint8Array(await selected.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(binary)}}
function payload(encoded){{const reviewComplete=radio('review_state')==='complete';const duration=Number(value('review_duration')||0);const changesMade=reviewComplete&&radio('changes_made')==='yes';return{{file_name:file.name,file_base64:encoded,file_hash:fileHash,title:value('title'),publication_context:value('publication_context'),ai_system:value('ai_system'),ai_model:value('ai_model'),ai_contribution:radio('ai_contribution'),generation_at:dateIso('generation_at'),review_state:radio('review_state'),reviewer_name:reviewComplete?value('reviewer_name'):'',reviewer_role:reviewComplete?value('reviewer_role'):'',review_at:reviewComplete?dateIso('review_at'):'',review_duration_minutes:reviewComplete?(document.getElementById('review-duration-unit').value==='hours'?duration*60:duration):0,review_scopes:reviewComplete?[...document.querySelectorAll('#review-scopes input:checked')].map(x=>x.value):[],competence_basis:reviewComplete?value('competence_basis'):'',changes_made:changesMade,change_summary:changesMade?value('change_summary'):'',partial_review_note:radio('review_state')==='partial'?value('partial_review_note'):'',responsibility_name:value('responsibility_name'),responsibility_role:value('responsibility_role'),correction_contact:value('correction_contact'),publication_at:value('publication_at')?dateIso('publication_at'):'',disclosure_state:radio('disclosure_state'),declaration_confirmed:document.getElementById('declaration-confirmed').checked}}}}
form.addEventListener('submit',async e=>{{e.preventDefault();if(current!==6||create.hidden||create.disabled)return;if(!document.getElementById('declaration-confirmed').checked){{fieldError(document.getElementById('declaration-confirmed'),'Confirmation is required before creating the record.');return}}let currentHash='';try{{currentHash=await hashFile(file)}}catch(error){{showStep(1);fieldError(document.getElementById('publication-file'),'The file could not be read. Re-select it to continue.');return}}if(currentHash!==fileHash){{showStep(1);fieldError(document.getElementById('publication-file'),'The file changed since you selected it. Re-select it to continue.');return}}document.getElementById('actions').hidden=true;document.getElementById('working').hidden=false;try{{const response=await fetch(PREFIX+'/create',{{method:'POST',headers:{{'Content-Type':'application/json','X-Pramaan-Session':TOKEN}},body:JSON.stringify(payload(await fileBase64(file)))}});const data=await response.json();if(!response.ok)throw new Error(data.error||'Record creation failed');showResult(data)}}catch(error){{document.getElementById('working').innerHTML=`<div class="boundary"><strong>The record could not be created</strong><p>${{String(error.message).replace(/[<>&]/g,'')}}</p></div><button class="button" type="button" id="retry">Return to review</button>`;document.getElementById('retry').addEventListener('click',()=>{{document.getElementById('working').hidden=true;document.getElementById('actions').hidden=false}})}}}});
function showResult(data){{form.hidden=true;document.getElementById('result').hidden=false;document.getElementById('result-title').textContent=data.valid?'Record created and verified':'Record created with findings';document.getElementById('result-status').innerHTML=data.valid?'<span class="status ok">VERIFIED</span> Signed files are intact and no required editorial check failed.':'<span class="status open">REVIEW NEEDED</span> Signed files are intact, but one or more editorial checks were not satisfied.';document.getElementById('result-item-title').textContent=data.title;document.getElementById('result-file-name').textContent=data.stored_file_name;document.getElementById('result-hash').textContent=data.file_hash;document.getElementById('result-id').textContent=data.record_id;document.getElementById('result-fingerprint').textContent=data.signer_fingerprint||'not established';document.getElementById('result-created').textContent=new Date(data.created_at).toLocaleString();document.getElementById('report-link').href=data.report_url;document.getElementById('download-link').href=data.download_url}}
document.getElementById('another').addEventListener('click',()=>location.reload());
document.querySelectorAll('#review-complete-fields input,#review-complete-fields textarea,#review-partial-fields textarea').forEach(x=>x.disabled=true);
create.disabled=true;
updatePublicationRequirement();
showStep(1);
}})();
</script>
</body>
</html>"""
