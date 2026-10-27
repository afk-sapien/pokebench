const $ = id => document.getElementById(id)
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
const pct = x => x == null ? 'Pending' : (x * 100).toFixed(1) + '%'
const million = x => (Number(x || 0) / 1e6).toFixed(2) + 'M'
const dollars = x => x == null ? 'Unknown' : '$' + Number(x).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})
const costRange = c => !c || c.low == null ? 'Unknown' : (Math.abs(c.high - c.low) < .005 ? dollars(c.low) : dollars(c.low) + '–' + dollars(c.high))
const costCell = c => `<span class="cost-value">${costRange(c)}</span>${c?.partial ? '<small class="partial-label">PARTIAL USAGE</small>' : ''}`
const count = x => Number(x || 0).toLocaleString()
const cap = x => x[0].toUpperCase() + x.slice(1)
const categoryNames = {navigation:'Navigation',battle:'Battles',operations:'Menus',preparation:'Preparation',objectives:'Quests'}
const reason = x => ({completed:'Completed',model_call_budget:'Decision limit',token_budget:'Token limit',challenge_failed:'Task failed',provider_error:'Evaluation error',loop_budget:'No-progress limit',loop_token_budget:'No-progress limit'}[x] || (x || '').replaceAll('_',' '))
let data
let category = 'all'
let model = null
let expanded = false
let longLimit = 2000
let view = location.hash === '#long' ? 'long' : 'short'
function setView(next, updateHash = true) {
  view = next
  for (const name of ['short','long']) {
    $('tab-' + name).setAttribute('aria-selected', name === view)
    $('tab-' + name).tabIndex = name === view ? 0 : -1
    $('panel-' + name).hidden = name !== view
  }
  if (updateHash) history.replaceState(null, '', '#' + view)
  if (data) renderStatus()
}
document.querySelectorAll('[data-view]').forEach(button => {
  button.addEventListener('click', () => setView(button.dataset.view))
  button.addEventListener('keydown', event => {
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return
    event.preventDefault()
    const next = event.key === 'Home' ? 'short' : event.key === 'End' ? 'long' : view === 'short' ? 'long' : 'short'
    setView(next)
    $('tab-' + next).focus()
  })
})
window.addEventListener('hashchange', () => {
  if (['#short','#long'].includes(location.hash)) setView(location.hash.slice(1), false)
})
setView(view, false)
function renderRank() {
  const s = data.short
  $('rank-head').innerHTML = '<tr><th>Model</th><th>Score</th>' + s.categories.map(c => `<th>${categoryNames[c]}</th>`).join('') + '<th>Finished</th><th>Est. cost</th></tr>'
  let rank = 0
  $('ranking').innerHTML = s.models.map(m => {
    if (m.complete) rank += 1
    return `<tr class="${m.complete ? '' : 'partial-row'} ${model === m.id ? 'selected-model' : ''}"><td><span class="rank">${m.complete ? String(rank).padStart(2,'0') : '●'}</span><button class="model-name" data-model="${esc(m.id)}" aria-pressed="${model === m.id}">${esc(m.label)}</button><span class="model-id">${esc(m.id)}</span></td><td><span class="score-value">${pct(m.score)}</span><span class="scorebar"><i style="width:${(m.score || 0) * 100}%"></i></span>${m.complete ? '' : '<span class="partial-label">PROVISIONAL</span>'}</td>${s.categories.map(c => `<td>${pct(m.categories[c])}</td>`).join('')}<td>${m.finished}/${m.planned}${m.errors ? `<span class="partial-label">${m.errors} errors</span>` : ''}</td><td title="${million(m.tokens)} reported tokens">${costCell(m.cost)}</td></tr>`
  }).join('')
  renderCost('short')
  $('short-stats').innerHTML = [[s.tasks.length,'tasks'],[s.models.length,'models'],[s.finished + '/' + s.planned,'trials finished']].map(([n,label]) => `<div><strong>${n}</strong><span>${label}</span></div>`).join('')
}
$('ranking').addEventListener('click', event => {
  const b = event.target.closest('[data-model]')
  if (!b) return
  model = model === b.dataset.model ? null : b.dataset.model
  renderRank()
  renderTasks()
  $('task-count').scrollIntoView({block:'center',behavior:'smooth'})
})
function rowStatus(row) {
  if (row.state !== 'finished') return `<span class="state wait">${esc(row.state.replaceAll('_',' '))}</span>`
  if (row.value == null) return '<span class="state wait">Unscored</span>'
  return `<span class="state ${row.value === 0 ? 'fail' : ''}">${row.mode === 'preparation' ? pct(row.value) : row.value === 1 ? 'Pass' : 'Fail'}</span>`
}
function renderTasks() {
  const s = data.short
  const open = new Set([...document.querySelectorAll('.task[open]')].map(el => el.dataset.task))
  const query = $('search').value.trim().toLowerCase()
  const tasks = s.tasks.filter(t => (category === 'all' || t.category === category) && `${t.title} ${t.goal} ${t.start}`.toLowerCase().includes(query))
  const shown = expanded || query || category !== 'all' ? tasks : tasks.slice(0,12)
  $('task-count').textContent = `${shown.length} of ${tasks.length} tasks` + (model ? ' · ' + s.models.find(m => m.id === model).label : ' · Open a task to compare attempts and watch replays')
  $('model-filter').hidden = !model
  if (model) $('model-filter').textContent = s.models.find(m => m.id === model).label + ' only ×'
  $('show-all').hidden = shown.length === tasks.length
  $('show-all').textContent = `Show all ${tasks.length} tasks ↓`
  $('tasks').innerHTML = shown.map(t => {
    const rows = s.cells.filter(c => c.task_id === t.id && (!model || c.model === model))
    rows.sort((a,b) => s.models.findIndex(m => m.id === a.model) - s.models.findIndex(m => m.id === b.model))
    const finished = rows.filter(c => c.state === 'finished').length
    const policy = t.mode === 'preparation' ? 'Team and resource choices, assessed by a fixed battle controller.' : (t.action_policy || '').includes('manual') ? 'Manual controls. Menu shortcuts disabled.' : 'Game information and mechanical shortcuts enabled.'
    return `<details class="task" data-task="${esc(t.id)}" ${open.has(t.id) ? 'open' : ''}><summary><span class="tag">${categoryNames[t.category]}</span><span class="task-title">${esc(t.title)}</span><span class="task-coverage">${finished}/${rows.length} finished</span></summary><div class="task-body"><p><strong>Goal:</strong> ${esc(t.goal)}</p><p><strong>Start:</strong> ${esc(t.start)}</p><p class="small">${policy}</p><div class="table-scroll"><table><thead><tr><th>Model / start</th><th>Result</th><th>Decisions</th><th>Tokens</th><th>Est. cost</th><th>End reason</th><th>Replay</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(s.models.find(m => m.id === r.model).label)}${r.variant !== 'default' ? ' / ' + esc(r.variant) : ''}<span class="model-id">${esc(r.revision)}</span></td><td>${rowStatus(r)}</td><td>${count(r.decisions)} / ${count(r.decision_limit)}</td><td title="Ceiling: ${count(r.token_limit)} tokens">${million(r.tokens)}</td><td>${costCell(r.cost)}</td><td>${r.state === 'finished' ? esc(reason(r.stop_reason) || 'Preparation assessed') : esc(r.state.replaceAll('_',' '))}</td><td>${r.replay ? `<a class="replay-link" target="_blank" rel="noopener" href="${esc(r.replay)}">Watch ↗</a>` : r.mode === 'preparation' ? '<span class="small">Preparation score</span>' : '<span class="small">Not available yet</span>'}</td></tr>`).join('')}</tbody></table></div></div></details>`
  }).join('') || '<p class="empty">No matching tasks. Try another search or category.</p>'
}
$('categories').addEventListener('click', event => {
  const b = event.target.closest('[data-category]')
  if (!b) return
  category = b.dataset.category
  for (const button of $('categories').children) button.setAttribute('aria-pressed',button.dataset.category === category)
  renderTasks()
})
$('search').addEventListener('input',renderTasks)
$('show-all').addEventListener('click',() => { expanded = true
  renderTasks()
})
$('model-filter').addEventListener('click',() => { model = null
  renderRank()
  renderTasks()
})
function selectedLongRuns() {
  return data.long.map(r => longLimit === r.decision_limit ? r : (r.extensions || []).find(e => e.decision_limit === longLimit)).filter(Boolean).sort((a,b) => b.score - a.score)
}
$('long-limit').addEventListener('change', event => {
  longLimit = Number(event.target.value)
  renderLong()
  renderStatus()
})
function renderLong() {
  const limits = [...new Set(data.long.flatMap(r => [r.decision_limit,...(r.extensions || []).map(e => e.decision_limit)]))].sort((a,b) => a-b)
  $('long-limit').innerHTML = limits.map(n => `<option value="${n}" ${n === longLimit ? 'selected' : ''}>${count(n)} decisions</option>`).join('')
  const rows = selectedLongRuns()
  renderCost('long', rows)
  $('long-limit-label').textContent = count(longLimit)
  const tokenLimits = [...new Set(rows.map(r => r.token_limit || 30000000))].sort((a,b) => a-b)
  $('long-token-label').textContent = tokenLimits.map(million).join(' / ')
  $('long-comparison-note').textContent = longLimit === 2000 ? 'Original results stay fixed when a run is extended.' : `${rows.length} extended run(s). In-progress scores are provisional. Models without this allowance are omitted.`
  const open = new Set([...document.querySelectorAll('.long-run')].filter(el => el.querySelector('details').open).map(el => el.dataset.run))
  $('long-runs').innerHTML = rows.map(r => `<article class="long-run" data-run="${esc(r.id)}"><div class="run-top">${r.image ? `<img class="run-image" loading="lazy" src="${esc(r.image)}" alt="${esc(r.label)}'s recorded game screen" width="112" height="101">` : '<div></div>'}<div><h3 class="run-name">${esc(r.label)}</h3><div class="badges" aria-label="${r.badges} of 8 badges">${Array.from({length:8},(_,i) => `<span class="badge ${i < r.badges ? 'earned' : ''}" aria-hidden="true"></span>`).join('')}</div><p class="badge-count">${r.badges} / 8 badges</p></div><div class="run-score"><strong>${r.score}</strong><span> / ${r.maximum}</span><small>progress points</small></div><div class="run-budget">${count(r.decisions)} / ${count(r.decision_limit)} decisions<br>${million(r.tokens)} tokens<br>${costCell(r.cost)}<span>${esc(reason(r.stop_reason) || r.state)}</span></div><div>${r.replay ? `<a class="watch" target="_blank" rel="noopener" href="${esc(r.replay)}">▶ Watch run</a><span class="replay-size">Interactive replay · ${r.replay_mb} MB</span>` : r.report ? `<a class="watch" target="_blank" rel="noopener" href="${esc(r.report)}">View live run ↗</a>` : '<span class="small">Waiting to start</span>'}${(r.extensions || []).filter(e => e.report).map(e => `<a class="extension-link" href="${esc(e.report)}" target="_blank" rel="noopener">${count(e.decision_limit)}-decision extension ↗</a>`).join('')}</div></div><details class="run-bottom" ${open.has(r.id) ? 'open' : ''}><summary>${r.milestones.length} milestones · Latest: ${esc(r.milestones.at(-1)?.label || 'None yet')}</summary><div class="milestones">${r.milestones.map(m => `<span class="milestone">${esc(m.label)}<small>DECISION ${count(m.decision)} · +${m.points} PTS</small></span>`).join('')}</div></details></article>`).join('')
}

let costSort = {short:'score',long:'score'}
function renderCost(kind, selected) {
  const isLong = kind === 'long'
  const source = isLong ? selected || selectedLongRuns() : data.short.efficiency.models
  const rows = source.map(r => ({...r, quality:isLong ? r.score / 1000 : r.score,
    unitCost:isLong ? {low:r.score && r.cost?.low != null ? r.cost.low * 100 / r.score : null,high:r.score && r.cost?.high != null ? r.cost.high * 100 / r.score : null} : r.per_full_score,
    provisional:isLong ? r.state !== 'finished' || r.stop_reason === 'provider_error' || r.cost?.partial : r.partial}))
  rows.sort((a,b) => costSort[kind] === 'value' ? (a.unitCost.low ?? Infinity) - (b.unitCost.low ?? Infinity) : (b.quality ?? -1) - (a.quality ?? -1))
  const maxCost = Math.max(0,...rows.map(r => r.cost?.high || 0))
  const title = isLong ? 'Progress vs cost' : 'Performance vs cost'
  const quantity = isLong ? 'Run cost so far' : 'Mean cost / task'
  const valueLabel = isLong ? 'Cost / 100 points' : 'Cost / full-score equivalent'
  const sourceLinks = data.pricing.sources.map((url,i) => `<a href="${esc(url)}" target="_blank" rel="noopener">${['OpenAI rates','Terra','Luna','Opus','Sonnet','Haiku','Fable'][i]}</a>`).join(' · ')
  $(kind + '-cost').innerHTML = `<div class="cost-heading"><div><p class="eyebrow">WHAT DOES PERFORMANCE COST?</p><h3>${title}</h3></div><div class="filters" aria-label="Sort cost comparison"><button data-cost-kind="${kind}" data-cost-sort="score" aria-pressed="${costSort[kind] === 'score'}">Score</button><button data-cost-kind="${kind}" data-cost-sort="value" aria-pressed="${costSort[kind] === 'value'}">Value</button></div></div>
  <p class="small">${isLong ? `At the selected ${count(longLimit)}-decision allowance. Costs and progress stay cumulative.` : `${data.short.efficiency.starts} shared completed starts across all models. Failed tasks count toward cost. Scores here use this shared subset.`} Lower dollar values are better.</p>
  <div class="table-scroll"><table class="cost-table"><thead><tr><th>Model</th><th>${isLong ? 'Progress' : 'Shared score'}</th><th>${quantity}</th><th>${valueLabel}</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(r.label)}${r.provisional ? '<small class="partial-label">PROVISIONAL</small>' : ''}</td><td>${isLong ? count(r.score) + ' / 1,000' : pct(r.quality)}<span class="scorebar"><i style="width:${100*(r.quality || 0)}%"></i></span></td><td>${costCell({...r.cost,partial:r.cost?.partial || r.partial})}<span class="spendbar"><i style="width:${maxCost ? 100*(r.cost?.high || 0)/maxCost : 0}%"></i></span></td><td>${r.quality === 0 ? 'No score earned' : costRange(r.unitCost)}</td></tr>`).join('')}</tbody></table></div>
  <p class="small">Estimated API-equivalent USD, not your subscription bill. Ranges reflect uncertain cache-write pricing. ${isLong ? 'Live or incomplete usage is provisional.' : 'Value = category-balanced mean cost ÷ shared score. Preparation receives fractional credit.'}</p>
  <details class="cost-method"><summary>Pricing and calculation</summary><p>${esc(data.pricing.basis)} Verified ${esc(data.pricing.as_of)}. ${esc(data.pricing.range)}</p><p>Only the displayed attempts are priced. Earlier replaced trials and development runs are excluded. Calls interrupted by outages never reported usage. The high estimate prices each one at its full token reserve as output tokens; the low estimate excludes it. Missing usage without a reserve is marked partial, never free. Value ordering uses the low end of the estimate, and overlapping ranges may reverse that ordering. Lower cost does not imply better gameplay.</p><p>${sourceLinks}</p></details>`
}
for (const kind of ['short','long']) {
  $(kind + '-cost').addEventListener('click', event => {
    const button = event.target.closest('[data-cost-sort]')
    if (!button) return
    costSort[kind] = button.dataset.costSort
    renderCost(kind)
  })
}

function renderStatus() {
  const remaining = data.short.planned - data.short.finished
  $('snapshot').textContent = view === 'long' ? `${selectedLongRuns().filter(r => r.state === 'finished').length}/${selectedLongRuns().length} runs finished at this allowance` : remaining ? `${remaining} trials remaining · Results updating` : 'All trials finished'
}
async function refresh(first = false) {
  try {
    const response = await fetch('showcase-data.json',{cache:'no-store'})
    if (!response.ok) throw new Error('Missing results')
    const next = await response.json()
    data = next
    if (first) $('categories').innerHTML = ['all',...data.short.categories].map(c => `<button data-category="${c}" aria-pressed="${c === category}">${c === 'all' ? 'All tasks' : categoryNames[c]}</button>`).join('')
    renderRank()
    renderTasks()
    renderLong()
    renderStatus()
    $('updated').textContent = 'Updated ' + new Date(data.updated_at).toLocaleString()
    if ($('report-link')) $('report-link').hidden = !data.report
    $('load-error').hidden = true
  } catch(error) {
    if (!data) $('load-error').hidden = false
    $('snapshot').textContent = data ? 'Showing last saved results' : 'Results unavailable'
  }
}
$('retry').addEventListener('click',() => refresh(true))
refresh(true)
setInterval(() => refresh(false),60000)
