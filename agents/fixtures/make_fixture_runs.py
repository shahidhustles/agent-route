"""Free end-to-end fixtures: build real files with the hand-written scripts in this folder, in the agent container, and
register each as a finished run in data/ui-runs, so the app shows them at /?run=fixture-<name> with no model call.

    .venv/bin/python agents/fixtures/make_fixture_runs.py          # create
    .venv/bin/python agents/fixtures/make_fixture_runs.py --clean  # delete the fixture runs
Restart the backend after creating or cleaning, because it reads data/ui-runs at start.
"""
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'agents'))
from adhoc import read_artifact_files  # noqa: E402
from validators.files import validate_files  # noqa: E402

RUNS = ROOT / 'data' / 'ui-runs'
SKILLS = ROOT / 'agents' / 'opencode' / 'skills-files'
FIXTURES = {
    'deck': ('slides', 'Build a three-slide pitch for a cold-chain trucking pilot.', 'node build/build_deck.js out/deck.pptx'),
    'doc': ('docx', 'Write a proposal for a weekend delivery pilot for a bakery.', 'node build/build_document.js out/document.docx'),
    'sheet': ('spreadsheet', 'Build a regional sales workbook with totals and a chart.',
              'python build/build_workbook.py out/workbook.xlsx && python /home/runner/.config/opencode/skills/xlsx/scripts/recalc.py out/workbook.xlsx'),
    'diagram': ('diagram', 'Draw the checkout flow.', 'cp build/diagram.html out/diagram.html'),
    'map': ('map', 'Map a walk between three Paris landmarks.', 'cp build/map.geojson out/map.geojson && python build/build_map.py out/map.geojson out/map.html'),
    'scene': ('scene-3d', 'Three floating cubes on a dark floor.', 'node build/build_scene.js out/scene.html'),
}


def make(name, agent, text, cmd):
    run = RUNS / f'fixture-{name}'
    shutil.rmtree(run, ignore_errors=True)
    ws = run / 'work'
    (ws / 'out').mkdir(parents=True)
    (ws / 'build').mkdir()
    for f in HERE.iterdir():
        if f.name.startswith('build') or f.suffix in ('.html', '.geojson'):
            shutil.copy(f, ws / 'build' / f.name)
    for d in (ws, ws / 'out', ws / 'build'):
        d.chmod(0o777)
    subprocess.run(['docker', 'run', '--rm', '--memory', '3g', '-v', f'{ws}:/work', '-v', f'{SKILLS}:/home/runner/.config/opencode/skills:ro',
                    'agent-route-opencode', 'bash', '-c', cmd], check=True, capture_output=True)
    check = validate_files(agent, {}, ws)
    artifact = read_artifact_files(agent, ws)
    state = {'id': f'fixture-{name}', 'text': text, 'agent': agent, 'model': 'z-ai/glm-5.3-flash', 'preference': 'balanced',
             'rerun_of': None, 'route': None, 'status': 'passed' if check['passed'] else 'failed', 'events': [],
             'started_at': '2026-11-02T00:00:00Z', 'csv_name': None, 'marked': None, 'mark_effect': None,
             'before': {'p_pass': 0.5, 'runs_seen': 0}, 'artifact': artifact,
             'result': {'status': 'passed' if check['passed'] else 'failed', 'detail': check['detail'], 'wall_s': 0.0, 'cost_usd': 0.0,
                        'input_tokens': 0, 'output_tokens': 0, 'final_text': 'Hand-written fixture, no model call.',
                        'appended': False, 'record_passed': None, 'contract': check}}
    (run / 'run.json').write_text(json.dumps(state))
    print(name, check)


if __name__ == '__main__':
    if '--clean' in sys.argv:
        for d in RUNS.glob('fixture-*'):
            shutil.rmtree(d)
        print('cleaned')
    else:
        for k, v in FIXTURES.items():
            make(k, *v)
