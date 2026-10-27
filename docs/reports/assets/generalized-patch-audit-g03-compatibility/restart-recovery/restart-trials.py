import json, os, time, subprocess, signal, hashlib
from pathlib import Path
import docker, httpx

root=Path('/home/libertarian/ai-debugging-workbench')
folder=root/'artifacts/repository-recovery-correction';folder.mkdir(exist_ok=True)
journal=folder/'trials.json'
assert not journal.exists(), 'Never overwrite or replace restart attempts'
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain','--','backend','scripts','docker','compose.yaml'],cwd=root,text=True)
client=docker.from_env()
services={name:client.containers.get('patch-audit-g3c-'+name+'-1') for name in ['api','evaluator','db']}
source_hash=hashlib.sha256((root/'backend/src/workbench/repository_audit/service.py').read_bytes()).hexdigest()
actual=services['api'].exec_run(['sha256sum','/app/backend/src/workbench/repository_audit/service.py'])
if actual.exit_code!=0:
    actual=services['api'].exec_run(['sha256sum','/app/src/workbench/repository_audit/service.py'])
assert actual.exit_code==0 and actual.output.decode().split()[0]==source_hash,actual.output
plan=root/'docs/reports/assets/generalized-patch-audit-g03-compatibility/restart-recovery/restart-plan.json'
records={'implementation_sha':sha,'plan_sha256':hashlib.sha256(plan.read_bytes()).hexdigest(),'maximum_trials':5,'trials':[]}
def save():journal.write_text(json.dumps(records,indent=2)+'\n')
save()
for trial in range(1,6):
    start=time.monotonic();wall=int(time.time())
    entry={'trial':trial,'implementation_sha':sha,'status':'started','services':{n:{'id':c.id,'image':c.image.id} for n,c in services.items()}}
    records['trials'].append(entry);save()
    log=folder/f'trial-{trial}.log'
    command=['./scripts/e2e','-k','test_repository_cancel_and_restart_reconcile_completed_without_reexecution']
    with log.open('w') as out:
        process=subprocess.Popen(command,cwd=root,env=os.environ,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            code=-999
    entry.update(exit_code=code,elapsed_seconds=round(time.monotonic()-start,3))
    for name in ['api','evaluator']:
        (folder/f'trial-{trial}-{name}.log').write_bytes(services[name].logs(since=wall,timestamps=True))
    try:
        if code!=0:raise AssertionError('Original restart scenario failed; no replacement permitted')
        observed=json.loads((root/'artifacts/repository-audit/recovery.json').read_text())
        entry['recovery']=observed
        logtext=(folder/f'trial-{trial}-evaluator.log').read_text()
        submits=[s for s in logtext.splitlines() if f'POST /repository-audits/{observed["restored"]} ' in s]
        assert len(submits)==1,(len(submits),submits)
        entry['completed_candidate_execution_submissions']=len(submits)
        entry['candidate_reexecutions']=0
        resources=set()
        def collect(value):
            if isinstance(value,dict):
                if isinstance(value.get('cleanup'),list):
                    for c in value['cleanup']:
                        if isinstance(c,dict) and c.get('kind') and c.get('id'):
                            assert c.get('confirmed_absent');resources.add((c['kind'],c['id']))
                for v in value.values():collect(v)
            elif isinstance(value,list):
                for v in value:collect(v)
        with httpx.Client(base_url=os.environ['E2E_BASE_URL'],timeout=10) as api:
            assert api.get('/api/health').status_code==200
            for key in ['cancelled','restored','missing_terminal']:
                response=api.get('/api/repository-audits/runs/'+observed[key]);response.raise_for_status();collect(response.json())
        for kind,rid in resources:
            try:getattr(client,kind).get(rid)
            except docker.errors.NotFound:pass
            else:raise AssertionError('Recorded resource remains: '+rid)
        entry['recorded_resources_confirmed_actually_absent']=[{'kind':k,'id':i} for k,i in sorted(resources)]
        entry['status']='passed'
    except Exception as error:
        entry.update(status='failed',error_class=type(error).__name__,reason=str(error));save();raise
    save();print(json.dumps({'trial':trial,'status':entry['status'],'elapsed_seconds':entry['elapsed_seconds'],'recovery':entry['recovery']}),flush=True)
client.close()
