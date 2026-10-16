"""Opt-in, one request per task; HTTP model receives only the recorded public context.

No tools, retrieval, filesystem mounts, reference patches, scoring code or feedback are exposed.
Every attempted generation is written before patch admission. No candidate is manually repaired.
"""

import argparse
import ast
import asyncio
import difflib
import json
from datetime import UTC, datetime
from pathlib import Path

from workbench.config import ProviderSettings
from workbench.evaluator.catalog import CATALOG, TASK_IDS, apply, digest, identity, task
from workbench.evaluator.runner import verifier_id
from workbench.rag.provider import NvidiaProvider, sanitize_model_text


def context(spec):
    excerpts = []
    for path in spec['allowed_paths']:
        content = spec['files'][path]
        tree = ast.parse(content)
        if spec['id'] == 'more-bucket':
            nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'bucket']
        else:
            nodes = [m for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == 'OrderedMultiDict' for m in n.body
                     if isinstance(m, ast.FunctionDef) and m.name == 'addlist']
        for node in nodes:
            excerpts.append({'path':path,'start_line':node.lineno,'end_line':node.end_lineno,
                             'content':''.join(content.splitlines(True)[node.lineno-1:node.end_lineno])})
    return excerpts


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', required=True)
    args=parser.parse_args()
    assert args.live
    freeze=json.loads((CATALOG/'freeze-v1.json').read_text())
    assert freeze['hash']==identity(freeze['body'])
    config=ProviderSettings(provider_retries=0,provider_max_requests=2,model_output_token_limit=3000)
    provider=NvidiaProvider(config)
    try:
        for task_id in TASK_IDS:
            spec=task(task_id)
            assert freeze['body']['tasks'][task_id]=={'spec_hash':spec['spec_hash'],'verifier_hash':verifier_id(task_id)}
            attempt_path=CATALOG/'generations'/(task_id+'-nvidia-01.json')
            if attempt_path.exists():
                raise ValueError('Attempt already retained. Use an explicitly versioned new experiment.')
            approved=context(spec)
            system='You are a coding agent repairing an upstream Python library. Return JSON only: {"edits":[{"path":"...","old":"exact unique source excerpt","new":"replacement source"}]}. Only edit the allowed production paths. Preserve indentation. You have no tools. Do not change tests or invent files. Produce a minimal working correction.'
            user=json.dumps({'project':spec['project'],'base_commit':spec['base_commit'],
                             'problem':spec['problem'],'expected_behavior':spec['expected'],
                             'allowed_paths':spec['allowed_paths'],'source_excerpts':approved})
            payload={'model':config.chat_model,'messages':[{'role':'system','content':system},
                      {'role':'user','content':user}],'temperature':0,'max_tokens':3000,
                      'response_format':{'type':'json_object'},
                      'chat_template_kwargs':{'enable_thinking':False}}
            record={'task_id':task_id,'base_commit':spec['base_commit'],'freeze_hash':freeze['hash'],
                    'started_at':datetime.now(UTC).isoformat(),'request':payload,
                    'request_hash':identity(payload),'context_hash':identity(approved),
                    'tools':[],'retrieval':False,'retries':0,'producer':'NVIDIA HTTP coding agent (single-turn, no tools)'}
            attempt_path.parent.mkdir(parents=True,exist_ok=True)
            # Record intent before making the external call, including failed attempts.
            attempt_path.write_text(json.dumps(record,indent=2)+'\n')
            try:
                body=await provider.request('chat','https://integrate.api.nvidia.com/v1/chat/completions',payload)
                record['response']=json.loads(sanitize_model_text(json.dumps(body),200000))
                raw=body['choices'][0]['message']['content']
                if body['choices'][0]['finish_reason']!='stop':
                    raise ValueError('Truncated response')
                edits=json.loads(raw)['edits']
                files=apply(spec,edits)
                patch=''.join(''.join(difflib.unified_diff(spec['files'][p].splitlines(True),files[p].splitlines(True),fromfile='a/'+p,tofile='b/'+p)) for p in spec['allowed_paths'])
                binding={'spec_hash':spec['spec_hash'],'patch_hash':digest(patch),
                         'source_hashes':{p:digest(v) for p,v in files.items()}}
                c={'id':task_id+'-nvidia-01','task_id':task_id,'spec_hash':spec['spec_hash'],
                   'candidate_hash':identity(binding),'label':'NVIDIA fresh candidate 01','kind':'agent',
                   'producer':config.chat_model,'provenance':'Fresh NVIDIA single-turn coding-agent output. No tools, reference correction, independent checks or evaluation feedback supplied. Public historical task; training contamination is possible.',
                   'edits':edits,'generation':str(attempt_path.relative_to(CATALOG)),
                   'freeze_hash':freeze['hash'],'generation_request_hash':identity(payload)}
                (CATALOG/'candidates'/(c['id']+'.json')).write_text(json.dumps(c,indent=2)+'\n')
                record['status']='candidate_admitted'
                record['candidate_hash']=c['candidate_hash']
            except Exception as error:
                record['status']='generation_failed_or_invalid'
                record['error']=type(error).__name__
            finally:
                record['completed_at']=datetime.now(UTC).isoformat()
                record['provider_calls']=list(provider.calls)
                attempt_path.write_text(json.dumps(record,indent=2)+'\n')
                print(task_id,record['status'])
    finally:
        await provider.close()


if __name__=='__main__':
    asyncio.run(main())
