"""Export only two selected, validated historical Boltons examples. Never scans local imports."""

import json
from pathlib import Path

from workbench.evaluator.catalog import digest, identity
from workbench.evaluator.experiment_catalog import task
from workbench.patch_audit.curated import FAIL, PASS, examples
from workbench.patch_audit.service import public_task

root = Path(__file__).resolve().parents[1]
selected = examples()
manifest = {'version':'recorded-patch-audits-v1', 'records':[]}
for key in (FAIL, PASS):
    example = selected[key]
    c = example['candidate']
    spec = task(c['task_id'])
    result = example['recorded_result']
    envelope = {'audit_id':key, 'candidate_id':c['id'], 'record_hash':c['record_hash'], 'result':result}
    value = {
        'id':key, 'candidate_id':c['id'], 'candidate_hash':c['candidate_hash'],
        'status':result['status'], 'created_at':result['ordinary']['started_at'],
        'updated_at':result['independent']['ended_at'], 'execution_mode':'recorded',
        'recording':{'historical':True, 'note':'Inspect saved evidence. No fresh audit or inference occurs.',
                     'source_trial':key, 'limitations':c['provenance']['limitations']},
        'evidence':{'task':public_task(spec), 'candidate':c, 'envelope':envelope,
                    'envelope_hash':identity(envelope), 'source_validation':example['source_validation'], 'license_text':spec['files']['LICENSE']},
    }
    name = 'patch-audit-' + ('missed' if key == FAIL else 'complete') + '.json'
    data = (json.dumps(value, indent=2) + '\n').encode()
    (root/'recordings'/name).write_bytes(data)
    manifest['records'].append({'id':key, 'title':example['label'], 'task_id':c['task_id'],
                                'file':name, 'sha256':digest(data), 'status':result['status']})
(root/'recordings/patch-audit-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Exported exactly two validated historical audits; no local imports or new execution included.')
