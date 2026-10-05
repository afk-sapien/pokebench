"""Summarize preregistered offline calibration, never mix it with model scores."""
from collections import Counter
from pathlib import Path

from .core import digest
from .suite import read


def assess(root):
    root=Path(root)
    registration=read(root/'preregistration.json')
    policy_hash=digest((root/'frozen-policy.py').read_bytes())
    if policy_hash != registration['policy_sha256']:
        raise ValueError('Frozen calibration policy changed')
    if len(set(registration['offsets'])) != len(registration['offsets']):
        raise ValueError('Starting offsets must be distinct')
    if registration['modes'] != ['tactical', 'attack-first', 'type-aware-attacker']:
        raise ValueError('All three registered policies are required in order')
    starts=[f'start-{i:03d}' for i in range(1,len(registration['offsets'])+1)]
    modes=registration['modes']
    expected={(start,mode) for start in starts for mode in modes}
    rows=read(root/'results.json')['results']
    counts=Counter((r['scenario'],r['mode']) for r in rows)
    if set(counts)!=expected or any(n!=1 for n in counts.values()):
        raise ValueError('Calibration must include every registered start and policy exactly once')
    for index,(start,offset) in enumerate(zip(starts,registration['offsets']),1):
        scenario=read(root/start/'scenario.json')
        if scenario['provenance']['offset_frames']!=offset:
            raise ValueError('Starting offset changed')
        state_hash=digest((root/start/'initial.state').read_bytes())
        if state_hash!=scenario['state_sha256']:
            raise ValueError('Starting state changed')
        for mode in modes:
            run=root/'runs'/f'{index:03d}-{mode}'
            manifest=read(run/'manifest.json')
            if (manifest['agent'].get('policy_sha256')!=policy_hash
                    or manifest['scenario']['state_sha256']!=state_hash):
                raise ValueError('Policy or fixture differs from registration')
            result=read(run/'result.json')
            row=next(r for r in rows if r['scenario']==start and r['mode']==mode)
            if row['completed']!=result['completed'] or not row['replay']['verified']:
                raise ValueError('Calibration result lacks consistent replay evidence')
    n=len(starts)
    wins={mode:sum(r['completed'] for r in rows if r['mode']==mode) for mode in modes}
    gaps={mode:wins['tactical']-value for mode,value in wins.items() if mode!='tactical'}
    invalid=sum(r['invalid_actions'] for r in rows)
    passed=(registration['split']=='holdout' and n==32 and wins['tactical']>=29
            and all(gap>=13 for gap in gaps.values()) and invalid==0)
    trajectories=[]
    for index in range(1,n+1):
        decisions=read(root/'runs'/f'{index:03d}-tactical'/'public-decisions.json')
        trajectories.append(digest(str([
            (r['request'],[(m['species'],m['hp'],m['status']) for m in r['observation']['party']],
             r['observation']['battle'].get('visible_hud'),r['result'].get('dialogue',{}).get('pages'))
            for r in decisions]).encode()))
    return {'status':'validated' if passed else 'experimental',
            'message':('Passed the preregistered offline tactical reliability gate.' if passed else
                       'Did not pass the tactical reliability gate. Excluded from model rankings.'),
            'attempts_per_policy':n,'wins':wins,'paired_win_gaps':gaps,'invalid_actions':invalid,
            'unique_tactical_trajectories':len(set(trajectories)),
            'criterion':registration['criterion'],'policy_sha256':policy_hash,'model_calls':0,
            'qualification':'Observed timing robustness, not proof of optimal play or independent random samples.',
            'registration_sha256':digest((root/'preregistration.json').read_bytes()),
            'rows':rows}
