"""The shipped PokeBench Hard tasks load, stay out of Short, and keep their caps and checks consistent."""
from pokeagent_bench import evaluation_catalog as catalog
from pokeagent_bench import milestone_runtime as runtime
from pokeagent_bench import navigation_conditions

TOKENS_PER_DECISION = 15_000
SHIPPED = {'navigation-hard-victory-road', 'navigation-hard-seafoam', 'navigation-hard-silph-co'}


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


def test_seafoam_milestones_score_only_the_holes_that_gate_articuno():
    task = shipped()['navigation-hard-seafoam']
    assert [row['id'] for row in task['milestones']] == [
        'first-basement', 'second-basement', 'third-basement', 'west-hole', 'east-hole', 'articuno']
    assert [row['check'].get('map') for row in task['milestones'][:3]] == [159, 160, 161]
    # EVENT_SEAFOAM4_BOULDER1_DOWN_HOLE and EVENT_SEAFOAM4_BOULDER2_DOWN_HOLE, set by the B3F holes.
    # The upper floor hole flags are optional and stay out of the score.
    assert [row['check'].get('event') for row in task['milestones'][3:5]] == [2512, 2513]
    assert task['milestones'][-1]['check'] == {'map': 162, 'near': [6, 1]}
    assert navigation_conditions.AFFECTED[task['id']] == ('SEAFOAM_ISLANDS', 'ROUTE_20')


def test_silph_co_milestones_follow_the_card_key_and_pad_route():
    task = shipped()['navigation-hard-silph-co']
    assert [row['id'] for row in task['milestones']] == [
        'fifth-floor-corridor', 'card-key', 'third-floor-pad-room', 'eleventh-floor-west-hall', 'giovanni-room']
    # 5F, 3F and 11F. CARD_KEY is item 0x30.
    assert [row['check'].get('map') for row in task['milestones']] == [210, None, 208, 235, 235]
    assert task['milestones'][1]['check'] == {'item': 48}
    assert task['milestones'][-1]['check'] == {'map': 235, 'area': [5, 5, 12, 13]}
    # One prefix per floor, so the rival and Giovanni flags stay as the start sets them.
    assert navigation_conditions.AFFECTED[task['id']] == tuple(f'SILPH_CO_{floor}F' for floor in range(2, 12))
