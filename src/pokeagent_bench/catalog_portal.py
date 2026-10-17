"""Local and exported visual explorer for prospective evaluation specifications."""
from html import escape
import json
from pathlib import Path

from .evaluation_catalog import summary
from .benchmark_tracks import SHORT, LONG, NAMES

LABELS = {
    'navigation': ('Navigation', 'Route finding and spatial puzzles', '01'),
    'battle': ('Battle tactics', 'Matchups, switching and tactical recovery', '02'),
    'operations': ('Menu operations', 'Exact commands without shortcuts', '03'),
    'preparation': ('Preparation', 'Team building and resource choices', '04'),
    'objectives': ('Quests', 'NPC instructions and quest dependencies', '05'),
    'campaign': ('Full-game campaign', 'One attempt with a progress checklist', '06'),
}


def _list(values):
    return '<ul>' + ''.join('<li>' + escape(value) + '</li>' for value in values) + '</ul>'


def render_catalog(data=None):
    data = data if data is not None else summary(benchmark=SHORT)
    benchmark = data.get('benchmark') or SHORT
    cards, groups = [], []
    for group in data['categories']:
        key = group['category']
        title, subtitle, number = LABELS[key]
        primary_count = sum(not task.get('variant_of') for task in group['evals'])
        variant_count = len(group['evals']) - primary_count
        count_label = f'{primary_count} task' + ('s' if primary_count != 1 else '') + (f' + {variant_count} variant' if variant_count else '')
        cards.append(f'<button class="category" data-category="{key}" aria-pressed="false">'
                     f'<span class="category-top"><span>{number}</span><span>{count_label}</span></span>'
                     f'<strong>{title}</strong><span>{subtitle}</span></button>')
        rows = []
        for index, task in enumerate(group['evals'], 1):
            source = task['existing_task']
            controls = 'Manual inputs' if key == 'operations' else 'Preparation choices' if key == 'preparation' else 'Shortcuts allowed'
            objective = task['objective']
            implementation = task.get('implementation')
            state_label = 'Runnable' if implementation and implementation['runnable'] else 'Setup pending' if implementation else 'Specified'
            scoring = ('Runtime grader implemented' if implementation else
                       'Existing objective available' if objective else 'Grader work needed')
            search = escape(' '.join([task['title'], key, title, task['difficulty'], task['start'], *task['success'], task.get('agent_goal', ''), *task.get('scenario_details', [])]).lower())
            source_text = ('Candidate source: ' + escape(source)) if source else 'New checkpoint needed'
            if implementation:
                source_text = (str(implementation['start_variants']) + ' checked start variants. ' +
                               str(implementation['reference_variants']) + ' completed native reference replays.')
                reference = implementation.get('preparation_reference')
                if reference:
                    source_text += (' Preparation actions verified. Fixed-controller native smoke: ' +
                                    str(reference['wins']) + ' / ' + str(reference['trials']) +
                                    ' battles won, ' + str(reference['evaluation_errors']) + ' evaluator errors. These are not model scores.')
            badge = f'<span class="difficulty {task["difficulty"]}">Estimate: {task["difficulty"].capitalize()}</span>'
            variant_parent = task.get('variant_of', '')
            variant_note = ('<p class="variant-note">Inventory variant of <a href="#' + escape(variant_parent) + '">the inventory checklist</a>. Shares that task’s weight in category scores.</p>') if variant_parent else ''
            purpose = ('<h4>What this tests</h4><p>' + escape(task['measures']) + '</p>') if task.get('measures') else ''
            solution = ('<h4>Expected solution (reviewer explanation)</h4><p>' + escape(task['expected_solution']) + '</p><p>This explanation is not added to the agent instruction.</p>') if task.get('expected_solution') else ''
            scenario = purpose + solution + '<h4>Concrete setup</h4>' + _list(task.get('scenario_details', []))
            if task.get('milestones'):
                scenario += '<h4>Milestones within this one attempt</h4>'
                plan = task.get('scoring_plan')
                if plan:
                    score_state = 'Campaign score' if implementation else 'Proposed campaign score'
                    score_status = 'Runtime tracking is implemented.' if implementation else 'Scoring integration is pending.'
                    scenario += '<p><strong>' + score_state + ': ' + str(plan['maximum_points']) + ' points across ' + str(len(task['milestones'])) + ' milestones.</strong> ' + score_status + '</p>'
                    for scoring_group in plan['groups']:
                        scenario += '<h4>' + escape(scoring_group['label']) + ' · ' + str(scoring_group['points']) + ' points</h4>'
                        scenario += _list([m['label'] + ' (' + str(m['points']) + ' points)' for m in task['milestones'] if m['group'] == scoring_group['id']])
                    scenario += '<h4>How the score works</h4>' + _list(plan['rules'])
                    scenario += '<h4>Run profile: measured separately from points</h4>'
                    scenario += _list([m['label'] + ': ' + m['measure'] + ' Availability: ' + m['availability'] for m in task.get('run_metrics', [])])
                else:
                    scenario += _list([m['label'] for m in task['milestones']])
            questions = '<h4>Still to verify</h4>' + _list(task.get('open_questions', []))
            if implementation:
                questions = '<h4>Validation</h4><p>Model difficulty calibration is pending.</p>'
                if implementation['issues']:
                    questions += _list(implementation['issues'])
            footnote = ('Executable Gen 1 task. Reference verification and model difficulty calibration are separate. Historical results remain available on the leaderboard.'
                        if implementation else 'Specification only. Saves and scoring still need validation. Difficulty is a design target, not a measured pass rate. Existing results are not assigned to this new specification.')
            instruction_label = 'Agent instruction' if implementation else 'Planned agent instruction'
            goal = escape(task.get('agent_goal', task['title']))
            rows.append(f'''<details class="task" id="{task['id']}" data-variant="{variant_parent}" data-search="{search}">
<summary><span class="number">{index:02d}</span><span class="task-title">{"Variant: " if variant_parent else ""}{escape(task['title'])}</span>{badge}<span class="task-state">{state_label}</span><span class="expand" aria-hidden="true">+</span></summary>
<div class="task-body">{variant_note}<div class="task-meta"><span>{controls}</span><span>{task.get('decision_limit', 10000):,} decisions / {task['token_limit']:,} token backstop</span><a href="#{task['id']}">Link to task</a></div>
<p class="start"><strong>{instruction_label}</strong><br>{goal}</p>
<p class="start"><strong>Starting situation</strong><br>{escape(task['start'])}</p>
<div class="detail-grid"><section>{scenario}<h4>What counts as success</h4>{_list(task['success'])}<h4>What counts as failure</h4>{_list(task['failure'])}</section>
<section><h4>Build status</h4><p>{scoring}<br>{source_text}</p>{'' if implementation else _list(task['requirements'])}<h4>Starting variants</h4>{_list(task['variants'])}{questions}</section></div>
<p class="footnote">{footnote}</p></div></details>''')
        groups.append(f'<section class="group" data-group="{key}"><div class="group-heading"><div><span class="eyebrow">CATEGORY {number}</span><h2>{title}</h2><p>{subtitle}</p></div><span class="group-count">{count_label}</span></div>' + ''.join(rows) + '</section>')
    page = PAGE.replace('__CARDS__', ''.join(cards)).replace('__GROUPS__', ''.join(groups)).replace('__COUNT__', str(data['eval_count'])).replace('__PRIMARY__', str(data.get('primary_task_count', data['eval_count']))).replace('__VARIANTS__', str(data.get('variant_count', 0))).replace('__CATEGORY_COUNT__', str(data['category_count'])).replace('__TRACK__', benchmark)
    if data.get('status') == 'implemented':
        page = page.replace('task drafts', 'tasks')
        page = page.replace('Explore the full task plan. Choose a category or search, then open any task to see its goal, rules and what remains to build.',
                            'Explore the implemented tasks. Choose a category or search, then open a task to see its goal, controls, starting setup and validation status.')
        start = page.index('<div class="notice">')
        end = page.index('</div>', start) + len('</div>')
        page = (page[:start] + '<div class="notice"><strong>' + str(data['runnable_new_evals']) +
                ' / ' + str(data['eval_count']) + ' runnable starts.</strong> ' +
                str(data.get('reference_verified_evals', 0)) +
                ' tasks have completed native reference replays. Model calibration is pending.</div>' + page[end:])
    short_current = ' aria-current="page"' if benchmark == SHORT else ''
    long_current = ' aria-current="page"' if benchmark == LONG else ''
    navigation = ('<a href="index.html">Results &amp; replays</a>' +
                  '<a href="catalog.html"' + short_current + '>PokeBench</a>' +
                  '<a href="pokebench-long.html"' + long_current + '>PokeBench Long</a>')
    page = page.replace('<nav aria-label="Main"><a href="index.html">Results &amp; replays</a><a href="catalog.html" aria-current="page">Task catalog</a></nav>',
                        '<nav aria-label="Main">' + navigation + '</nav>')
    page = page.replace('<title>PokeBench | Task catalog</title>', '<title>' + NAMES[benchmark] + ' | Tasks</title>')
    page = page.replace('<h1>What are we testing?</h1>', '<h1>' + NAMES[benchmark] + '</h1>')
    if benchmark == LONG:
        description = 'One continuous Pokemon Red run, from the bedroom to Champion. Score progress across 50 milestones worth 1,000 points, with tokens, elapsed time and the final team reported alongside completion.'
        page = page.replace('<span>tasks in __CATEGORY_COUNT__ categories + __VARIANTS__ inventory variant</span>', '<span>continuous campaign</span>')
        page = page.replace('<span>tasks in 1 categories + 0 inventory variant</span>', '<span>continuous campaign</span>')
        page = page.replace('<details class="task"', '<details open class="task"')
        page = page.replace('href="catalog.json"', 'href="pokebench-long.json"')
        page = page.replace('</style>', '.categories {display:none}\n.toolbar {display:none}\n</style>')
    else:
        description = 'Focused Pokemon Red tasks across navigation, battle tactics, menu operations, preparation and quests. Compare these skills here. Full-game campaigns have their own PokeBench Long scores and budget.'
    for original in (
        'Explore the full task plan. Choose a category or search, then open any task to see its goal, rules and what remains to build.',
        'Explore the implemented tasks. Choose a category or search, then open a task to see its goal, controls, starting setup and validation status.'):
        page = page.replace(original, description)
    return page


def export_catalog(output, fixtures=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    count = 0
    for benchmark, stem in ((SHORT, 'catalog'), (LONG, 'pokebench-long')):
        data = summary(fixtures=fixtures, benchmark=benchmark)
        (output / (stem + '.html')).write_text(render_catalog(data))
        (output / (stem + '.json')).write_text(json.dumps(data, indent=2) + '\n')
        count += data['eval_count']
    return count



PAGE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PokeBench | Task catalog</title>
<style>
:root {color-scheme:light}
* {box-sizing:border-box}
body {margin:0}
body {background:#f7f8f5}
body {color:#1e302a}
body {font:15px/1.6 system-ui,sans-serif}
a {color:#236748}
button,input {font:inherit}
button {cursor:pointer}
button,a,input,summary {outline-offset:4px}
[hidden] {display:none!important}
header {background:#fff}
header {border-bottom:1px solid #dce3dc}
.header-inner {max-width:1240px}
.header-inner {margin:auto}
.header-inner {padding:19px 32px}
.header-inner {display:flex}
.header-inner {align-items:center}
.header-inner {justify-content:space-between}
.brand {font-size:23px}
.brand {font-weight:800}
.brand {text-decoration:none}
.brand {color:#183c2d}
header nav {display:flex}
header nav {gap:24px}
header nav a {text-decoration:none}
header nav a[aria-current] {font-weight:700}
main {max-width:1240px}
main {margin:auto}
main {padding:40px 32px 70px}
.hero {display:flex}
.hero {justify-content:space-between}
.hero {gap:30px}
.eyebrow {font-size:11px}
.eyebrow {font-weight:750}
.eyebrow {letter-spacing:1.6px}
.eyebrow {color:#567061}
h1 {font-size:42px}
h1 {letter-spacing:-1.5px}
h1 {line-height:1.15}
h1 {margin:10px 0 15px}
.hero p {max-width:660px}
.hero p {color:#52645a}
.hero p {margin:0}
.count {text-align:right}
.count strong {font-size:48px}
.count strong {line-height:1.1}
.count span {display:block}
.count span {color:#647568}
.notice {border-left:3px solid #ad8545}
.notice {background:#f0eee5}
.notice {padding:12px 18px}
.notice {margin:26px 0}
.notice {color:#62563d}
.categories {display:grid}
.categories {grid-template-columns:repeat(3,minmax(0,1fr))}
.categories {gap:12px}
.category {text-align:left}
.category {border:1px solid #d9e2d9}
.category {border-radius:9px}
.category {padding:16px 18px}
.category {background:white}
.category {color:inherit}
.category {transition:background .12s}
.category:hover {background:#eff5ef}
.category[aria-pressed=true] {border-color:#28734d}
.category[aria-pressed=true] {background:#e7f1e8}
.category[aria-pressed=true] {box-shadow:inset 0 0 0 1px #28734d}
.category-top {display:flex}
.category-top {justify-content:space-between}
.category-top {font-size:11px}
.category-top {color:#657b6b}
.category strong {display:block}
.category strong {font-size:18px}
.category strong {margin-top:7px}
.category>span:last-child {font-size:13px}
.category>span:last-child {color:#586e60}
.toolbar {position:sticky}
.toolbar {top:0}
.toolbar {z-index:2}
.toolbar {display:flex}
.toolbar {gap:12px}
.toolbar {align-items:center}
.toolbar {padding:20px 0 14px}
.toolbar {background:#f7f8f5}
.search {flex:1}
.search {position:relative}
.search input {width:100%}
.search input {border:1px solid #ccd9ce}
.search input {border-radius:7px}
.search input {background:white}
.search input {padding:11px 15px}
.toolbar button {padding:11px 16px}
.toolbar button {border:1px solid #ccd9ce}
.toolbar button {border-radius:7px}
.toolbar button {background:white}
.toolbar button[aria-pressed=true] {background:#224e38}
.toolbar button[aria-pressed=true] {color:white}
#visible-count {color:#536c5b}
#visible-count {min-width:100px}
#visible-count {font-size:13px}
.group {margin-top:26px}
.group-heading {display:flex}
.group-heading {justify-content:space-between}
.group-heading {align-items:end}
.group-heading {padding:0 0 16px}
h2 {font-size:24px}
h2 {margin:0}
.group-heading p {margin:0}
.group-heading p {color:#617367}
.group-count {font-size:13px}
.group-count {color:#68786d}
.task {background:white}
.task {border:1px solid #dfe5de}
.task {border-bottom:0}
.task:last-child {border-bottom:1px solid #dfe5de}
.task summary {display:grid}
.task summary {grid-template-columns:30px 1fr 82px 70px 18px}
.task summary {gap:14px}
.task summary {align-items:center}
.task summary {padding:17px 20px}
.task summary {cursor:pointer}
.task summary {list-style:none}
.task summary::-webkit-details-marker {display:none}
.task summary:hover {background:#f5f8f4}
.number {color:#819184}
.number {font-size:12px}
.task-title {font-weight:600}
.task-state {font-size:12px}
.task-state {color:#7b6a46}
.difficulty {font-size:11px}
.difficulty {text-align:center}
.difficulty {padding:3px 8px}
.difficulty {border-radius:4px}
.easy {background:#e9f1e5}
.easy {color:#406440}
.medium {background:#e8eef5}
.medium {color:#456484}
.hard {background:#f4ecdc}
.hard {color:#846426}
.stretch {background:#eee7f3}
.stretch {color:#77508b}
.expand {font-size:21px}
.expand {color:#617b66}
details[open] .expand {transform:rotate(45deg)}
details[open] summary {background:#f0f5ef}
.task-body {padding:8px 28px 22px 64px}
.task-meta {display:flex}
.task-meta {gap:18px}
.task-meta {flex-wrap:wrap}
.task-meta {font-size:12px}
.task-meta {color:#5b7463}
.task-meta {padding:9px 0}
.start {color:#40574a}
.detail-grid {display:grid}
.detail-grid {grid-template-columns:1fr 1fr}
.detail-grid {gap:36px}
h4 {margin:10px 0}
h4 {font-size:13px}
h4 {color:#244c36}
ul {padding-left:20px}
ul {margin:5px 0 18px}
li {margin:6px 0}
.detail-grid p,.detail-grid li {font-size:13px}
.footnote {color:#788577}
.footnote {font-size:12px}
.footnote {border-top:1px solid #e4e9e1}
.footnote {padding-top:12px}
#empty {padding:45px}
#empty {text-align:center}
footer {margin-top:32px}
footer {color:#657568}
footer {font-size:13px}
@media(max-width:760px) {
main {padding:25px 16px}
.header-inner {padding:16px}
header nav {gap:14px}
header nav a {font-size:13px}
h1 {font-size:32px}
.categories {grid-template-columns:repeat(2,minmax(0,1fr))}
.category {padding:13px}
.category strong {font-size:16px}
.category>span:last-child {font-size:12px}
.count {display:none}
.task summary {grid-template-columns:1fr 70px 14px}
.task summary {padding:14px}
.task summary {gap:8px}
.number,.task-state {display:none}
.task-title {font-size:14px}
.task-body {padding:10px 16px}
.task[data-variant]:not([data-variant=""]) {margin-left:24px}
.variant-note {background:#edf4ed}
.variant-note {padding:12px}
.detail-grid {grid-template-columns:1fr}
.detail-grid {gap:0}
#visible-count {min-width:70px}
.toolbar {gap:8px}
.toolbar button {padding:11px}
}
</style></head><body>
<header><div class="header-inner"><a class="brand" href="index.html">PokeBench</a><nav aria-label="Main"><a href="index.html">Results &amp; replays</a><a href="catalog.html" aria-current="page">Task catalog</a></nav></div></header>
<main><div class="hero"><div><span class="eyebrow">GEN 1 / BENCHMARK EXPLORER</span><h1>What are we testing?</h1><p>Explore the full task plan. Choose a category or search, then open any task to see its goal, rules and what remains to build.</p></div><div class="count"><strong>__PRIMARY__</strong><span>tasks in __CATEGORY_COUNT__ categories + __VARIANTS__ inventory variant</span></div></div>
<div class="notice"><strong>__COUNT__ task drafts · save validation pending.</strong> Focused tests isolate skills. The full-game campaign records milestones from one attempt. Existing results and replays remain on the results page.</div>
<nav class="categories" aria-label="Task categories">__CARDS__</nav>
<div class="toolbar"><button id="all" aria-pressed="true">All tasks</button><label class="search"><input type="search" id="search" aria-label="Search tasks" placeholder="Search tasks, goals or difficulty..."></label><span id="visible-count" role="status" aria-live="polite">__COUNT__ tasks</span></div>
<div id="groups">__GROUPS__</div><p id="empty" hidden>No matching tasks. Try another search or choose All tasks.</p>
<footer>Difficulty and token caps are provisional. Preparation uses a shared battle evaluator after the agent submits its choices. <a href="catalog.json" download>Download task specifications</a></footer>
<noscript><p>All tasks are shown. Open any task to read its details. Search and category filtering require JavaScript.</p></noscript></main>
<script>
const benchmarkTrack = '__TRACK__'
const cards = [...document.querySelectorAll('[data-category]')]
const groups = [...document.querySelectorAll('[data-group]')]
const tasks = [...document.querySelectorAll('.task')]
const search = document.getElementById('search')
const all = document.getElementById('all')
let selected = 'all'
function render() {
 const query = search.value.trim().toLowerCase()
 let count = 0
 groups.forEach(group => {
  let inGroup = 0
  let variants = 0
  group.querySelectorAll('.task').forEach(task => {
   const visible = (selected === 'all' || selected === group.dataset.group) && task.dataset.search.includes(query)
   task.hidden = !visible
   if (visible) {
    inGroup++
    if (task.dataset.variant) variants++
   }
  })
  group.hidden = inGroup === 0
  group.querySelector('.group-count').textContent = `${inGroup - variants} task${inGroup - variants === 1 ? '' : 's'}${variants ? ' + ' + variants + ' variant' : ''}`
  count += inGroup
 })
 cards.forEach(card => card.setAttribute('aria-pressed', String(card.dataset.category === selected)))
 all.setAttribute('aria-pressed', String(selected === 'all'))
 document.getElementById('visible-count').textContent = `${count} of ${tasks.length} task cases`
 document.getElementById('empty').hidden = count !== 0
}
function pick(category) {
 selected = category
 history.replaceState(null, '', category === 'all' ? location.pathname : '#category-' + category)
 render()
}
cards.forEach(card => card.addEventListener('click', () => pick(card.dataset.category)))
all.addEventListener('click', () => { search.value = ''
 pick('all')
})
search.addEventListener('input', render)
function fromHash() {
 const hash = location.hash.slice(1)
 if (benchmarkTrack === 'pokebench' && (hash === 'campaign-full-game' || hash === 'category-campaign')) {
  location.replace('pokebench-long.html#' + hash)
  return
 }
 const id = hash === 'category-quests' ? 'category-objectives' : hash
 const category = cards.find(card => 'category-' + card.dataset.category === id)
 const task = tasks.find(row => row.id === id)
 if (category) selected = category.dataset.category
 else if (task) {
  selected = task.closest('[data-group]').dataset.group
  search.value = ''
  task.open = true
 } else selected = 'all'
 render()
 if (task) task.scrollIntoView({block:'center'})
}
window.addEventListener('hashchange', fromHash)
fromHash()
</script></body></html>'''
