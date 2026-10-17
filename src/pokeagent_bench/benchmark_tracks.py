"""Separate focused-task ability from continuous full-game progress."""
SHORT = 'pokebench'
LONG = 'pokebench-long'
BENCHMARKS = (SHORT, LONG)
NAMES = {SHORT: 'PokeBench', LONG: 'PokeBench Long'}


def for_category(category):
    return LONG if category == 'campaign' else SHORT


def validate(benchmark):
    if benchmark not in BENCHMARKS:
        raise ValueError('Choose pokebench or pokebench-long')
    return benchmark
