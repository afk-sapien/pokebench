"""A single local leaderboard with category scores and searchable task evidence."""
import json


def page(data):
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return TEMPLATE.replace('__DATA__', payload)


TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PokeBench | Model comparison</title>
<style>
:root {color-scheme:light} * {box-sizing:border-box} body {margin:0} body {background:#f6f5f1} body {color:#202722} body {font-family:Inter,ui-sans-serif,system-ui,sans-serif} body {line-height:1.5}
a {color:#305c4a} a {text-underline-offset:3px} button,input {font:inherit} button {cursor:pointer}
header {border-bottom:1px solid #dcded5} header {background:#fffefa} .wrap {max-width:1420px} .wrap {margin:auto} .wrap {padding:28px 36px}
.top {display:flex} .top {align-items:center} .top {justify-content:space-between} .top {gap:20px} nav {display:flex} nav {gap:24px} nav {flex-wrap:wrap} nav a {font-size:14px}
.brand {font-size:23px} .brand {font-weight:850} .brand {letter-spacing:-1px} .brand {color:#202722} .brand {text-decoration:none}
.ball {display:inline-block} .ball {width:20px} .ball {height:20px} .ball {border:3px solid #202722} .ball {border-radius:50%} .ball {background:linear-gradient(#d3543f 45%,#202722 45%,#202722 60%,#fffefa 60%)} .ball {margin-right:8px}
.kicker {font-size:12px} .kicker {font-weight:750} .kicker {letter-spacing:1.5px} .kicker {text-transform:uppercase} .kicker {color:#697269}
h1 {font-size:clamp(32px,4vw,52px)} h1 {line-height:1.1} h1 {letter-spacing:-2px} h1 {margin:12px 0 18px}
h2 {font-size:25px} h2 {letter-spacing:-.6px} h2 {margin:0 0 10px} h3 {font-size:18px}
.lede {max-width:800px} .lede {font-size:18px} .lede {color:#616b62} .hero {padding-top:42px} .muted {color:#697269} .small {font-size:13px}
.stats {display:grid} .stats {grid-template-columns:repeat(4,1fr)} .stats {gap:18px} .stats {margin:30px 0}
.stat {padding:18px 20px} .stat {background:#ebece4} .stat {border-radius:8px} .stat strong {display:block} .stat strong {font-size:27px} .stat span {font-size:13px} .stat span {color:#626d62}
.panel {background:#fffefa} .panel {border:1px solid #dddfd5} .panel {border-radius:10px} .panel {overflow:hidden} .section {margin-top:38px} .scroll {overflow:auto}
table {width:100%} table {border-collapse:collapse} th,td {padding:14px 16px} th,td {text-align:right} th,td {white-space:nowrap} th:first-child,td:first-child {text-align:left} thead th {font-size:11px} thead th {text-transform:uppercase} thead th {letter-spacing:.8px} thead th {color:#687568} thead {background:#f0f1e9} tbody tr {border-top:1px solid #e7e8df} tbody tr:hover {background:#f8f9f3}
.rank {color:#879087} .rank {font-size:12px} .rank {margin-right:12px} .model {font-weight:750} .model-id {font-size:11px} .model-id {font-weight:400} .model-id {color:#7c857b} .model-id {display:block} .model-id {margin-left:24px}
.score {font-size:21px} .score {font-weight:800} .score {color:#28533d} .scorebar {display:inline-block} .scorebar {width:62px} .scorebar {height:5px} .scorebar {background:#e2e7dc} .scorebar {margin-left:12px} .scorebar {border-radius:3px} .scorebar i {display:block} .scorebar i {height:100%} .scorebar i {background:#51744b}
.note {padding:16px 20px} .note {font-size:13px} .note {color:#63705f} .note {border-top:1px solid #e5e8dc}
.toolbar {display:flex} .toolbar {justify-content:space-between} .toolbar {align-items:center} .toolbar {gap:14px} .toolbar {flex-wrap:wrap} .toolbar {margin:20px 0}
.filters {display:flex} .filters {gap:7px} .filters {flex-wrap:wrap} .filters button {border:1px solid #d5d9cc} .filters button {background:transparent} .filters button {padding:7px 13px} .filters button {border-radius:30px} .filters button {font-size:13px} .filters button[aria-pressed=true] {background:#284b37} .filters button[aria-pressed=true] {color:white} .filters button[aria-pressed=true] {border-color:#284b37}
input {padding:10px 13px} input {border:1px solid #cdd3c6} input {border-radius:7px} input {background:#fffefa} input {width:260px} input:focus {outline:2px solid #51744b}
.task-name {white-space:normal} .task-name {min-width:275px} .task-name {max-width:440px} .task-name button {border:0} .task-name button {padding:0} .task-name button {background:none} .task-name button {text-align:left} .task-name button {font-weight:650} .task-name button:hover {text-decoration:underline} .tag {display:block} .tag {font-size:11px} .tag {color:#747e70} .tag {text-transform:uppercase} .tag {letter-spacing:.7px} .tag {margin-top:3px}
.chip {display:inline-block} .chip {border-radius:5px} .chip {padding:4px 8px} .chip {font-weight:650} .chip {font-size:13px} .good {background:#e4efdc} .good {color:#365632} .bad {background:#f4e5df} .bad {color:#935642} .partial {background:#f6edc9} .partial {color:#75622c}
.detail td {white-space:normal} .detail td {text-align:left} .detail td {padding:20px 24px} .detail {background:#f4f5ee} .detail p {max-width:920px} .detail table {font-size:13px} .detail table td {padding:9px} .detail table th {padding:9px} .detail table td {white-space:nowrap} .detail[hidden] {display:none}
.grid2 {display:grid} .grid2 {grid-template-columns:1fr 1fr} .grid2 {gap:24px} .card {padding:24px} .card ul {padding-left:20px} .card li {margin:12px 0} .card p {font-size:14px} .card p {color:#626d62} .status {color:#385636} .status {font-weight:700}
details summary {cursor:pointer} details summary {font-weight:650} details summary {padding:16px 20px} .notice {border-left:3px solid #cead69} .notice {padding:12px 18px} .notice {background:#f5efdF}
footer {margin:40px 0 10px} footer {border-top:1px solid #dce0d3} footer {padding-top:20px} footer {font-size:13px} footer {color:#657360}
@media(max-width:800px) {.wrap {padding:20px 16px} .stats {grid-template-columns:1fr 1fr} .grid2 {grid-template-columns:1fr} .top {align-items:flex-start} .top {flex-direction:column} nav {gap:16px} th,td {padding:12px} input {width:100%} h1 {letter-spacing:-1px}}
</style></head><body>
<header><div class="wrap top"><a class="brand" href="index.html"><span class="ball" aria-hidden="true"></span>PokeBench</a><nav><a href="#tasks">Tasks &amp; replays</a><a href="#stability">Repeat check</a><a href="technical-report.pdf">Technical report</a><a href="historical-index.html">Earlier results</a></nav></div></header>
<main class="wrap"><section class="hero"><div class="kicker">Pokemon Red · Short-task benchmark</div><h1>How well can models play?</h1><p class="lede">Six models. The same starting saves and task budgets. Compare navigation, battle tactics, menu operation, preparation, and quest completion.</p><div class="stats" id="stats"></div></section>
<section aria-labelledby="rank-title"><h2 id="rank-title">Model leaderboard</h2><p class="muted">Overall score gives each of the five skill categories equal weight.</p><div class="panel"><div class="scroll"><table><thead id="rank-head"></thead><tbody id="ranking"></tbody></table></div><div class="note">Scores are task completion rates, except preparation, which uses the win rate of a fixed battle controller with the model's submitted team. Each task group has equal weight within its category. Tokens are reported input plus output usage, including cached input where reported. They are not a dollar bill.</div><details><summary>How sensitive is the ranking to task selection?</summary><div class="note" id="sensitivity"></div></details></div></section>
<section id="tasks" class="section"><h2>Explore the tasks</h2><p class="muted">Choose a category or search. Open any task for its goal, budgets, individual outcomes, and replays.</p><div class="toolbar"><div class="filters" id="filters"></div><input id="search" type="search" placeholder="Search tasks or goals" aria-label="Search tasks or goals"></div><p id="task-count" class="small muted" aria-live="polite"></p><div class="panel scroll"><table><thead id="task-head"></thead><tbody id="task-body"></tbody></table></div></section>
<section class="section grid2"><div class="panel card"><div class="kicker">Failure review</div><h2>What went wrong?</h2><div id="audit"></div><p>The counts describe recorded symptoms. A rejected response is not automatically an emulator bug, and a valid response is not proof that every shortcut behaved correctly.</p><a href="focused-pass-v056.html">Full attempt log</a></div><div class="panel card"><div class="kicker">What the results mean</div><h2>Useful differences, uneven difficulty</h2><div id="difficulty"></div><p>The Lorelei replay shows a strategy difference: Sol used Amnesia repeatedly before attacking. Opus switched to Pikachu early and later lost the battle. Neither recorded response-format errors in that attempt.</p><p>In the reviewed cave and boulder failures, the agents were still navigating the same map at the decision limit. The capture attempt reached a Pikachu battle but had not caught it when its limit arrived. These are observations, not proof that the framework is faultless.</p><p>The all-zero league-preparation task also hides partial progress: its fixed controller often reached the Champion before losing. A zero win rate does not mean the team achieved nothing.</p><p><a href="replays/focused-v056-cell-0067.html">Sol's Lorelei replay</a> · <a href="replays/focused-v056-cell-0070.html">Opus's Lorelei replay</a></p></div></section>
<section id="stability" class="section"><h2>Do the results repeat?</h2><p class="muted">Two extra attempts per model on forest navigation, the underleveled Lorelei battle, and move preparation. Original saves and budgets are reused. These selected tasks do not change the main leaderboard's weights.</p><div id="repeat-status" class="notice"></div><div class="panel" style="margin-top:16px"><details><summary>View matched attempts and score changes</summary><div class="scroll"><table><thead><tr><th>Task / model</th><th>Original</th><th>Repeat 2</th><th>Repeat 3</th><th>Mean so far</th></tr></thead><tbody id="repeats"></tbody></table></div></details></div><p class="small muted">Tasks were selected after seeing the first pass. This is a targeted repeatability check, not an independent estimate of the whole leaderboard's reliability. Replaying one save does not sample all possible battle randomness.</p></section>
<footer><p id="accounting"></p><p>Exploratory results with recorded backend repairs. Earlier trials remain available. PokeBench Long is separate and has not been included here. <a href="catalog.html">Full task catalog</a> · <a href="focused-analysis.json">Download analysis JSON</a></p><p id="updated"></p></footer></main>
<script id="data" type="application/json">__DATA__</script><script>
const d = JSON.parse(document.getElementById('data').textContent)
const $ = id => document.getElementById(id)
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
const pct = x => x == null ? 'Pending' : (x * 100).toFixed(1) + '%'
const count = x => Number(x || 0).toLocaleString()
const mil = x => (Number(x || 0)/1e6).toFixed(1) + 'M'
const cap = x => x[0].toUpperCase() + x.slice(1)
const policy = t => t.mode === 'preparation' ? 'Constrained preparation submission' : (t.action_policy || '').includes('manual') ? 'Manual menu inputs' : 'Mechanical gameplay shortcuts enabled'
const mean = rows => {const values = rows.filter(r => r.state === 'finished' && r.value != null).map(r => r.value)
return values.length ? values.reduce((a,b) => a+b,0)/values.length : null}
const chip = value => `<span class="chip ${value === 1 ? 'good' : value === 0 ? 'bad' : 'partial'}">${pct(value)}</span>`
$('stats').innerHTML = [[d.counts.tasks,'Tasks across five categories'],[`${d.counts.finished}/${d.counts.attempts}`,'Initial attempts finished'],[d.counts.evaluation_errors,'Unresolved evaluation errors'],[mil(d.usage.reported_tokens),'Reported tokens, including archived attempts']].map(([a,b])=>`<div class="stat"><strong>${a}</strong><span>${b}</span></div>`).join('')
$('rank-head').innerHTML = `<tr><th>Model</th><th>Overall</th>${d.categories.map(c=>`<th>${cap(c)}</th>`).join('')}<th>Tokens</th></tr>`
$('ranking').innerHTML = d.models.map((m,i)=>`<tr><th><span class="rank">${i+1}</span><span class="model">${esc(m.label)}</span><span class="model-id">${esc(m.model)}</span></th><td><span class="score">${pct(m.score)}</span><span class="scorebar"><i style="width:${m.score*100}%"></i></span></td>${d.categories.map(c=>`<td>${pct(m.categories[c])}</td>`).join('')}<td>${mil(m.tokens)}</td></tr>`).join('')
$('sensitivity').innerHTML='<p>Remove each task group once and recompute the same category-weighted score. These are observed rank ranges, not statistical confidence intervals.</p><p>'+d.models.map(m=>{
const r=d.task_sensitivity.rows.find(r=>r.model===m.model)
return `<strong>${esc(m.label)}:</strong> ${r.best_rank===r.worst_rank?r.best_rank:r.best_rank+' to '+r.worst_rank}`
}).join(' · ')+'</p>'
let filter = 'all'
$('filters').innerHTML = ['all',...d.categories].map(c=>`<button data-filter="${c}" aria-pressed="${c==='all'}">${cap(c)}</button>`).join('')
$('filters').addEventListener('click',e=>{const b=e.target.closest('button')
if(!b) return
filter=b.dataset.filter
for(const item of $('filters').children) item.setAttribute('aria-pressed',item===b)
renderTasks()})
$('search').addEventListener('input',renderTasks)
$('task-head').innerHTML = `<tr><th>Task</th>${d.models.map(m=>`<th>${esc(m.label)}</th>`).join('')}</tr>`
function renderTasks(){
const query=$('search').value.toLowerCase()
const tasks=d.tasks.filter(t=>(filter==='all'||t.category===filter)&&`${t.title} ${t.goal}`.toLowerCase().includes(query))
$('task-count').textContent=`${tasks.length} of ${d.tasks.length} tasks. Scores average registered starts where a task has variants.`
$('task-body').innerHTML=tasks.map(t=>{
const rows=d.cells.filter(r=>r.task_id===t.id)
return `<tr><td class="task-name"><button aria-expanded="false" aria-controls="detail-${esc(t.id)}" data-task="${esc(t.id)}">${esc(t.title)}</button><span class="tag">${esc(t.category)}</span></td>${d.models.map(m=>`<td>${chip(mean(rows.filter(r=>r.model===m.model)))}</td>`).join('')}</tr><tr id="detail-${esc(t.id)}" class="detail" hidden><td colspan="7"><p><strong>Goal:</strong> ${esc(t.goal)}</p><p><strong>Start:</strong> ${esc(t.start)}</p><p class="small"><strong>Budget:</strong> ${count(t.decision_limit)} decisions and ${mil(t.token_limit)} tokens per attempt. <strong>Tools:</strong> ${esc(policy(t))}. ${t.mode==='preparation'?'The model submits preparation choices. A fixed controller grades battles. No gameplay replay is expected.':''}</p><div class="scroll"><table><thead><tr><th>Model / start</th><th>Score</th><th>Decisions</th><th>Tokens</th><th>End reason</th><th>Format errors</th><th>Evidence</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(d.models.find(m=>m.model===r.model).label)} / ${esc(r.variant)}</td><td>${pct(r.value)}</td><td>${count(r.decisions)}</td><td>${count(r.tokens)}</td><td>${esc(r.stop_reason||'Preparation assessed')}</td><td>${r.audit.format_error_decisions}</td><td>${r.replay?`<a href="${esc(r.replay)}">Watch replay</a>`:r.mode==='preparation'?'Scored submission':'No replay'}</td></tr>`).join('')}</tbody></table></div></td></tr>`}).join('')
}
$('task-body').addEventListener('click',e=>{const b=e.target.closest('[data-task]')
if(!b) return
const detail=$('detail-'+b.dataset.task)
detail.hidden=!detail.hidden
b.setAttribute('aria-expanded',!detail.hidden)})
renderTasks()
const reasons=d.audit.stop_reasons
$('audit').innerHTML=`<ul><li><strong>${count(reasons.model_call_budget)} runs reached the decision limit.</strong> These are scored incomplete attempts, not unfinished jobs.</li><li><strong>${count(reasons.challenge_failed)} runs ended in a task failure.</strong> Battle losses and other failed task conditions remain model outcomes.</li><li><strong>${count(d.audit.format_error_decisions)} rejected decisions across ${count(d.audit.runs_with_format_errors)} runs.</strong> They supplied no controller action or valid history request. Out of ${count(d.audit.trace_decisions)} recorded gameplay decisions. Most errors occurred in Saffron Gym navigation. The per-task table exposes the counts.</li><li><strong>${d.counts.evaluation_errors} unresolved evaluation errors.</strong> Archived provider failures and the repaired oversized-memory response remain recorded.</li></ul>`
$('difficulty').innerHTML=`<p><strong>${d.counts.all_full_score_tasks} tasks scored 100% for every model.</strong> They provide capability coverage but little separation in this pass.</p><p><strong>${d.counts.all_zero_tasks} tasks scored zero for every model.</strong> Inspect their traces and task feasibility before treating them as evidence of model limits.</p>`
function renderRepeats(){
$('repeat-status').innerHTML=`<strong>${d.repeats.finished}/${d.repeats.planned} repeat attempts finished.</strong> ${esc(d.repeats.status)}. ${mil(d.repeats.reported_tokens)} reported tokens against a ${mil(d.repeats.token_ceiling)} phase ceiling.`
$('repeats').innerHTML=d.repeats.rows.map(r=>`<tr><th>${esc(d.tasks.find(t=>t.id===r.task_id).title)}<span class="model-id">${esc(d.models.find(m=>m.model===r.model).label)}</span></th><td>${pct(r.initial)}</td>${r.repeats.map(a=>`<td>${a.replay?`<a href="${esc(a.replay)}">${a.state==='finished'?pct(a.value):esc(a.state)}</a>`:a.state==='finished'?pct(a.value):esc(a.state)}</td>`).join('')}<td>${pct(r.mean)} ${r.changed?'· changed':''}</td></tr>`).join('')
}
renderRepeats()
$('accounting').textContent=`Initial pass: ${count(d.usage.selected_tokens)} tokens in current results plus ${count(d.usage.archived_tokens)} from archived attempts. ${count(d.usage.unknown_reserve)} additional tokens reserved for missing usage, not measured consumption. Repeats use a separate bounded phase within the existing ${mil(d.usage.combined_ceiling)} combined allowance.`
$('updated').textContent='Updated '+new Date(d.generated_at).toLocaleString()+'. Local analysis preview.'
const refresh = setInterval(async()=>{
try {
const response=await fetch('focused-analysis.json',{cache:'no-store'})
if(!response.ok) return
const current=await response.json()
d.repeats=current.repeats
renderRepeats()
$('updated').textContent='Updated '+new Date(current.generated_at).toLocaleString()+'. Local analysis preview.'
if(current.repeats.status==='complete') clearInterval(refresh)
} catch(error) { $('repeat-status').title='Could not refresh. Showing the last saved snapshot.' }
},30000)
</script></body></html>'''
