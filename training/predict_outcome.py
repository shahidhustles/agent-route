"""Score validation and test rows with a trained outcome router (GPU recommended).

    python training/predict_outcome.py --model artifacts/outcome-router/merged --out artifacts/outcome-router/predictions.jsonl

Pass the untrained base model as --model to get the zero-shot ablation. --format agent scores the agent
classifier on data/agents instead.
Each output line holds the row's case_id, split, router probabilities, and
the scoring time in milliseconds.
"""
import argparse
import json
import pathlib
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

import agent_router
import outcome_router

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--revision', default=None)
    parser.add_argument('--data-dir', type=pathlib.Path, default=ROOT / 'data' / 'outcome')
    parser.add_argument('--splits', nargs='+', default=['validation', 'test'])
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--format', choices=['outcome', 'agent'], default='outcome')
    args = parser.parse_args()
    score = (agent_router if args.format == 'agent' else outcome_router).candidate_probabilities

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, revision=args.revision, torch_dtype=torch.float16 if device == 'cuda' else torch.float32).to(device)
    model.eval()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w') as out:
        for split in args.splits:
            for line in (args.data_dir / f'{split}.jsonl').read_text().splitlines():
                row = json.loads(line)
                start = time.perf_counter()
                probs = score(model, tokenizer, row['input'])
                if device == 'cuda':
                    torch.cuda.synchronize()
                out.write(json.dumps({'case_id': row['case_id'], 'split': split, 'probabilities': probs,
                                      'routing_ms': round((time.perf_counter() - start) * 1000, 1)}) + '\n')
    print(f'wrote {args.out}')


if __name__ == '__main__':
    main()
