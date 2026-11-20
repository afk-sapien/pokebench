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
const shortTag = t => (t || '').match(/^[a-z]+-v\d+(?:\.\d+)*/)?.[0] || t || ''
const harnessCell = h => `<span class="harness-revision">${esc(h?.revisions?.join(' + ') || 'Unknown')}</span><span class="harness-version" title="${esc((h?.versions || []).join(', '))}">${esc(h?.label || '')}</span>`
const communityNote = c => c ? `<span class="community-note">${esc(c.label)}<br>Submitted by ${esc(c.handle || 'unnamed')}. ${count(c.attempts || 1)} declared attempt${(c.attempts || 1) === 1 ? '' : 's'}</span>` : ''
const maintainerNote = n => n ? `<span class="community-note maintainer-note" title="${esc(`Ran on package ${n.packages.join(' and ')}. Replay verified on ${n.release}. Report sha256 ${n.report_sha256}.`)}">${esc(n.label)}<br>${esc(n.detail)}</span>` : ''
const noteLabel = code => data.short.label_text?.[code] || {label: code.replaceAll('_',' '), detail: ''}
const noteTag = (code, detail) => `<span class="note-label" title="${esc(detail || noteLabel(code).detail)}">${esc(noteLabel(code).label)}</span>`
const modelNotes = labels => Object.entries(labels || {}).map(([code, n]) => `<span class="note-label" title="${esc(noteLabel(code).detail)}">${n} ${esc(noteLabel(code).label)}</span>`).join('')
const cellNotes = r => (r.labels || []).map(code => noteTag(code, code === 'harness_fault' ? r.harness_fault : null)).join('')
const cellMeta = r => [r.revision, r.harness && shortTag(r.harness), r.evaluation_spec_sha256 && 'spec ' + r.evaluation_spec_sha256.slice(0,8), r.policy_version].filter(Boolean).map(esc).join(' · ')
const ciText = ci => ci ? `95% CI ${(ci.low * 100).toFixed(1)} to ${(ci.high * 100).toFixed(1)}` : ''
// The summary holds no attempts. Each row marks, in task order, a 1 for every task it has an attempt on.
const taskIds = (rows, retired = false) => new Set(data.short.tasks.filter((t, i) => (retired || !t.retired) && rows.some(m => m.ran[i] === '1')).map(t => t.id))
// Attempts load one file at a time: a row's file when that row is picked, else a task's file when the task is opened.
const files = new Map()
function attempts(url) {
  if (!files.has(url)) {
    files.set(url, null)
    fetch(url).then(response => {
      if (!response.ok) throw new Error('Missing attempts')
      return response.json()
    }).then(rows => files.set(url, rows), error => files.set(url, error)).then(() => renderTasks())
  }
  return files.get(url)
}
const modelId = r => r.model || data.short.models.find(m => m.label === r.label)?.id || ''
function stopText(r) {
  if (r.stop_reason === 'model_call_budget') return `Used all ${count(r.decision_limit)} decisions.`
  if (r.stop_reason === 'token_budget') return `Reached the ${million(r.token_limit)} token ceiling.`
  if (r.stop_reason === 'provider_error') return 'The model provider failed and the run could not continue.'
  if (r.stop_reason === 'loop_token_budget') {
    const d = r.stop_detail || {}
    return `Stopped early after ${million(d.limit || 2000000)} tokens without reaching a new location or milestone${d.last_progress_decision ? `. Last progress at decision ${count(d.last_progress_decision)}` : ''}.`
  }
  return ''
}
const unranked = c => (data.short.unranked_categories || []).includes(c)
// A row's task set: the stored suite for a rerun row, else the scored earlier tasks its own attempts cover.
const taskSet = m => m.suite ? `${m.suite.tasks}-task ${shortTag(m.suite.benchmark)}` : `${taskIds([m]).size}-task earlier`
const splitSets = () => (data.short.models.some(m => m.suite) && data.short.models.some(m => !m.suite)) || new Set(data.short.models.map(taskSet)).size > 1
// With rows on the stored suite and rows on the earlier set, each set is a group of its own, the current set first.
// Every other page is one group with no title.
function rankGroups() {
  const s = data.short
  const earlier = s.models.filter(m => !m.suite)
  if (!s.models.some(m => m.suite) || !earlier.length) return [{rows: s.models}]
  const current = [...new Set(s.models.filter(m => m.suite).map(m => m.suite.benchmark))].map(benchmark => {
    const rows = s.models.filter(m => m.suite?.benchmark === benchmark)
    return {title: `Current set, ${shortTag(benchmark)}, ${rows[0].suite.tasks} tasks`, rows}
  })
  return [...current, {title: `Earlier set, ${taskIds(earlier).size} tasks`, rows: earlier}]
}
const setNote = m =>`<span class="note-label" title="${esc(m.suite ? `Scored on the ${m.suite.tasks} tasks of ${m.suite.benchmark}, from ${m.suite.source}.` : 'Scored on the earlier task set. Kept until this model has a complete rerun.')} Rows on different task sets are not strictly comparable.">${esc(taskSet(m))} set</span>`
function weightParts(rows, ranked) {
  const groups = {}
  const ran = taskIds(rows)
  for (const t of data.short.tasks) if (ran.has(t.id)) (groups[t.category] ||= new Set()).add(t.score_group || t.id)
  return ranked.map(c => `${categoryNames[c]} ${groups[c]?.size || 0} tasks, ${(100 / ranked.length / (groups[c]?.size || 1)).toFixed(1)} points each`).join(' · ')
}
function renderWeights() {
  const ranked = data.short.ranked_categories || data.short.categories
  const shown = (data.short.unranked_categories || []).map(c => categoryNames[c])
  let parts = ': ' + weightParts(data.short.models, ranked)
  if (splitSets()) {
    const setOf = new Map(data.short.models.map(m => [m.id, taskSet(m)]))
    parts = [...new Set(setOf.values())].map((name, i) => `${i ? ' On' : ', on'} the ${name} set: ${weightParts(data.short.models.filter(m => setOf.get(m.id) === name), ranked)}`).join('.')
  }
  $('weight-note').textContent = `Each of the ${ranked.length} ranked categories counts for ${(100 / ranked.length).toFixed(0)}% of the score, whatever its task count. Turning one failed task into a full pass moves the score by${parts}.${shown.length ? ` ${shown.join(', ')} is scored and shown, but not ranked.` : ''}`
}
function renderSuiteNote() {
  const s = data.short
  const split = splitSets()
  $('suite-note').hidden = !split
  if (!split) return
  const fresh = s.models.filter(m => m.suite)
  const newer = taskIds(fresh, true)
  const earlier = taskIds(s.models.filter(m => !m.suite), true)
  const both = [...newer].filter(t => earlier.has(t)).length
  const suitesOf = rows => [...new Set(rows.map(m => m.suite.benchmark))].map(shortTag).join(', ')
  const names = rows => rows.map(m => m.label).join(', ')
  const reruns = fresh.filter(m => !m.maintainer && !m.community)
  const extra = fresh.filter(m => m.maintainer)
  const community = fresh.filter(m => m.community)
  const grouped = rankGroups().length > 1
  const parts = [grouped ? 'Task sets differ between rows, so each set is ranked as its own group, the current set first.' : 'Task sets differ between rows.']
  if (reruns.length) parts.push(`${names(reruns)} ${reruns.length === 1 ? 'has' : 'have'} been rerun on the ${suitesOf(reruns)} Short suite.`)
  if (extra.length) parts.push(`${names(extra)} ${extra.length === 1 ? 'is a maintainer run' : 'are maintainer runs'} on the ${suitesOf(extra)} Short suite, ranked in the current set. ${extra.length === 1 ? 'That model\'s' : 'Each model\'s'} earlier row keeps its place in the earlier set.`)
  if (community.length) parts.push(`${names(community)} ${community.length === 1 ? 'is a community run' : 'are community runs'} on the ${suitesOf(community)} Short suite, ranked in the current set with ${community.length === 1 ? 'its' : 'their'} own label.`)
  parts.push(reruns.length ? 'Every other row keeps its earlier results until its own rerun is complete.' : 'The rows in the earlier set keep their earlier results.')
  $('suite-note').textContent = `${parts.join(' ')} The sets share ${both} tasks. Each row is scored only on its own set, with the categories weighted equally, so ${grouped ? 'scores in different groups' : 'ranks across different sets'} are not strictly comparable. In the task list, a row shows Not run for a task outside its set.`
}
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
  $('rank-head').innerHTML = '<tr><th>Model</th><th>Score</th>' + s.categories.map(c => `<th>${categoryNames[c]}${unranked(c) ? '<small class="partial-label">Not ranked</small>' : ''}</th>`).join('') + '<th>Finished</th><th>Harness</th><th>Est. cost</th></tr>'
  const split = splitSets()
  const ran = (m, c) => s.tasks.some((t, i) => m.ran[i] === '1' && t.category === c)
  const categoryCell = (m, c) => m.categories[c] == null && !ran(m, c) ? '<td title="Not in this row\'s task set">—</td>' : `<td>${pct(m.categories[c])}</td>`
  const rankCell = (m, rank) => `<span class="rank">${m.complete ? String(rank).padStart(2,'0') : '●'}</span>`
  // Each group is ranked on its own, so a row on one set moves no rank in the other.
  $('ranking').innerHTML = rankGroups().map(group => {
    let rank = 0
    const title = group.title ? `<tr class="set-row"><th colspan="${s.categories.length + 5}" scope="colgroup"><span>${esc(group.title)}</span></th></tr>` : ''
    return title + group.rows.map(m => row(m, m.complete ? ++rank : rank)).join('')
  }).join('')
  function row(m, rank) {
    return `<tr class="${m.complete ? '' : 'partial-row'} ${model === m.id ? 'selected-model' : ''}"><td>${rankCell(m, rank)}<button class="model-name" data-model="${esc(m.id)}" aria-pressed="${model === m.id}">${esc(m.label)}</button><span class="model-id">${esc(m.community ? m.community.model : m.maintainer ? m.maintainer.model : m.id)}</span>${communityNote(m.community)}${maintainerNote(m.maintainer)}</td><td><span class="score-value">${pct(m.score)}</span><span class="scorebar"><i style="width:${(m.score || 0) * 100}%"></i></span><span class="score-ci">${ciText(m.ci)}</span>${m.complete ? '' : '<span class="partial-label">PROVISIONAL</span>'}${split ? setNote(m) : ''}</td>${s.categories.map(c => categoryCell(m, c)).join('')}<td>${m.finished}/${m.planned}${m.errors ? `<span class="partial-label">${m.errors} errors</span>` : ''}${modelNotes(m.labels)}</td><td>${harnessCell(m.harness)}</td>${m.community ? `<td>${million(m.tokens)} tokens<small class="partial-label">SELF REPORTED</small></td>` : `<td title="${million(m.tokens)} reported tokens">${costCell(m.cost)}</td>`}</tr>`
  }
  renderCost('short')
  renderWeights()
  renderSuiteNote()
  renderAttempts()
  // With two task sets on the page, their union is a count no row ran, so each set's own size is shown.
  const sets = new Map()
  for (const m of [...s.models].sort((a, b) => !a.suite - !b.suite)) {
    const name = m.suite ? shortTag(m.suite.benchmark) + ' set' : 'earlier set'
    if (!sets.has(name)) sets.set(name, new Set())
    for (const id of taskIds([m])) sets.get(name).add(id)
  }
  const taskStats = split ? [...sets].map(([name, ids]) => [ids.size, name + ' tasks']) : [[s.tasks.filter(t => !t.retired).length,'tasks']]
  $('short-stats').innerHTML = [...taskStats,[new Set(s.models.map(m => m.maintainer ? m.maintainer.model : m.id)).size,'models'],[s.finished + '/' + s.planned,'trials finished']].map(([n,label]) => `<div><strong>${n}</strong><span>${label}</span></div>`).join('')
}
function renderAttempts() {
  const a = data.short.attempts || {rule: '', log: []}
  const label = id => data.short.models.find(m => m.id === id)?.label || id || 'Unknown'
  $('attempts-rule').textContent = a.rule
  $('attempts-body').innerHTML = a.log.map(e => `<tr><td>${esc(e.batch)} / ${esc(e.cell)}</td><td>${esc(label(e.model))}</td><td>${esc(e.task_id || '')}</td><td>${esc(e.kind)}</td><td>${esc(e.reason)}</td><td>${esc(reason(e.stop_reason) || 'Unknown')}${e.decisions != null ? ` after ${count(e.decisions)} decisions` : ''}</td></tr>`).join('') || '<tr><td colspan="6">No stopped or replaced attempts.</td></tr>'
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
  // Milestone tasks score the share of their ordered milestones reached, so a partial value shows as a share.
  return `<span class="state ${row.value === 0 ? 'fail' : ''}">${row.mode === 'preparation' || (row.value > 0 && row.value < 1) ? pct(row.value) : row.value === 1 ? 'Pass' : 'Fail'}</span>`
}
// A task's attempts: from the picked row's file, or from the task's own file once the task is opened.
// An array once loaded, an Error if the file failed, else null.
function taskAttempts(t, picked, open) {
  if (picked) {
    const rows = attempts(picked.cells)
    return Array.isArray(rows) ? rows.filter(c => c.task_id === t.id) : rows
  }
  if (!t.coverage.attempts) return []
  return open.has(t.id) || files.has(t.cells) ? attempts(t.cells) : null
}
function renderTasks() {
  const s = data.short
  const open = new Set([...document.querySelectorAll('.task[open]')].map(el => el.dataset.task))
  // A render replaces every task, so focus goes back to the task it was on.
  const focused = document.activeElement?.closest?.('.task')?.dataset.task
  const picked = model && s.models.find(m => m.id === model)
  const query = $('search').value.trim().toLowerCase()
  const tasks = s.tasks.filter(t => (category === 'all' || t.category === category) && `${t.title} ${t.goal} ${t.start}`.toLowerCase().includes(query))
  const shown = expanded || query || category !== 'all' ? tasks : tasks.slice(0,12)
  $('task-count').textContent = `${shown.length} of ${tasks.length} tasks` + (model ? ' · ' + s.models.find(m => m.id === model).label : ' · Open a task to compare attempts and watch replays')
  $('model-filter').hidden = !model
  if (model) $('model-filter').textContent = s.models.find(m => m.id === model).label + ' only ×'
  $('show-all').hidden = shown.length === tasks.length
  $('show-all').textContent = `Show all ${tasks.length} tasks ↓`
  const split = splitSets()
  $('tasks').innerHTML = shown.map(t => {
    const i = s.tasks.indexOf(t)
    const found = taskAttempts(t, picked, open)
    const rows = Array.isArray(found) ? [...found].sort((a,b) => s.models.findIndex(m => m.id === a.model) - s.models.findIndex(m => m.id === b.model)) : null
    const coverage = picked ? rows ? `${rows.filter(c => c.state === 'finished').length}/${rows.length} finished` : found ? 'Not loaded' : 'Loading…' : `${t.coverage.finished}/${t.coverage.attempts} finished`
    const pending = `<tr><td colspan="7"><span class="small">${found ? 'Attempts could not be loaded. Close and open the task to try again.' : 'Loading attempts…'}</span></td></tr>`
    // With mixed task sets, a row that never ran this task gets an empty line instead of disappearing.
    const missing = split ? s.models.filter(m => (!model || m.id === model) && m.ran[i] !== '1') : []
    const policy = t.mode === 'preparation' ? 'Team and resource choices, assessed by a fixed battle controller.' : (t.action_policy || '').includes('manual') ? 'Manual controls. Menu shortcuts disabled.' : 'Game information and mechanical shortcuts enabled.'
    return `<details class="task" data-task="${esc(t.id)}" ${open.has(t.id) ? 'open' : ''}><summary><span class="tag">${categoryNames[t.category]}${t.retired ? ' · Retired, not scored' : unranked(t.category) ? ' · Not ranked' : ''}${t.suite ? ' · Added in ' + esc(shortTag(t.suite)) : ''}</span><span class="task-title">${esc(t.title)}</span><span class="task-coverage">${coverage}</span></summary><div class="task-body">${t.retired ? `<p class="small"><strong>Retired:</strong> ${esc(t.retirement_reason || 'No longer run or scored.')}</p>` : ''}<p><strong>Goal:</strong> ${esc(t.goal)}</p><p><strong>Start:</strong> ${esc(t.start)}</p><p class="small">${policy}${t.milestones ? ` Scored by the share of its ${t.milestones} ordered milestones reached.` : ''}</p><div class="table-scroll"><table><thead><tr><th>Model / start</th><th>Result</th><th>Decisions</th><th>Tokens</th><th>Est. cost</th><th>End reason</th><th>Replay</th></tr></thead><tbody>${rows ? rows.map(r => `<tr><td>${esc(s.models.find(m => m.id === r.model).label)}${r.variant !== 'default' ? ' / ' + esc(r.variant) : ''}<span class="model-id">${cellMeta(r)}</span>${cellNotes(r)}</td><td>${rowStatus(r)}</td><td>${count(r.decisions)} / ${count(r.decision_limit)}</td><td title="Ceiling: ${count(r.token_limit)} tokens">${million(r.tokens)}</td><td>${costCell(r.cost)}</td><td>${r.state === 'finished' ? esc(reason(r.stop_reason) || 'Preparation assessed') : esc(r.state.replaceAll('_',' '))}</td><td>${r.replay ? `<a class="replay-link" target="_blank" rel="noopener" href="${esc(r.replay)}">Watch ↗</a>` : r.mode === 'preparation' ? '<span class="small">Preparation score</span>' : r.revision === 'Maintainer run' ? '<span class="small" title="The recorded run was replayed and matched. Its replay page is not published yet.">Verified, not published</span>' : '<span class="small">Not available yet</span>'}</td></tr>`).join('') : pending}${missing.map(m => `<tr class="not-run"><td>${esc(m.label)}<span class="model-id">${esc(taskSet(m))} set</span></td><td colspan="6"><span class="small">Not run. This task is not in this row's task set.</span></td></tr>`).join('')}</tbody></table></div></div></details>`
  }).join('') || '<p class="empty">No matching tasks. Try another search or category.</p>'
  if (focused) [...$('tasks').children].find(el => el.dataset.task === focused)?.querySelector('summary')?.focus({preventScroll: true})
  rendered = open
}
// The tasks the last render drew open. A task drawn open fires its own toggle, which is not a visitor opening it.
let rendered = new Set()
// A task's attempts load the first time it is opened. A file that failed loads again on the next open.
$('tasks').addEventListener('toggle', event => {
  const id = event.target.dataset?.task
  if (!event.target.open) return rendered.delete(id)
  if (rendered.has(id)) return
  rendered.add(id)
  const t = data.short.tasks.find(t => t.id === id)
  if (!t || (!model && !t.coverage.attempts)) return
  const url = model ? data.short.models.find(m => m.id === model).cells : t.cells
  if (files.get(url) instanceof Error) files.delete(url)
  if (!files.has(url)) renderTasks()
}, true)
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
  $('long-comparison-note').textContent = longLimit === 2000 ? 'Ranked at 2,000 decisions. Original results stay fixed when a run is extended.' : `${rows.length} extended run(s), not ranked. Only models run before v0.61 have extensions. New models get none. In-progress scores are provisional.`
  const open = new Set([...document.querySelectorAll('.long-run')].filter(el => el.querySelector('details').open).map(el => el.dataset.run))
  $('long-runs').innerHTML = rows.map(r => `<article class="long-run" data-run="${esc(r.id)}"><div class="run-top">${r.image ? `<img class="run-image" loading="lazy" src="${esc(r.image)}" alt="${esc(r.label)}'s recorded game screen" width="112" height="101">` : '<div></div>'}<div><h3 class="run-name">${esc(r.label)}</h3><span class="run-model">${esc(modelId(r))}${r.harness ? ` · harness <span title="${esc(r.harness)}">${esc(shortTag(r.harness))}</span>` : ''}</span><div class="badges" aria-label="${r.badges} of 8 badges">${Array.from({length:8},(_,i) => `<span class="badge ${i < r.badges ? 'earned' : ''}" aria-hidden="true"></span>`).join('')}</div><p class="badge-count">${r.badges} / 8 badges</p></div><div class="run-score"><strong>${r.score}</strong><span> / ${r.maximum}</span><small>progress points</small></div><div class="run-budget">${count(r.decisions)} / ${count(r.decision_limit)} decisions<br>${million(r.tokens)} tokens<br>${costCell(r.cost)}<span class="stop-reason">Stop: ${esc(reason(r.stop_reason) || r.state)}</span><span class="stop-detail">${esc(stopText(r))}</span>${r.pair_blocks?.pair ? `<span class="stop-detail" title="Before v0.61 the local map drew both tiles of a pair as floor.">${count(r.pair_blocks.pair)} of ${count(r.pair_blocks.blocked)} blocked moves hit a tile pair the map did not show.</span>` : ''}</div><div>${r.replay ? `<a class="watch" target="_blank" rel="noopener" href="${esc(r.replay)}">▶ Watch run</a><span class="replay-size">Interactive replay · ${r.replay_mb} MB</span>` : r.report ? `<a class="watch" target="_blank" rel="noopener" href="${esc(r.report)}">View live run ↗</a>` : '<span class="small">Waiting to start</span>'}${(r.extensions || []).filter(e => e.report).map(e => `<a class="extension-link" href="${esc(e.report)}" target="_blank" rel="noopener">${count(e.decision_limit)}-decision extension ↗</a>`).join('')}</div></div><details class="run-bottom" ${open.has(r.id) ? 'open' : ''}><summary>${r.milestones.length} milestones · Latest: ${esc(r.milestones.at(-1)?.label || 'None yet')}</summary><div class="milestones">${r.milestones.map(m => `<span class="milestone">${esc(m.label)}<small>DECISION ${count(m.decision)} · +${m.points} PTS</small></span>`).join('')}</div></details></article>`).join('')
}

function costSetNote() {
  const reruns = data.short.models.filter(m => m.suite && !m.maintainer && !m.community)
  const extra = data.short.models.filter(m => m.maintainer)
  return (reruns.length ? ' These shared starts were fixed before the reruns, so a rerun moves only its own row. A rerun row is priced on its own attempts at the same starts.' : '') +
    (extra.length ? ` ${extra.map(m => m.label).join(', ')} ${extra.length === 1 ? 'is a maintainer run' : 'are maintainer runs'} on a newer harness and ${extra.length === 1 ? 'stays' : 'stay'} out of this comparison.` : '')
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
  <p class="small">${isLong ? `At the selected ${count(longLimit)}-decision allowance. Costs and progress stay cumulative.` : `${data.short.efficiency.starts} shared completed starts across all models. Failed tasks count toward cost. Scores here use this shared subset.${costSetNote()}`} Lower dollar values are better.</p>
  <div class="table-scroll"><table class="cost-table"><thead><tr><th>Model</th><th>${isLong ? 'Progress' : 'Shared score'}</th><th>${quantity}</th><th>${valueLabel}</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(r.label)}${r.provisional ? '<small class="partial-label">PROVISIONAL</small>' : ''}${!isLong && r.starts !== data.short.efficiency.starts ? `<small class="partial-label">${r.starts} OF ${data.short.efficiency.starts} STARTS</small>` : ''}</td><td>${isLong ? count(r.score) + ' / 1,000' : pct(r.quality)}<span class="scorebar"><i style="width:${100*(r.quality || 0)}%"></i></span></td><td>${costCell({...r.cost,partial:r.cost?.partial || r.partial})}<span class="spendbar"><i style="width:${maxCost ? 100*(r.cost?.high || 0)/maxCost : 0}%"></i></span></td><td>${r.quality === 0 ? 'No score earned' : costRange(r.unitCost)}</td></tr>`).join('')}</tbody></table></div>
  <p class="small">Estimated API-equivalent USD, not your subscription bill. Ranges reflect uncertain cache-write pricing. ${isLong ? 'Live or incomplete usage is provisional.' : 'Value = category-balanced mean cost ÷ shared score, over the ranked categories. Preparation is left out.'}</p>
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

// The hosted cost guide: the token caps of a Short run on the current set and what the priced runs on it used.
function renderSubmitCost() {
  const s = data.short
  const runs = s.models.filter(m => m.suite && !m.community && m.cost?.low != null)
  if (!runs.length) return
  // One decimal, as the plan prints it.
  const tokens = x => (x / 1e6).toFixed(1) + 'M'
  const worst = runs[0].token_cap || 0
  const used = runs.map(m => `${esc(m.maintainer ? m.maintainer.model : m.id)} used ${tokens(m.tokens)}, an estimated ${costRange(m.cost)} at API list prices`).join('. ')
  // One run's summed play time, as an example. Only a maintainer row records it.
  const timed = runs.find(m => m.maintainer?.wall_seconds > 0)
  const span = w => w >= 5400 ? `${Math.round(w / 3600)} hours` : `${Math.max(1, Math.round(w / 60))} minutes`
  const time = timed ? `<p><strong>Time:</strong> one example, not a promise. The published ${esc(timed.maintainer.model)} run played the whole Short suite, one task at a time, in about ${span(timed.maintainer.wall_seconds)}. Yours depends on the model, its provider and your machine.</p>` : ''
  $('submit-cost').innerHTML = `<p><strong>Local model:</strong> free. It uses only your own computer.</p><p><strong>Hosted model:</strong> up to ${tokens(worst)} tokens, input plus output, the sum of every task's own cap. Published runs on this task set: ${used}. Through a Claude Code or Codex login the run counts against that account's usage like any other session.</p>${time}`
}
function renderStatus() {
  const remaining = data.short.planned - data.short.finished
  $('snapshot').textContent = view === 'long' ? `${selectedLongRuns().filter(r => r.state === 'finished').length}/${selectedLongRuns().length} runs finished at this allowance` : remaining ? `${remaining} trials remaining · Results updating` : 'All trials finished'
}
async function refresh(first = false) {
  try {
    const response = await fetch('showcase-summary.json',{cache:'no-store'})
    if (!response.ok) throw new Error('Missing results')
    const next = await response.json()
    data = next
    for (const [url, rows] of files) if (rows instanceof Error) files.delete(url)
    if (first) $('categories').innerHTML = ['all',...data.short.categories].map(c => `<button data-category="${c}" aria-pressed="${c === category}">${c === 'all' ? 'All tasks' : categoryNames[c]}</button>`).join('')
    renderRank()
    renderTasks()
    renderLong()
    renderStatus()
    renderSubmitCost()
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
