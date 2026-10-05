"""Offline review player with fixed transport and independently scrolling details."""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>PokeAgent Bench | Run review</title>
<style>
* {box-sizing:border-box}
body {margin:0}
body {background:#0c1116}
body {color:#edf3ef}
body {font:14px system-ui,sans-serif}
body {overflow:hidden}
main {height:100dvh}
main {display:grid}
main {grid-template-rows:58px minmax(0,1fr) 158px}
header {display:flex}
header {align-items:center}
header {justify-content:space-between}
header {padding:0 18px}
header {border-bottom:1px solid #2b3942}
h1 {font-size:15px}
h1 {margin:0}
h2 {font-size:15px}
h3 {font-size:13px}
p {line-height:1.5}
p {margin:8px 0}
small,.muted {color:#a4b6bc}
.eyebrow {font-size:10px}
.eyebrow {letter-spacing:.13em}
.eyebrow {color:#86e3ae}
.tabs {display:flex}
.tabs {gap:6px}
button,select {font:inherit}
button,select {color:inherit}
button,select {background:#1b2832}
button,select {border:1px solid #3b4d59}
button,select {border-radius:7px}
button,select {height:36px}
button,select {padding:0 12px}
button {cursor:pointer}
button {touch-action:manipulation}
button {user-select:none}
button:hover {background:#2a3c49}
button:focus-visible,select:focus-visible,input:focus-visible {outline:2px solid #86e3ae}
button[aria-selected=true],#play {background:#86e3ae}
button[aria-selected=true],#play {color:#0c2418}
button:disabled {opacity:.35}
button:disabled {cursor:default}
.workspace {display:grid}
.workspace {grid-template-columns:minmax(0,1fr) 350px}
.workspace {min-height:0}
.stage {min-width:0}
.stage {min-height:0}
.stage {padding:18px}
.stage {display:flex}
.stage {align-items:center}
.screens {display:grid}
.screens {grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.screens {gap:16px}
.screens {width:100%}
.screens {height:100%}
figure {margin:0}
figure {min-width:0}
figure {min-height:0}
figure {display:grid}
figure {grid-template-rows:24px minmax(0,1fr)}
figure img {width:100%}
figure img {height:100%}
figure img {min-height:0}
figure img {object-fit:contain}
figure img {image-rendering:pixelated}
figcaption {color:#93a9b3}
figcaption {font:11px ui-monospace,monospace}
figcaption {white-space:nowrap}
.inspector {min-height:0}
.inspector {overflow-y:auto}
.inspector {overflow-wrap:anywhere}
.inspector {scrollbar-gutter:stable}
.inspector {padding:18px}
.inspector {border-left:1px solid #2b3942}
.inspector {background:#141e26}
#plan {font-size:17px}
#plan {line-height:1.45}
#plan {margin:10px 0 14px}
#actions,.tags,.metrics,.jumps {display:flex}
#actions,.tags,.metrics,.jumps {flex-wrap:wrap}
#actions,.tags,.metrics,.jumps {gap:7px}
.action,.tag {font-size:11px}
.action,.tag {border:1px solid #38505b}
.action,.tag {border-radius:4px}
.action,.tag {padding:6px}
.tag.warn {color:#f5c888}
.tags {margin:12px 0}
#cost,#reviewer {font-size:12px}
details {margin-top:18px}
summary {cursor:pointer}
summary {color:#b1c9d1}
pre {white-space:pre-wrap}
pre {font:11px ui-monospace,monospace}
li {margin:6px 0}
ul {padding-left:18px}
.metrics {gap:16px}
.metrics strong {display:block}
#model {font-size:12px}
#end {color:#f5c888}
.jumps {margin-top:12px}
.jumps button {height:auto}
.jumps button {min-height:32px}
.jumps button {font-size:11px}
.jumps button {text-align:left}
footer {font-size:11px}
footer {color:#8fa5b0}
footer {line-height:1.5}
footer {margin-top:20px}
.transport {border-top:1px solid #3b4d59}
.transport {background:#18242d}
.transport {padding:10px 18px}
.transport {overflow:hidden}
.timeline {display:flex}
.timeline {height:12px}
.timeline {gap:1px}
.timeline button {flex:1}
.timeline button {min-width:0}
.timeline button {height:12px}
.timeline button {padding:0}
.timeline button {border:0}
.timeline button {border-radius:1px}
.timeline .repeat {background:#906c3b}
.timeline .event {background:#407d61}
.timeline .active {background:#c1ffdb}
input[type=range] {display:block}
input[type=range] {width:100%}
input[type=range] {height:20px}
input[type=range] {margin:1px 0 6px}
input[type=range] {accent-color:#86e3ae}
.toolbar {display:flex}
.toolbar {align-items:center}
.toolbar {gap:12px}
.buttons {display:grid}
.buttons {grid-template-columns:48px 82px 48px}
.buttons {gap:6px}
.buttons {flex-shrink:0}
#prev,#next {font-size:21px}
.toolbar label {display:flex}
.toolbar label {align-items:center}
.toolbar label {gap:6px}
.toolbar label {font-size:12px}
#speed {width:104px}
#mode {width:130px}
.statusline {display:flex}
.statusline {gap:20px}
.statusline {margin-top:7px}
.statusline {height:18px}
.statusline {font-size:12px}
.statusline {white-space:nowrap}
#position {font-variant-numeric:tabular-nums}
#position {overflow:hidden}
#position {text-overflow:ellipsis}
#coverage {color:#a4b6bc}
#skipped {height:16px}
#skipped {font-size:11px}
#skipped {color:#f5c888}
#skipped {white-space:nowrap}
#skipped {overflow:hidden}
.shortcuts {margin-left:auto}
.shortcuts {font-size:11px}
.shortcuts {color:#a4b6bc}
@media(max-width:1000px) {.shortcuts {display:none} .workspace {grid-template-columns:minmax(0,1fr) 290px}}
@media(max-width:760px) {
main {grid-template-rows:54px minmax(0,1fr) 186px}
header {padding:0 10px}
h1 {font-size:12px}
.tabs button {padding:0 9px}
.workspace {grid-template-columns:minmax(0,1fr)}
.workspace {grid-template-rows:minmax(0,min(52vw,55%)) minmax(0,1fr)}
.stage {padding:10px}
.screens {gap:10px}
.inspector {border-left:0}
.inspector {border-top:1px solid #2b3942}
.inspector {padding:10px 14px}
#plan {font-size:14px}
.transport {padding:8px 10px}
.toolbar {display:grid}
.toolbar {grid-template-columns:190px minmax(0,1fr)}
.toolbar {gap:6px 12px}
.toolbar label {justify-content:flex-start}
.toolbar label span {display:none}
#mode {width:100%}
#speed {width:100%}
#novel {font-size:11px}
.statusline {gap:8px}
.statusline {font-size:10px}
#coverage {display:none}
}
@media(max-height:520px) and (min-width:761px) {main {grid-template-rows:44px minmax(0,1fr) 142px} .transport {padding:4px 18px}}
</style>
</head>
<body><main>
<header><h1>POKEAGENT <span class="muted">/ REPLAY</span></h1><nav id="tabs" class="tabs" aria-label="Choose model run"></nav></header>
<div class="workspace">
<section class="stage" aria-label="Recorded game screens"><div class="screens">
<figure><figcaption id="beforeLabel"></figcaption><img id="before" alt="Game screen before the recorded decision"></figure>
<figure><figcaption id="afterLabel"></figcaption><img id="after" alt="Game screen after the executed controller actions"></figure>
</div></section>
<aside class="inspector" aria-label="Decision details">
<div class="eyebrow">AGENT'S STATED PLAN</div><p id="plan"></p><div id="actions"></div>
<p><small>Expected result, according to the agent</small><br><span id="expected"></span></p>
<div id="tags" class="tags"></div><p id="reviewer"></p><p id="cost" class="muted"></p>
<details id="gameplay-panel"><summary>Information supplied to model</summary><pre id="gameplay-input"></pre></details>
<details id="notebook"><summary>Agent notebook</summary><small>These claims may contain mistakes.</small><div id="notes"></div></details>
<details><summary>Jump to a moment</summary><small>Locations are evaluator annotations. Scene reports are the agent's claims.</small><div id="jumps" class="jumps"></div></details>
<details><summary>Run summary</summary><strong id="model"></strong><p id="objective"></p><div id="metrics" class="metrics"></div><p id="end"></p></details>
<details><summary>Evidence and provenance</summary><pre id="evidence"></pre></details>
<footer>Recorded decision screens, not continuous video. Highlights skip decisions. Amber marks a previously seen image, green marks an event. Repeated pixels do not prove a stall. Review annotations were not fed to the agent. Works offline with no model calls.</footer>
</aside></div>
<section class="transport" aria-label="Playback controls">
<div id="timeline" class="timeline" aria-label="Decision timeline"></div>
<input id="seek" type="range" min="0" value="0" aria-label="Seek to a decision">
<div class="toolbar">
<div class="buttons"><button id="prev" aria-label="Previous decision" title="Previous decision (Left arrow)">←</button><button id="play" title="Play or pause (Space)">Play</button><button id="next" aria-label="Next decision" title="Next decision (Right arrow)">→</button></div>
<label><span>Speed</span><select id="speed" aria-label="Playback speed"><option value="1">1 / sec</option><option value="2">2 / sec</option><option value="4">4 / sec</option><option value="8" selected>8 / sec</option><option value="16">16 / sec</option><option value="32">32 / sec</option></select></label>
<label><span>Show</span><select id="mode" aria-label="Playback selection"><option value="all">Every decision</option><option value="highlights">Highlights</option></select></label>
<button id="novel">Next new screen</button><span class="shortcuts">← → Step · Shift: ±10 · Space: play</span>
</div>
<div class="statusline"><span id="position"></span><span id="coverage"></span></div><div id="skipped"></div>
</section></main>
<script id="data" type="application/json">__REVIEW_DATA__</script>
<script>
const data = JSON.parse(document.getElementById('data').textContent)
const $ = id => document.getElementById(id)
const number = value => Number(value || 0).toLocaleString()
const elapsed = value => Math.floor(value / 60) + 'm ' + Math.floor(value % 60) + 's'
let runIndex = 0
let cursor = 0
let timer = null
let playing = false
let hashTimer = null
function speed() {
  return $('speed').value === 'duration' ? Math.max(1, sequence().length - 1) / data.seconds : Number($('speed').value)
}
function updateHash() {
  if (hashTimer !== null) return
  hashTimer = setTimeout(() => {
    history.replaceState(null, '', '#run=' + encodeURIComponent(run().id) + '&decision=' + run().steps[cursor].decision)
    hashTimer = null
  }, 500)
}
function element(tag, text, cls) {
  const e = document.createElement(tag)
  if (text !== undefined) e.textContent = text
  if (cls) e.className = cls
  return e
}
function run() { return data.runs[runIndex] }
function sequence() { return $('mode').value === 'highlights' ? run().highlights : run().steps.map((_, i) => i) }
function pause() {
  clearTimeout(timer)
  timer = null
  playing = false
  $('play').textContent = cursor === run().steps.length - 1 ? 'Replay' : 'Play'
}
function render(skipped = 0) {
  const r = run()
  const s = r.steps[cursor]
  $('before').src = r.images[s.before]
  $('after').src = r.images[s.after]
  $('beforeLabel').textContent = 'BEFORE · frame ' + number(s.before_frame)
  $('afterLabel').textContent = 'AFTER · frame ' + number(s.after_frame)
  $('plan').textContent = s.plan
  $('expected').textContent = s.expected || 'No expected result recorded'
  $('actions').replaceChildren()
  for (const [i, a] of s.actions.entries()) {
    const text = (a.button || 'wait').toUpperCase() + ' · hold ' + a.hold_frames + 'f + release ' + a.release_frames + 'f · ran ' + s.action_frames[i] + 'f'
    $('actions').append(element('span', text, 'action'))
  }
  if (!s.actions.length) $('actions').append(element('span', 'No controller action executed', 'action'))
  $('tags').replaceChildren()
  if (s.unchanged) $('tags').append(element('span', 'Before and after pixels identical', 'tag warn'))
  if (s.seen_before) $('tags').append(element('span', 'Result screen seen ' + s.seen_before + ' time(s) before', 'tag warn'))
  if (s.no_new_view_streak >= 4) $('tags').append(element('span', s.no_new_view_streak + ' decisions without a new result image', 'tag warn'))
  for (const event of s.events) $('tags').append(element('span', event.label, 'tag'))
  $('reviewer').textContent = 'Reviewer location: ' + s.location + ' · Game time: ' + s.game_seconds.toFixed(1) + 's. Map state can change before a fade finishes.'
  $('cost').textContent = number(s.tokens) + ' tokens this decision · ' + number(s.cumulative_tokens) + ' cumulative · ' + s.model_seconds.toFixed(1) + 's model time'
  if ($('notebook').open || !playing) {
  $('notes').replaceChildren()
  for (const [key, title] of [['observed', 'Claimed observations'], ['hypotheses', 'Hypotheses'], ['unsuccessful_attempts', 'Remembered failed attempts']]) {
    $('notes').append(element('h3', title))
    const list = element('ul')
    for (const item of s[key]) list.append(element('li', item))
    if (!s[key].length) list.append(element('li', 'None recorded'))
    $('notes').append(list)
  }
  }
  $('gameplay-panel').hidden = !s.gameplay_input
  $('gameplay-input').textContent = JSON.stringify({information:s.gameplay_input, requested_commands:s.requested_commands}, null, 2)
  $('evidence').textContent = JSON.stringify({run:r.id, benchmark:r.benchmark, track:r.track, decision:s.decision,
    before_frame:s.before_frame, after_frame:s.after_frame, source_before_sha256:s.source_before_sha256,
    source_after_sha256:s.source_after_sha256, trace_head:r.trace_head,
    final_evaluator:r.final_evaluator}, null, 2)
  $('seek').value = cursor
  $('position').textContent = 'Decision ' + s.decision + ' of ' + r.steps.length + ' · ' + number(s.cumulative_tokens) + ' / ' + number(r.tokens) + ' reported tokens'
  $('coverage').textContent = sequence().length + ' decisions · about ' + Math.ceil(Math.max(0, sequence().length - 1) / speed()) + 's from start'
  $('skipped').textContent = skipped > 0 ? 'Skipped ' + skipped + ' decisions in highlights mode. Use the slider or arrows to inspect them.' : ''
  $('prev').disabled = cursor === 0
  $('next').disabled = cursor === r.steps.length - 1
  $('novel').disabled = !r.steps.some((step, i) => i > cursor && !step.seen_before)
  for (const [i, button] of [...$('timeline').children].entries()) button.classList.toggle('active', i === cursor)
  updateHash()
}
function seek(index) {
  pause()
  cursor = Math.max(0, Math.min(run().steps.length - 1, index))
  render()
  pause()
}
function schedule() {
  timer = setTimeout(() => {
    const next = sequence().find(i => i > cursor)
    if (next === undefined) { pause()
      return
    }
    const skipped = next - cursor - 1
    cursor = next
    render(skipped)
    if (cursor === run().steps.length - 1) pause()
    else schedule()
  }, 1000 / speed())
}
function play() {
  if (playing) { pause()
    return
  }
  if (cursor === run().steps.length - 1) cursor = 0
  playing = true
  $('play').textContent = 'Pause'
  render()
  schedule()
}
function selectRun(index, initial = 0) {
  pause()
  runIndex = index
  cursor = Math.max(0, Math.min(initial, run().steps.length - 1))
  const r = run()
  for (const [i, button] of [...$('tabs').children].entries()) button.setAttribute('aria-selected', String(i === index))
  $('model').textContent = r.model + ' · ' + r.id
  $('objective').textContent = r.objective
  $('metrics').replaceChildren()
  for (const [label, value] of [['Decisions', r.steps.length], ['Actions', r.actions], ['Reported tokens', number(r.tokens)], ['Recorded wall time', elapsed(r.wall_seconds)], ['Formal score', r.score + ' / ' + r.score_max]]) {
    const item = element('div')
    item.append(element('small', label), element('strong', value))
    $('metrics').append(item)
  }
  $('end').textContent = (r.completed ? 'Completed' : 'Formal completion not recorded') + ' · ' + r.stop_reason.replaceAll('_', ' ') + (r.accounting_complete === false ? ' · Token accounting incomplete' : '')
  $('seek').max = r.steps.length - 1
  $('timeline').replaceChildren()
  $('jumps').replaceChildren()
  const moments = new Map([[0, 'Start'], [r.steps.length - 1, 'Final state']])
  for (const [i, step] of r.steps.entries()) {
    const button = element('button', '', step.events.length ? 'event' : step.seen_before ? 'repeat' : '')
    button.setAttribute('aria-label', 'Decision ' + step.decision)
    button.title = 'Decision ' + step.decision + ': ' + step.plan
    button.onclick = () => seek(i)
    $('timeline').append(button)
    if (step.events.length) moments.set(i, step.events.map(e => e.label).join(' / '))
    else if (step.no_new_view_streak === 4) moments.set(i, 'Repeated views')
  }
  for (const [i, label] of [...moments].sort((a,b) => a[0]-b[0])) {
    const button = element('button', 'D' + r.steps[i].decision + ' · ' + label)
    button.onclick = () => seek(i)
    $('jumps').append(button)
  }
  render()
  pause()
}
for (const [index, r] of data.runs.entries()) {
  const multipleTasks = new Set(data.runs.map(run => run.objective)).size > 1
  const label = r.model.replace(/^gpt-[\d.]+-/, '').toUpperCase() + (multipleTasks ? ' · ' + r.task_label : '')
  const button = element('button', label)
  button.setAttribute('aria-selected', 'false')
  button.onclick = () => selectRun(index)
  $('tabs').append(button)
}
if (data.seconds) {
  const option = element('option', data.seconds + 's total')
  option.value = 'duration'
  $('speed').append(option)
  $('speed').value = 'duration'
}
$('notebook').ontoggle = () => { if ($('notebook').open) render() }
$('play').onclick = play
$('prev').onclick = () => seek(cursor - 1)
$('next').onclick = () => seek(cursor + 1)
$('seek').oninput = event => seek(Number(event.target.value))
$('novel').onclick = () => {
  const next = run().steps.findIndex((step, i) => i > cursor && !step.seen_before)
  if (next >= 0) seek(next)
}
$('mode').onchange = () => { pause()
  render()
}
$('speed').onchange = () => {
  clearTimeout(timer)
  render()
  if (playing) schedule()
}
document.addEventListener('keydown', event => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName) || document.activeElement.isContentEditable) return
  if (event.code === 'Space' || event.code === 'KeyK') { event.preventDefault()
    play()
  }
  if (event.code === 'ArrowRight' || event.code === 'KeyL') { event.preventDefault()
    seek(cursor + (event.shiftKey ? 10 : 1))
  }
  if (event.code === 'ArrowLeft' || event.code === 'KeyJ') { event.preventDefault()
    seek(cursor - (event.shiftKey ? 10 : 1))
  }
})
const fragment = new URLSearchParams(location.hash.slice(1))
const initialRun = Math.max(0, data.runs.findIndex(r => r.id === fragment.get('run')))
const requestedDecision = Number(fragment.get('decision'))
const initialStep = Math.max(0, data.runs[initialRun].steps.findIndex(s => s.decision === requestedDecision))
selectRun(initialRun, initialStep)
</script></body></html>"""
