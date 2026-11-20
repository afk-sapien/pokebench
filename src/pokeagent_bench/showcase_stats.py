"""The 95% interval under each Short score, computed once at build time so the page needs no attempts to show it."""

MASK = 0xFFFFFFFF


def imul(a, b):
    """32-bit multiply, as JavaScript's Math.imul, kept unsigned."""
    return (a * b) & MASK


def score_interval(cells, draws=2000, seed=20261026, unranked=('preparation',)):
    """Return the 95% percentile interval of a category-balanced Short score.

    Score groups are resampled with replacement within each category, so the category weights stay fixed.
    Retired tasks and unranked categories are left out, as in the point score. This is the page's earlier
    scoreInterval step for step: the same mulberry32 draws, sums added left to right and the same group order,
    so it returns the same interval the page computed.
    """
    groups = {}
    for c in cells:
        if c.get('state') != 'finished' or c.get('value') is None or c.get('retired') or c.get('category') in unranked:
            continue
        key = c['category'] + '\0' + (c.get('score_group') or c['task_id'])
        groups.setdefault(key, (c['category'], []))[1].append(c['value'])
    by_category = {}
    for key in sorted(groups):
        category, values = groups[key]
        total = 0
        for value in values:
            total += value
        by_category.setdefault(category, []).append(total / len(values))
    categories = list(by_category.values())
    if not categories:
        return None
    state = seed & MASK

    def random():
        nonlocal state
        state = (state + 0x6D2B79F5) & MASK
        t = state
        t = imul(t ^ (t >> 15), t | 1)
        t ^= (t + imul(t ^ (t >> 7), t | 61)) & MASK
        return (t ^ (t >> 14)) / 4294967296

    scores = []
    for _ in range(draws):
        total = 0
        for values in categories:
            picked = 0
            for _ in values:
                picked += values[int(random() * len(values))]
            total += picked / len(values)
        scores.append(total / len(categories))
    scores.sort()
    return {'low': scores[int(0.025 * draws)], 'high': scores[int(0.975 * draws) - 1], 'draws': draws,
            'method': 'stratified-task-bootstrap-v1'}
