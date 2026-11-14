"""Separate focused-task ability from continuous full-game progress."""
SHORT = 'pokebench'
LONG = 'pokebench-long'
# Longer focused tasks scored by ordered milestones, ranked in their own table.
HARD = 'pokebench-hard'
BENCHMARKS = (SHORT, LONG, HARD)
NAMES = {SHORT: 'PokeBench', LONG: 'PokeBench Long', HARD: 'PokeBench Hard'}
# Preparation is scored and shown, but kept out of the ranked Short score.
UNRANKED_CATEGORIES = ('preparation',)
RANKED_CATEGORIES = ('navigation', 'battle', 'operations', 'objectives')


def ranked_average(category_scores):
    """Equal-weight mean of the ranked category scores, or None when none has a score."""
    values = [score for key, score in category_scores.items() if key not in UNRANKED_CATEGORIES]
    return sum(values) / len(values) if values else None


def for_category(category):
    return LONG if category == 'campaign' else SHORT


def for_task(task_id, category):
    """Hard tasks share category names with Short, so route them by task."""
    from .evaluation_catalog import hard_tasks
    return HARD if task_id in hard_tasks() else for_category(category)


def validate(benchmark):
    if benchmark not in BENCHMARKS:
        raise ValueError('Choose pokebench, pokebench-hard or pokebench-long')
    return benchmark
