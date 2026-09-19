import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from common import label, validate_output, validate_request

ROOT = Path(__file__).resolve().parents[1]


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.splits = {s:[json.loads(line) for line in (ROOT/'data'/f'{s}.jsonl').read_text().splitlines()]
                      for s in ['train','validation','test']}

    def test_disjoint_families_and_requests(self):
        for left,right in [('train','validation'),('train','test'),('validation','test')]:
            self.assertFalse({r['metadata']['family_id'] for r in self.splits[left]} &
                             {r['metadata']['family_id'] for r in self.splits[right]})
            self.assertFalse({r['input']['user_task'] for r in self.splits[left]} &
                             {r['input']['user_task'] for r in self.splits[right]})

    def test_family_source_and_split_counts(self):
        source = json.loads((ROOT/'training/task_families.json').read_text())
        tasks = [task for category in source['categories'] for task in category['tasks']]
        self.assertEqual(len(tasks),120)
        self.assertEqual(len({task['family_id'] for task in tasks}),120)
        self.assertEqual({split:sum(task['split']==split for task in tasks)
                          for split in ['train','validation','test']},
                         {'train':80,'validation':20,'test':20})
        self.assertFalse(any('mrpl' in task['text'].lower() for task in tasks))

    def test_manifest_matches_saved_bytes(self):
        manifest = json.loads((ROOT/'data/manifest.json').read_text())
        self.assertEqual(manifest['profile_version'],'benchmark-v1-20260919T110437Z-272c')
        self.assertEqual(manifest['family_source']['sha256'],
            hashlib.sha256((ROOT/'training/task_families.json').read_bytes()).hexdigest())
        for split,rows in self.splits.items():
            self.assertEqual(manifest['splits'][split]['count'],len(rows))
            self.assertEqual(manifest['splits'][split]['sha256'],
                hashlib.sha256((ROOT/'data'/f'{split}.jsonl').read_bytes()).hexdigest())

    def test_all_labels_and_anonymization(self):
        for rows in self.splits.values():
            self.assertGreaterEqual(sum(r['metadata']['anonymous'] for r in rows)/len(rows),.3)
            for row in rows:
                self.assertEqual(set(row['input']['candidate_models']),
                    {profile['model_slug'] for profile in row['input']['profiles']})
                self.assertEqual(len(row['input']['profiles']),2)
                validate_request(row['input'])
                self.assertEqual(validate_output(json.dumps(row['output']),row['input']),row['output'])
                self.assertEqual(label(row['input'],row['metadata']['requirements']),row['output'])

    def test_teacher_uses_profiles_not_names_or_order(self):
        for row in self.splits['test']:
            request = copy.deepcopy(row['input'])
            request['profiles'].reverse()
            request['candidate_models'].reverse()
            self.assertEqual(label(request,row['metadata']['requirements']),row['output'])
            mapping = {slug:f'unseen_{i}' for i,slug in enumerate(request['candidate_models'])}
            for p in request['profiles']:
                p['model_slug'] = mapping[p['model_slug']]
            request['candidate_models'] = [mapping[s] for s in request['candidate_models']]
            self.assertEqual(label(request,row['metadata']['requirements'])['model_slug'],mapping[row['output']['model_slug']])

    def test_reject_invalid_output(self):
        request = self.splits['test'][0]['input']
        for raw in ['{}','not json',json.dumps({'model_slug':'missing','confidence':.9}),
                    json.dumps({'model_slug':request['candidate_models'][0],'confidence':True}),
                    json.dumps({'model_slug':request['candidate_models'][0],'confidence':float('nan')})]:
            with self.assertRaises(ValueError):
                validate_output(raw,request)

    def test_hard_constraints_and_vision_pool(self):
        request = copy.deepcopy(self.splits['test'][0]['input'])
        candidate = request['profiles'][0]
        candidate['features']['multimodal'] = False
        candidate['features']['tool_calling'] = True
        request['requires_tools'] = True
        request['input_tokens'] = 1
        output = json.dumps({'model_slug':candidate['model_slug'],'confidence':.7})
        validate_output(output,request)
        candidate['features']['tool_calling'] = False
        with self.assertRaises(ValueError):
            validate_output(output,request)
        request['requires_tools'] = False
        request['input_tokens'] = candidate['runtime']['usable_context']+1
        with self.assertRaises(ValueError):
            validate_output(output,request)

    def test_held_out_evaluation_requires_explicit_flag(self):
        result = subprocess.run([sys.executable,str(ROOT/'training/evaluate.py'),
            '--model','unused','--split','test','--report','unused.json'],
            capture_output=True,text=True,check=False)
        self.assertEqual(result.returncode,2)
        self.assertIn('--allow-held-out-test',result.stderr)


if __name__ == '__main__':
    unittest.main()
