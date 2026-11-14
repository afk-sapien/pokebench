"""Separate focused-task ability from continuous full-game progress."""
SHORT = 'pokebench'
LONG = 'pokebench-long'
BENCHMARKS = (SHORT, LONG)
NAMES = {SHORT: 'PokeBench', LONG: 'PokeBench Long'}
# Preparation is scored and shown, but kept out of the ranked Short score.
UNRANKED_CATEGORIES = ('preparation',)
RANKED_CATEGORIES = ('navigation', 'battle', 'operations', 'objectives')


def ranked_average(category_scores):
    """Equal-weight mean of the ranked category scores, or None when none has a score."""
    values = [score for key, score in category_scores.items() if key not in UNRANKED_CATEGORIES]
    return sum(values) / len(values) if values else None


def for_category(category):
    return LONG if category == 'campaign' else SHORT


def validate(benchmark):
    if benchmark not in BENCHMARKS:
        raise ValueError('Choose pokebench or pokebench-long')
    return benchmark
