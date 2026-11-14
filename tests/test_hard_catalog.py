"""The shipped PokeBench Hard tasks load, stay out of Short, and keep their caps and checks consistent."""
from pokeagent_bench import evaluation_catalog as catalog
from pokeagent_bench import milestone_runtime as runtime
from pokeagent_bench import navigation_conditions

TOKENS_PER_DECISION = 15_000
SHIPPED = {'navigation-hard-victory-road'}


def shipped():
    catalog._hard_definitions.cache_clear()
    return {task['id']: task for group in catalog.load_catalog(hard=True) for task in group['evals']}


def test_shipped_hard_tasks_load_only_in_the_hard_table():
    tasks = shipped()
    assert SHIPPED <= set(tasks)
    assert SHIPPED <= catalog.hard_tasks()
    short = {task['id'] for group in catalog.load_catalog(include_retired=True) for task in group['evals']}
    assert not short & set(tasks)


def test_shipped_hard_tasks_have_valid_milestones_and_matching_budgets():
    for task_id, task in shipped().items():
        runtime.validate_milestones(task['milestones'])
        assert task['difficulty'] == 'hard'
        assert task['token_limit'] == TOKENS_PER_DECISION * task['decision_limit'], task_id
        assert task['objective']['task_id'] == task_id


def test_victory_road_milestones_follow_the_forced_route():
    task = shipped()['navigation-hard-victory-road']
    assert [row['id'] for row in task['milestones']] == [
        'second-floor', 'third-floor', 'third-floor-switch', 'boulder-dropped', 'second-floor-switch', 'exit']
    # EVENT_VICTORY_ROAD_3_BOULDER_ON_SWITCH1, EVENT_VICTORY_ROAD_3_BOULDER_ON_SWITCH2, EVENT_VICTORY_ROAD_2_BOULDER_ON_SWITCH2
    assert [row['check'].get('event') for row in task['milestones'][2:5]] == [1632, 1638, 1343]
    assert task['milestones'][-1]['check'] == {'map': 34, 'near': [14, 31]}
    assert task['navigation_condition'] == navigation_conditions.PROTOCOL
    assert navigation_conditions.AFFECTED[task['id']] == ('VICTORY_ROAD', 'ROUTE_23')
