from copy import deepcopy

from pokeagent_bench.combined_analysis import combine_reports, summarize


def task(key='one'):
    return {'id':key, 'name':key, 'state_hash':'save-'+key, 'tokens':100,
            'objective':{'kind':'milestone','target':'badge:boulder'}}


def cohort(key, tasks=None, statuses=None, passes=None):
    tasks = tasks or [task()]
    return {'id':key, 'label':key, 'suite':key, 'tasks':tasks,
            'configuration':{'rom_sha256':'rom', 'source_sha256':key},
            'models':[{'model':'a'},{'model':'b'}],
            'attempts':[{'id':f'{key}-{t["id"]}-{m}', 'task':t['id'], 'model':m, 'repeat':1,
                         'status':(statuses or {}).get(m,'finished'), 'completed':(passes or {}).get(m,True),
                         'replay_verified':True,'replay':key+'-'+m+'.html','tokens':10}
                        for t in tasks for m in ['a','b']]}


def test_latest_started_task_is_selected_for_all_models_even_when_worse():
    new = cohort('new',passes={'a':False,'b':True})
    old = cohort('old')
    before = deepcopy([new, old])
    report = combine_reports([new, old])
    assert report['scored_task_ids']==['one']
    assert {a['source_cohort'] for a in report['attempts']}=={'new'}
    assert {m['model']:m['score'] for m in report['models']}=={'a':0,'b':100}
    assert report['tasks'][0]['source']['configuration']['source_sha256']=='new'
    assert [new, old]==before


def test_unstarted_registration_does_not_hide_earlier_observations():
    pending = cohort('planned',statuses={'a':'pending','b':'pending'})
    old = cohort('old')
    report = combine_reports([pending, old])
    assert report['tasks'][0]['source']['id']=='old'
    assert report['models'][0]['score']==100
    pending['attempts'][0]['status']='running'
    report = combine_reports([pending, old])
    assert report['tasks'][0]['source']['id']=='planned'
    assert not report['scored_task_ids']
    assert not report['ranking_ready']


def test_shared_denominator_excludes_error_pending_and_missing_tasks_equally():
    catalog = cohort('catalog',[task('one'),task('two'),task('three')])
    catalog['models']=[]
    catalog['attempts']=[]
    first = cohort('first',passes={'a':False,'b':True})
    error = cohort('error',[task('two')],statuses={'a':'finished','b':'error'})
    report = combine_reports([first,error,catalog])
    assert report['scored_task_ids']==['one']
    assert len(report['tasks'])==3
    assert {m['model']:m['score'] for m in report['models']}=={'a':0,'b':100}
    assert all(m['scored_tasks']==1 and m['total_tasks']==3 for m in report['models'])
    assert not report['coverage_complete']
    assert report['tokens']==40
    assert len(report['attempts'])==4
    assert report['tasks'][2]['source'] is None


def test_different_save_budget_or_rom_is_never_substituted_for_catalog_task():
    catalog = cohort('catalog')
    catalog['models']=[]
    catalog['attempts']=[]
    for field,value in [('state_hash','different'),('tokens',200),('objective',{'kind':'heal'})]:
        incompatible=cohort('bad')
        incompatible['tasks'][0][field]=value
        report=combine_reports([catalog,incompatible])
        assert not report['attempts']
    incompatible=cohort('bad')
    incompatible['configuration']['rom_sha256']='other'
    assert not combine_reports([catalog,incompatible])['attempts']


def test_equal_task_weights_and_matching_repeats():
    tasks=[task('one'),task('two')]
    c=cohort('source',tasks)
    c['attempts'][0]['completed']=False
    c['attempts'][1]['completed']=True
    c['attempts'][2]['completed']=True
    c['attempts'][3]['completed']=False
    extra=[{**a,'id':a['id']+'-2','repeat':2} for a in c['attempts'] if a['task']=='one']
    eligible, models=summarize(tasks,c['attempts']+extra,['a','b'])
    assert eligible==['one','two']
    assert all(m['score']==50 and m['rank']==1 for m in models)
    eligible,_=summarize(tasks,c['attempts']+extra[:1],['a','b'])
    assert eligible==['two']
    eligible,_=summarize(tasks,c['attempts']+[deepcopy(c['attempts'][0])],['a','b'])
    assert eligible==['two']


def test_unknown_usage_from_selected_retry_stays_visible_without_fabricated_tokens():
    new = cohort('new')
    new['interrupted_attempts'] = [{'id': 'old-attempt', 'retry_cell_id': 'new-one-a',
                                  'task': 'one', 'model': 'a', 'recorded_tokens': 0,
                                  'accounting_complete': False, 'reserved_tokens': 100}]
    old = cohort('old')
    old['interrupted_attempts'] = [{'id': 'older', 'task': 'one', 'model': 'a',
                                  'accounting_complete': False}]
    report = combine_reports([new, old])
    assert len(report['interrupted_attempts']) == 1
    assert report['interrupted_attempts'][0]['source_cohort'] == 'new'
    assert report['interrupted_attempts'][0]['reserved_tokens'] == 100
    assert report['tokens'] == 20
    assert report['scored_task_ids'] == ['one']


def test_curated_ranking_preserves_history_and_removes_trivial_tasks_from_costs():
    from pokeagent_bench.combined_analysis import RETIREMENTS, RANKING_VERSION
    retired = [{**task(key), 'state_hash':value[0]} for key,value in RETIREMENTS.items()]
    source = cohort('original', [*retired, task('heal'), task('lorelei-tactics')])
    for attempt in source['attempts']:
        attempt.update(cost_complete=True, estimated_credits=5)
        if attempt['task']=='lorelei-tactics' and attempt['model']=='a':
            attempt['completed']=False
    before = deepcopy(source)
    result = combine_reports([source])
    assert source == before
    assert result['analysis']==RANKING_VERSION
    assert [t['id'] for t in result['tasks']]==['heal','lorelei-tactics']
    assert result['scored_task_ids']==['heal','lorelei-tactics']
    assert len(result['retired_tasks'])==5
    assert all(t['source']['id']=='original' and t['reason'] for t in result['retired_tasks'])
    assert {m['model']:m['score'] for m in result['models']}=={'a':50,'b':100}
    assert len(result['attempts'])==4 and result['tokens']==40
    assert result['cost_analysis']['task_ids']==['heal','lorelei-tactics']
    assert {m['model']:m['credits_per_success'] for m in result['cost_analysis']['models']}=={'a':10,'b':5}


def test_retirement_is_bound_to_exact_save_not_name_or_universal_success():
    from pokeagent_bench.combined_analysis import RETIREMENTS
    old = task('brock')
    old['state_hash']=RETIREMENTS['brock'][0]
    replacement = {**old, 'state_hash':'calibrated-brock-save'}
    report = combine_reports([cohort('replacement',[replacement, task('heal')]),cohort('old',[old])])
    assert report['retired_tasks']==[]
    assert report['scored_task_ids']==['brock','heal']
    assert all(m['score']==100 for m in report['models'])
