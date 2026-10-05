import shutil
import subprocess

import pytest

from pokeagent_bench.portal import HTML, category, publish
from pokeagent_bench.core import digest, write_json


def test_categories_support_new_tasks_without_extra_columns():
    assert category({'id':'new-gym','objective':{'kind':'milestone'}}) == 'Battles'
    assert category({'id':'future','objective':{'kind':'capture'}}) == 'Collection'
    assert category({'id':'item-recovery'}) == 'Recovery'


def test_portal_separates_versions_and_links_only_existing_replays(tmp_path, monkeypatch):
    suite = tmp_path/'suite'
    suite.mkdir()
    (suite/'suite.json').write_text('{}')
    fixture = suite/'fixture'
    fixture.mkdir()
    (fixture/'preview.png').write_bytes(b'preview')
    write_json(fixture/'scenario.json',{'objective':{'description':'A real task'}})
    definition = {'definition':{'tasks':[{'id':'starter','name':'Starter','tokens':100,'difficulty':'easy','objective':{'kind':'opening'}}]},
                  'fixtures':{'starter':{'scenario':'fixture','state_sha256':'abc'}}}
    monkeypatch.setattr('pokeagent_bench.portal.validate',lambda *args,**kwargs:definition)
    batch = tmp_path/'batch'
    run = batch/'cell-1'
    run.mkdir(parents=True)
    (run/'manifest.json').write_text('{}')
    (run/'result.json').write_text('{}')
    report={'configuration':{'suite_sha256':digest((suite/'suite.json').read_bytes())},
            'attempts':[{'id':'cell-1','status':'finished'}]}
    entries=[]
    for key in ['old','new']:
        path=tmp_path/(key+'.json')
        write_json(path,report)
        entries.append({'id':key,'label':key,'report':str(path),'batch':str(batch),'suite':str(suite)})
    target=tmp_path/'portal.html'
    result=publish(entries,target)
    assert [c['id'] for c in result['cohorts']] == ['old','new']
    assert all(c['attempts'][0]['replay'] is None for c in result['cohorts'])
    revision=digest(b'{}{}')[:16]
    link=tmp_path/f'old-cell-1-{revision}.html'
    link.write_text('Replay')
    result=publish(entries,target)
    assert result['cohorts'][0]['attempts'][0]['replay']==link.name
    assert result['cohorts'][1]['attempts'][0]['replay'] is None
    assert 'http-equiv="refresh"' not in target.read_text()
    report['configuration']['suite_sha256']='tampered'
    write_json(tmp_path/'old.json',report)
    with pytest.raises(ValueError,match='does not match'):
        publish(entries,target)


def test_fifty_benchmarks_pagination_filtering_and_ranking(tmp_path):
    node=shutil.which('node')
    if not node:
        pytest.skip('Node required for portal interaction logic')
    script=HTML.split('<script>')[1].split('</script>')[0].replace('__FEED__','"data.json"')
    script=script.rsplit('\nrefresh()',1)[0]
    path=tmp_path/'portal.js'
    path.write_text(script)
    test=r'''
const fs = require('fs')
const vm = require('vm')
const assert = require('assert')
const elements = {}
const element = id => elements[id] ??= {value:'',innerHTML:'',textContent:'',scrollTop:0,addEventListener(){},showModal(){this.open=true},close(){this.open=false}}
element('difficulty').value='all'
element('sort').value='default'
const context = {document:{getElementById:element,addEventListener(){},querySelector(){return null}},Intl,console,Set,Date,setInterval(){}}
vm.createContext(context)
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context)
vm.runInContext(`
const tasks = Array.from({length:50},(_,i)=>({id:'t'+i,name:'Benchmark '+i,category:i<25?'Battles':'Navigation',difficulty:'easy',tokens:100,description:'Test',state_hash:'abc',preview:''}))
const attempts = ['a','b'].flatMap(model=>tasks.map((t,i)=>({id:model+t.id,model,task:t.id,status:'finished',replay_verified:true,completed:model==='a'||i<25,tokens:10,repeat:1})))
const cohort = {id:'current',tasks,attempts,models:[{model:'a'},{model:'b'}],downloads:{},configuration:{core:{}},tokens:1000}
state.data={updated_at:new Date().toISOString(),cohorts:[cohort]}
state.cohort='current'
render()
`,context)
assert.equal((element('tasks').innerHTML.match(/class="task-row"/g)||[]).length,10)
assert.equal(element('page-info').textContent,'1–10 of 50')
vm.runInContext('state.page=4\nrenderTasks()',context)
assert.equal(element('page-info').textContent,'41–50 of 50')
assert.equal(element('next').disabled,true)
const full=vm.runInContext('metrics(current(),scoped())',context)
assert.equal(full.ready,true)
assert.equal(full.models[0].score,100)
assert.equal(full.models[1].score,50)
element('search').value='Benchmark 49'
vm.runInContext('renderTasks()',context)
assert.equal(element('page-info').textContent,'1–1 of 1')
assert.match(element('tasks').innerHTML,/Benchmark 49/)
vm.runInContext("state.category='Battles'\nrenderBoard()",context)
const battles=vm.runInContext('metrics(current(),scoped())',context)
assert.equal(battles.models[1].score,100)
vm.runInContext("current().attempts[0].status='running'",context)
assert.equal(vm.runInContext('metrics(current(),scoped()).ready',context),false)
vm.runInContext("current().analysis='combined-exploratory-v1'",context)
const combined=vm.runInContext('metrics(current(),scoped())',context)
assert.equal(combined.ready,true)
assert.equal(combined.scored,24)
assert.equal(combined.total,25)
assert.equal(combined.models[0].score,100)
assert.equal(combined.models[1].score,100)
vm.runInContext('renderBoard()',context)
assert.match(element('score-note').textContent,/24 of 25/)
vm.runInContext(`
const canonical=current()
const priorScores=metrics(canonical,scoped()).models.map(m=>m.score)
const pilotTask={...canonical.tasks[0],id:'pilot-task',name:'Pilot battle',validation:{status:'experimental'}}
canonical.tasks.push(pilotTask)
const pilot={id:'pilot',label:'Experimental pilot',tasks:[pilotTask],attempts:[{id:'pilot-1',task:'pilot-task',model:'a',status:'running',tokens:12,repeat:1}],models:[{model:'a'}]}
state.data.cohorts.unshift(pilot)
state.cohort='pilot'
`,context)
assert.equal(vm.runInContext('current().id',context),'current')
assert.equal(vm.runInContext('visibleAttempts("pilot-task")[0].status',context),'running')
assert.equal(vm.runInContext('metrics(current(),scoped()).scored',context),24)
vm.runInContext("openDetail('task','pilot-task')",context)
assert.match(element('detail-content').innerHTML,/not included in the ability score/)
assert.match(element('detail-content').innerHTML,/Running/)
vm.runInContext(`
state.data.cohorts.push({...pilot,id:'earlier',label:'Earlier pilot',attempts:[{...pilot.attempts[0],id:'earlier-1',status:'finished',completed:false,replay:'saved.html'}]})
state.detailKey=null
detailContent()
`,context)
assert.match(element('detail-content').innerHTML,/Earlier runs \(1\)/)
assert.match(element('detail-content').innerHTML,/saved.html/)
vm.runInContext('state.data.cohorts=[canonical]\ncanonical.tasks.pop()',context)
vm.runInContext('delete current().analysis',context)
vm.runInContext("openDetail('task','t0')",context)
assert.equal(element('detail').open,true)
assert.match(element('detail-content').innerHTML,/Model attempts/)
vm.runInContext("current().models=[]\ncurrent().attempts=[]\nstate.detailKey=null\nrender()\nopenDetail('task','t0')",context)
assert.match(element('score-note').textContent,/have not been run/)
assert.match(element('status').textContent,/50 verified benchmarks/)
assert.match(element('detail-content').innerHTML,/No model attempts/)
console.log('50-benchmark pagination, search, category scores and unrun catalog checks passed')
'''
    harness=tmp_path/'test.cjs'
    harness.write_text(test)
    result=subprocess.run([node,str(harness),str(path)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_calibration_applies_only_to_identical_starting_variants(tmp_path, monkeypatch):
    definitions = {}
    entries = []
    for key, hashes, status in [
        ('old', ['old-1','old-2'], 'experimental'),
        ('new', ['new-1','new-2'], 'validated'),
        ('catalog', ['old-1','old-2'], None),
        ('other', ['new-1','different-2'], None),
    ]:
        folder=tmp_path/key
        fixture=folder/'fixture'
        fixture.mkdir(parents=True)
        (fixture/'preview.png').write_bytes(b'preview')
        write_json(fixture/'scenario.json',{'objective':{'description':'A tactical battle'}})
        write_json(folder/'suite.json',{})
        definitions[folder]={'definition':{'tasks':[{'id':'lorelei-tactics','objective':{'kind':'battle-milestone'}}]},
                             'fixtures':{'lorelei-tactics':{'scenario':'fixture','state_sha256':hashes[0],
                                                          'variants':[{'state_sha256':h} for h in hashes]}}}
        report=folder/'report.json'
        write_json(report,{'configuration':{'suite_sha256':digest((folder/'suite.json').read_bytes())},'attempts':[]})
        entry={'id':key,'label':key,'report':str(report),'suite':str(folder),'batch':str(folder/'batch')}
        if status:
            validation=folder/'validation.json'
            write_json(validation,{'status':status})
            entry['validation']=str(validation)
        entries.append(entry)
    monkeypatch.setattr('pokeagent_bench.portal.validate',lambda root,**kwargs:definitions[root])
    result=publish(entries,tmp_path/'portal.html')
    tasks={cohort['id']:cohort['tasks'][0] for cohort in result['cohorts']}
    assert tasks['old']['validation']['status']=='experimental'
    assert tasks['new']['validation']['status']=='validated'
    assert tasks['catalog']['validation']['status']=='experimental'
    assert 'validation' not in tasks['other']
