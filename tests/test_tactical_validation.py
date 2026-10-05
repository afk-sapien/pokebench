import json

import pytest

from pokeagent_bench.core import digest, write_json
from pokeagent_bench.tactical_validation import assess


def calibration(tmp_path, wins=(29,0,16)):
    policy=b'frozen calibration'
    (tmp_path/'frozen-policy.py').write_bytes(policy)
    modes=['tactical','attack-first','type-aware-attacker']
    registration={'policy_sha256':digest(policy),'offsets':list(range(32)),
                  'modes':modes,'split':'holdout','criterion':'preregistered'}
    write_json(tmp_path/'preregistration.json',registration)
    rows=[]
    for index in range(32):
        start=tmp_path/f'start-{index+1:03d}'
        start.mkdir()
        raw=str(index).encode()
        (start/'initial.state').write_bytes(raw)
        write_json(start/'scenario.json',{'provenance':{'offset_frames':index},'state_sha256':digest(raw)})
        for mode,successes in zip(modes,wins):
            run=tmp_path/'runs'/f'{index+1:03d}-{mode}'
            run.mkdir(parents=True)
            write_json(run/'manifest.json',{'agent':{'policy_sha256':digest(policy)},'scenario':{'state_sha256':digest(raw)}})
            completed=index<successes
            write_json(run/'result.json',{'completed':completed})
            write_json(run/'public-decisions.json',[])
            rows.append({'scenario':start.name,'mode':mode,'completed':completed,
                         'invalid_actions':0,'replay':{'verified':True}})
    write_json(tmp_path/'results.json',{'results':rows})
    return tmp_path


def test_frozen_gate_and_small_sample_qualification(tmp_path):
    result=assess(calibration(tmp_path))
    assert result['status']=='validated'
    assert result['wins']['tactical']==29
    assert result['paired_win_gaps']['type-aware-attacker']==13
    assert result['unique_tactical_trajectories']==1
    assert 'not proof' in result['qualification']


@pytest.mark.parametrize('wins',[(28,0,0),(29,0,17)])
def test_reliability_and_separation_both_required(tmp_path,wins):
    assert assess(calibration(tmp_path,wins))['status']=='experimental'


@pytest.mark.parametrize('mutation',['missing','duplicate','policy','state','missing_baseline','duplicate_offset'])
def test_missing_or_changed_evidence_fails_closed(tmp_path,mutation):
    root=calibration(tmp_path)
    if mutation in ('missing','duplicate'):
        data=json.loads((root/'results.json').read_text())
        if mutation=='missing':
            data['results'].pop()
        else:
            data['results'].append(data['results'][0])
        write_json(root/'results.json',data)
    elif mutation in ('missing_baseline','duplicate_offset'):
        data=json.loads((root/'preregistration.json').read_text())
        if mutation=='missing_baseline':
            data['modes'].pop()
        else:
            data['offsets'][1]=data['offsets'][0]
        write_json(root/'preregistration.json',data)
    elif mutation=='policy':
        (root/'frozen-policy.py').write_text('changed')
    else:
        (root/'start-001/initial.state').write_bytes(b'changed')
    with pytest.raises(ValueError):
        assess(root)


def test_experimental_task_does_not_rank_models():
    from pokeagent_bench.combined_analysis import summarize
    task={'id':'fight','validation':{'status':'experimental'}}
    rows=[{'task':'fight','model':m,'repeat':1,'status':'finished','completed':True,'replay_verified':True}
          for m in ('a','b')]
    tasks,scores=summarize([task],rows,['a','b'])
    assert tasks==[]
    assert all(row['score'] is None for row in scores)
