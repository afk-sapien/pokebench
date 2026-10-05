"""Local, read-only viewer. Agent and evaluator controls are never mounted here."""
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from .report import comparison_report, read_runs, summarize

PAGE = """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PokeAgent Bench</title>
<style>
* {box-sizing:border-box}
body {margin:0}
body {background:#10151a}
body {color:#e8efee}
body {font:15px system-ui,sans-serif}
main {max-width:1280px}
main {margin:0 auto}
main {padding:36px 24px}
header {display:flex}
header {justify-content:space-between}
header {align-items:center}
.eyebrow {color:#83e5b2}
.eyebrow {letter-spacing:0.15em}
.eyebrow {font-size:12px}
h1 {font-size:38px}
h1 {letter-spacing:-0.04em}
h1 {margin:10px 0}
p, small {color:#a8b7bd}
.tag {border:1px solid #3b5750}
.tag {border-radius:20px}
.tag {padding:7px 12px}
.tag {color:#83e5b2}
.grid {display:grid}
.grid {grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.grid {gap:20px}
.grid {margin-top:28px}
article {background:#182128}
article {border:1px solid #2b3a43}
article {border-radius:16px}
article {padding:20px}
.screen {background:#0b1115}
.screen {border-radius:10px}
.screen {padding:18px}
.screen {text-align:center}
img {width:100%}
img {max-width:320px}
img {image-rendering:pixelated}
img {aspect-ratio:10/9}
h2 {font-size:19px}
h2 {overflow-wrap:anywhere}
.score {color:#83e5b2}
.score {font-size:34px}
.metrics {display:grid}
.metrics {grid-template-columns:1fr 1fr}
.metrics {gap:15px}
.metrics {padding:20px 0}
.metrics strong {display:block}
.metrics strong {font-size:18px}
progress {width:100%}
progress {accent-color:#83e5b2}
.milestones {padding-left:20px}
.milestones {line-height:1.8}
.empty {border:1px dashed #3b5750}
.empty {padding:40px}
.empty {border-radius:16px}
.empty {margin-top:30px}
#error {color:#ffb6a5}
footer {padding-top:26px}
footer {color:#889aA3}
code {color:#b9d9c9}
.toolbar {display:flex}
.toolbar {gap:16px}
.toolbar {align-items:center}
.toolbar {flex-wrap:wrap}
.toolbar {margin:24px 0}
select {background:#182128}
select {color:#e8efee}
select {border:1px solid #3b5750}
select {border-radius:8px}
select {padding:10px}
select {max-width:100%}
a {color:#83e5b2}
.table-wrap {overflow-x:auto}
.table-wrap {border:1px solid #2b3a43}
.table-wrap {border-radius:12px}
table {width:100%}
table {border-collapse:collapse}
table {font-variant-numeric:tabular-nums}
th, td {padding:14px}
th, td {text-align:left}
th, td {border-bottom:1px solid #2b3a43}
th {color:#b9d9c9}
th {font-size:12px}
td {white-space:nowrap}
caption {text-align:left}
caption {padding:14px}
caption {background:#182128}
.comparison {margin:24px 0}
.comparison h2 {margin-bottom:8px}
@media(max-width:550px) {header {display:block} .tag {display:inline-block}}
</style>
<main><header><div><div class="eyebrow">POKEAGENT / EVALUATION LAB</div>
<h1>The road to Champion.</h1><p>One game. Different agents. Every step recorded.</p></div>
<span class="tag">Experimental v0.3</span></header>
<p>Compare runs with the same group ID. Different tracks, scenarios, prompts, or budgets form separate groups.</p>
<div class="toolbar"><label for="group">Comparison group </label><select id="group"><option value="">All groups</option></select>
<a href="/api/report" download="pokeagent-report.json">Download report JSON</a></div>
<div id="error" role="status"></div><section id="comparisons" aria-label="Model comparisons"></section>
<h2>Individual trials</h2><section id="runs" class="grid" aria-live="polite"></section>
<footer>Local viewer · Read-only · Updates every 3 seconds · API costs require configured prices</footer></main>
<script>
function node(tag, text, cls) {
  const element = document.createElement(tag)
  if (text !== undefined) element.textContent = text
  if (cls) element.className = cls
  return element
}
function duration(value) {
  return Math.floor(value / 3600) + 'h ' + Math.floor(value % 3600 / 60) + 'm ' + Math.floor(value % 60) + 's'
}
function metric(label, value) {
  const item = node('div')
  item.append(node('small', label), node('strong', value))
  return item
}
let snapshot = {runs:[], summary:[]}
function number(value) {
  return value == null ? 'Unavailable' : value.toLocaleString(undefined, {maximumFractionDigits:1})
}
function time(value) {
  return value == null ? 'Unavailable' : duration(value)
}
function renderComparisons(rows, summaries) {
  const container = document.getElementById('comparisons')
  container.replaceChildren()
  for (const group of [...new Set(rows.map(row => row.group))]) {
    const sample = rows.find(row => row.group === group)
    const section = node('section', undefined, 'comparison')
    section.append(node('h2', sample.goal + ' / ' + sample.track))
    section.append(node('p', sample.benchmark + ' · Group ' + group))
    const wrap = node('div', undefined, 'table-wrap')
    const table = node('table')
    table.append(node('caption', 'Only trials within this group are comparable. Success and score exclude running trials and infrastructure errors.'))
    const head = node('thead')
    const titles = node('tr')
    for (const text of ['Model', 'Trials', 'Success', 'Mean score', 'Median finish time', 'Median wall / game time', 'Median actions', 'Calls', 'Tokens in / out', 'Estimated spend']) {
      const title = node('th', text)
      title.scope = 'col'
      titles.append(title)
    }
    head.append(titles)
    const body = node('tbody')
    for (const entry of summaries.filter(item => item.group === group)) {
      const row = node('tr')
      const model = node('th', (entry.model || 'External agent') + ' / ' + entry.provider)
      model.scope = 'row'
      row.append(model)
      const success = entry.success_rate == null ? 'Not evaluated' : number(entry.success_rate * 100) + '% (' + entry.completed + '/' + entry.evaluated + ')'
      const partial = entry.incomplete_usage_trials ? ' + unreported usage' : ''
      const spend = entry.estimated_cost_usd == null ? 'Unavailable' : '$' + entry.estimated_cost_usd.toFixed(4) + ' (' + entry.priced_trials + '/' + entry.trials + ' priced)' + partial
      for (const text of [entry.trials + ' total · ' + entry.running + ' running · ' + entry.errors_or_interruptions + ' errors', success,
        number(entry.mean_score) + ' / ' + sample.score_max, time(entry.median_completion_wall_seconds),
        time(entry.median_wall_seconds) + ' / ' + time(entry.median_emulated_seconds), number(entry.median_actions),
        number(entry.total_model_calls), number(entry.total_input_tokens) + ' / ' + number(entry.total_output_tokens), spend]) row.append(node('td', text))
      body.append(row)
    }
    table.append(head, body)
    wrap.append(table)
    section.append(wrap, node('p', 'Finish time includes successes only. Wall time, game time, and actions use evaluated trials. Usage and spend include running and failed trials when available. Missing prices are not treated as zero.'))
    container.append(section)
  }
}
function render() {
    const selected = document.getElementById('group').value
    const rows = snapshot.runs.filter(row => !selected || row.group === selected)
    renderComparisons(rows, snapshot.summary)
    const container = document.getElementById('runs')
    container.replaceChildren()
    if (!rows.length) container.append(node('div', 'No runs yet. Start a run with pokeagent run or connect an MCP agent.', 'empty'))
    for (const row of rows) {
      const card = node('article')
      card.append(node('small', row.provider + ' / ' + row.track + ' / ' + row.goal))
      card.append(node('h2', row.model || 'External agent'))
      const screen = node('div', undefined, 'screen')
      const image = node('img')
      image.src = '/api/runs/' + encodeURIComponent(row.id) + '/screen?t=' + row.frames
      image.alt = 'Current game screen for ' + row.id
      screen.append(image)
      card.append(screen, node('p', row.id + ' · ' + (row.stop_reason || 'running')))
      card.append(node('div', row.score + ' / ' + row.score_max, 'score'))
      const progress = node('progress')
      progress.value = row.score
      progress.max = row.score_max
      progress.setAttribute('aria-label', 'Achievement score')
      card.append(progress)
      const metrics = node('div', undefined, 'metrics')
      metrics.append(metric('Wall time', duration(row.wall_seconds)), metric('Game time', duration(row.emulated_seconds)))
      metrics.append(metric('Actions', row.actions.toLocaleString()), metric('Model calls', row.provider === 'external-mcp' ? 'Unavailable' : row.usage.calls))
      metrics.append(metric('Tokens in / out', row.provider === 'external-mcp' ? 'Unavailable' : row.usage.input_tokens + ' / ' + row.usage.output_tokens), metric('Estimated cost', row.usage.estimated_cost_usd == null ? 'Not configured' : '$' + row.usage.estimated_cost_usd.toFixed(4)))
      card.append(metrics)
      if (row.usage.accounting_complete === false) card.append(node('p', 'Usage is incomplete. A failed request may have consumed additional tokens.'))
      const milestones = node('ul', undefined, 'milestones')
      for (const award of row.achievements) milestones.append(node('li', award.id + ' +' + award.points + ' at ' + duration(award.wall_seconds)))
      if (row.achievements.length) card.append(milestones)
      if (row.state === 'finished') {
        const review = node('a', 'Watch decision recap')
        review.href = '/api/runs/' + encodeURIComponent(row.id) + '/review'
        review.target = '_blank'
        review.rel = 'noopener'
        const link = node('p')
        link.append(review)
        card.append(link)
      }
      card.append(node('small', 'Comparison group ' + row.group))
      container.append(card)
    }
}
async function refresh() {
  try {
    const response = await fetch('/api/report', {cache:'no-store'})
    if (!response.ok) throw new Error('Could not read run data')
    snapshot = await response.json()
    const select = document.getElementById('group')
    const selected = select.value
    select.replaceChildren()
    const all = node('option', 'All groups')
    all.value = ''
    select.append(all)
    for (const group of [...new Set(snapshot.runs.map(row => row.group))]) {
      const sample = snapshot.runs.find(row => row.group === group)
      const option = node('option', sample.goal + ' / ' + sample.track + ' / ' + group)
      option.value = group
      select.append(option)
    }
    if ([...select.options].some(option => option.value === selected)) select.value = selected
    render()
    document.getElementById('error').textContent = ''
  } catch (error) {
    document.getElementById('error').textContent = 'Viewer disconnected. Retrying shortly.'
  }
}
document.getElementById('group').addEventListener('change', render)
refresh()
setInterval(refresh, 3000)
</script></html>
"""


def create_app(root: Path):
    root = root.resolve()
    app = FastAPI(title="PokeAgent Bench", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return PAGE

    @app.get("/api/report")
    def report():
        return comparison_report(root)

    @app.get("/api/runs")
    def runs():
        return read_runs(root)

    @app.get("/api/summary")
    def summary():
        return summarize(read_runs(root))

    @app.get("/api/runs/{run_id}/review", response_class=HTMLResponse)
    def review(run_id: str):
        from .review import review_html
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id) or run_id in (".", ".."):
            raise HTTPException(404)
        path = root / run_id
        if path.is_symlink() or not path.is_dir() or not path.resolve().is_relative_to(root):
            raise HTTPException(404)
        try:
            return HTMLResponse(review_html([path]), headers={"Cache-Control": "no-store"})
        except (ValueError, OSError, KeyError, TypeError):
            raise HTTPException(422, "Review unavailable. A finished run with recorded visual-feedback images is required.") from None

    @app.get("/api/runs/{run_id}/screen")
    def screen(run_id: str):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id) or run_id in (".", ".."):
            raise HTTPException(404)
        path = root / run_id / "latest.png"
        if not path.is_file() or path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(root):
            raise HTTPException(404)
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

    return app
