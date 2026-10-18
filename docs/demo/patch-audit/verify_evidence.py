"""Revalidate filmed fresh audits with the unchanged product validators. No execution."""
import json
from pathlib import Path
from workbench.patch_audit.admission import rebuild
from workbench.patch_audit.execution import validate
from workbench.evaluator.experiment_catalog import task
from workbench.evaluator.catalog import identity

ROOT=Path(__file__).resolve().parents[3]
RAW=ROOT/'artifacts/demo-production/raw'
rows=[]
for key,outcome,recording in [('incomplete','failed','patch-audit-missed.json'),('complete','passed','patch-audit-complete.json')]:
    audit=json.loads((RAW/(key+'-audit.json')).read_text())
    evidence=audit['evidence'];candidate=evidence['candidate'];result=evidence['envelope']['result']
    validate(task(candidate['task_id']),rebuild(candidate),result)
    assert identity(evidence['envelope'])==evidence['envelope_hash']
    historical=json.loads((ROOT/'recordings'/recording).read_text())['evidence']['candidate']
    assert candidate['patch']==historical['patch'] and candidate['candidate_hash']==historical['candidate_hash']
    assert result['status']==outcome and result['ordinary']['outcome']=='passed'
    rows.append({'audit_id':audit['id'],'status':result['status'],'candidate_hash':candidate['candidate_hash'],'envelope_hash':evidence['envelope_hash'],'validation':'accepted existing admission, verifier and envelope validation','ordinary':'passed','independent':outcome})
(RAW/'evidence-validation.json').write_text(json.dumps(rows,indent=2)+'\n')
print('Both filmed audits match their exact historical patch bytes and pass existing evidence validation.')
