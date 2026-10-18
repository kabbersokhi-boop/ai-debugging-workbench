"""Create explicitly authored controls from pinned source; never attribute these to a model."""

import difflib
import json
import subprocess

from workbench.evaluator.catalog import CATALOG, TASK_IDS, apply, digest, identity, task


def retain(spec, label, edits, provenance):
    files = apply(spec, edits)
    patch = ''.join(''.join(difflib.unified_diff(
        spec['files'][p].splitlines(keepends=True), files[p].splitlines(keepends=True),
        fromfile='a/'+p, tofile='b/'+p)) for p in spec['allowed_paths'])
    binding = {'spec_hash': spec['spec_hash'], 'patch_hash': digest(patch),
               'source_hashes': {p: digest(v) for p, v in files.items()}}
    candidate_id = spec['id'] + '-' + label
    value = {'id': candidate_id, 'task_id': spec['id'], 'spec_hash': spec['spec_hash'],
             'candidate_hash': identity(binding), 'label': label.replace('-', ' ').title(),
             'kind': 'control', 'producer': 'Deliberately authored evaluator control',
             'provenance': provenance, 'edits': edits}
    path = CATALOG / 'candidates' / (candidate_id + '.json')
    encoded = json.dumps(value, indent=2)+'\n'
    if path.exists() and path.read_text() != encoded:
        raise ValueError('Controls are immutable; use a new ID')
    path.write_text(encoded)


def main():
    for task_id in TASK_IDS:
        spec = task(task_id)
        retain(spec, 'baseline', [], 'Unmodified upstream defective base; not an agent output.')
        reference = []
        for path in spec['allowed_paths']:
            repo = '/tmp/evaluator-more-itertools' if task_id == 'more-bucket' else '/tmp/evaluator-boltons'
            fixed = subprocess.check_output(['git', '-C', repo, 'show',
                                            spec['reference_commit']+':'+path], text=True)
            before = spec['files'][path]
            matcher = difflib.SequenceMatcher(None, before.splitlines(True), fixed.splitlines(True))
            for tag, i, j, a, b in matcher.get_opcodes():
                if tag != 'equal':
                    # Include surrounding context to make insertions uniquely applicable.
                    lo, hi = max(0,i-2), min(len(before.splitlines(True)),j+2)
                    old = ''.join(before.splitlines(True)[lo:hi])
                    new = ''.join(before.splitlines(True)[lo:i])+''.join(fixed.splitlines(True)[a:b])+''.join(before.splitlines(True)[j:hi])
                    reference.append({'path':path,'old':old,'new':new})
        retain(spec, 'reference', reference, 'Production-source changes from upstream correction '+spec['reference_commit']+'. Upstream tests are preserved at base.')
        if task_id == 'more-bucket':
            old='        self._validator = validator or (lambda x: True)'
            negative=[{'path':spec['allowed_paths'][0],'old':old,'new':'        self._validator = (lambda x: True) if validator is None else (validator if validator else lambda x: False)'}]
            alternate=[{'path':spec['allowed_paths'][0],'old':old,'new':'        if validator is None:\n            validator = lambda x: True\n        self._validator = validator'}]
        else:
            negative=[e for e in reference if e['path']=='boltons/dictutils.py']
            alternate=[{**e,'new':e['new'].replace('v = list(v)','v = tuple(v)')} for e in reference]
        retain(spec, 'negative', negative, 'Intentional partial fix: '+('treats all false-valued validators as reject-all, losing accepted keys.' if task_id=='more-bucket' else 'repairs dictutils but leaves the documented urlutils copy broken.'))
        retain(spec, 'alternate', alternate, 'Legitimate alternative implementation used to test implementation-neutral scoring.')


if __name__ == '__main__':
    main()
