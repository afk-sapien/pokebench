// 95% percentile interval for a category-balanced Short score.
// Resamples score groups with replacement within each category, so category weights stay fixed.
function scoreInterval(cells, draws = 2000, seed = 20261026) {
  const groups = {}
  for (const c of cells) {
    if (c.state !== 'finished' || c.value == null) continue
    const key = c.category + '\u0000' + (c.score_group || c.task_id)
    ;(groups[key] ||= {category:c.category, values:[]}).values.push(c.value)
  }
  const byCategory = {}
  for (const key of Object.keys(groups).sort()) {
    const g = groups[key]
    ;(byCategory[g.category] ||= []).push(g.values.reduce((a,b) => a + b, 0) / g.values.length)
  }
  const categories = Object.values(byCategory)
  if (!categories.length) return null
  let state = seed >>> 0
  const random = () => {
    state = (state + 0x6D2B79F5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  const scores = []
  for (let i = 0; i < draws; i++) {
    let total = 0
    for (const values of categories) {
      let sum = 0
      for (let j = 0; j < values.length; j++) sum += values[Math.floor(random() * values.length)]
      total += sum / values.length
    }
    scores.push(total / categories.length)
  }
  scores.sort((a,b) => a - b)
  return {low:scores[Math.floor(0.025 * draws)], high:scores[Math.floor(0.975 * draws) - 1], draws, method:'stratified-task-bootstrap-v1'}
}
if (typeof module !== 'undefined') module.exports = {scoreInterval}
