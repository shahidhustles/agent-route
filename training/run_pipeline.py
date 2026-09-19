"""Run training and evaluation sequentially; persist progress and failures locally."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='Qwen/Qwen3-0.6B')
    parser.add_argument('--epochs', type=float, default=2)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--accumulation', type=int, default=2)
    parser.add_argument('--resume')
    parser.add_argument('--adapter', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/qwen3-router')
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True,exist_ok=True)
    status_file = output/'pipeline-status.json'
    def status(stage, **details):
        state = {'stage':stage,'updated_at':datetime.now(timezone.utc).isoformat(),**details}
        temporary = status_file.with_suffix('.tmp')
        temporary.write_text(json.dumps(state,indent=2))
        temporary.replace(status_file)
        print(json.dumps(state),flush=True)
    def run(stage, command):
        status(stage)
        with (output/f'{stage}.log').open('a',encoding='utf-8') as log:
            result = subprocess.run([sys.executable,'-u',*command],stdout=log,
                stderr=subprocess.STDOUT,check=False)
        if result.returncode:
            status('failed',failed_stage=stage,exit_code=result.returncode)
            raise SystemExit(result.returncode)
    command = [str(ROOT/'training/train.py'),'--model',args.model,'--output',str(output),
        '--epochs',str(args.epochs),'--batch-size',str(args.batch_size),'--accumulation',str(args.accumulation)]
    if args.resume:
        command += ['--resume',args.resume]
    if args.adapter:
        command += ['--adapter',str(args.adapter)]
    run('training',command)
    run('evaluating_validation',[str(ROOT/'training/evaluate.py'),'--model',str(output/'merged'),
        '--split','validation','--report',str(output/'validation-report.json')])
    report = json.loads((output/'validation-report.json').read_text())
    metrics = report['original']
    invalid_rate = 1 - metrics['raw_valid_format_rate']
    violations = metrics['raw_constraint_violation_rate']
    if metrics['accuracy'] < .8 or invalid_rate >= .01 or violations != 0:
        status('evaluation_below_target',split='validation',accuracy=metrics['accuracy'],
            invalid_output_rate=invalid_rate,constraint_violation_rate=violations,
            note='Checkpoint exists but is not validated. The held-out test remains sealed.')
        return
    data_manifest_path = ROOT/'data/manifest.json'
    training_report_path = output/'training-report.json'
    training_manifest = {
        'data_manifest': json.loads(data_manifest_path.read_text()),
        'data_manifest_sha256': hashlib.sha256(data_manifest_path.read_bytes()).hexdigest(),
        'training_report': json.loads(training_report_path.read_text()),
        'training_report_sha256': hashlib.sha256(training_report_path.read_bytes()).hexdigest(),
        'validation_report_sha256': hashlib.sha256((output/'validation-report.json').read_bytes()).hexdigest(),
        'validation': metrics,
        'held_out_test_opened': False,
    }
    (output/'training-manifest.json').write_text(json.dumps(training_manifest,indent=2)+'\n')
    status('validated',accuracy=metrics['accuracy'],invalid_output_rate=invalid_rate,
        constraint_violation_rate=violations,
        note='Artifacts are frozen for review. Open the held-out test only with its explicit evaluator flag.')


if __name__ == '__main__':
    main()
