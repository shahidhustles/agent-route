"""Run one OpenCode agent on a free-text task, for the web app.

`agents/run.py` needs a suite task, because its validators read the task's checks. A prompt typed into the app has
no checks, so this module runs the same agent in the same Docker sandbox through the same proxy and validates the
artifact against its output contract only: the file exists and parses, and the format rules of the validator hold.
Content checks (expected numbers, keywords) are absent, which is why a contract pass is recorded as `passed: null`
until the user marks the result.

Progress comes from the OpenCode event stream (`--format json`), one JSON event per line, forwarded as it arrives.
"""
import ast
import json
import pathlib
import re
import subprocess
import sys
import threading
import time
import uuid

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cmdproxy  # noqa: E402
from run import docker_argv, is_rate_limited, parse_events, prepare_workspace  # noqa: E402
from validators import ARTIFACTS, validate  # noqa: E402
from validators import files as file_contract  # noqa: E402

STOP_MARKERS = (cmdproxy.CAP_MARKER, cmdproxy.WEEKLY_MARKER)
TEXT_LIMIT = 400_000  # bytes read per artifact file
TEXT_SUFFIXES = {'.html', '.geojson', '.py', '.json', '.csv', '.jsonl', '.md', '.txt'}


def free_text_detail(agent, detail):
    """Reword a passing suite-validator message for a free-text run, so it claims only what was checked.

    The suite validators say "expected cells match" or "3 answers correct" because suite tasks carry gold values.
    A typed prompt has none, so those words would claim a check that never ran. `agents/validators` keeps its
    wording for suite runs; this rewrite happens only on the free-text path.
    """
    m = re.fullmatch(r'(\d+) ops, (\d+) rows, expected cells match', detail)
    if agent == 'spreadsheet' and m:
        return f'format valid: spreadsheet has the required files ({m[1]} ops, {m[2]} rows). Cell values were not checked.'
    m = re.fullmatch(r'(\d+) answers correct, (\w+) chart with (\d+) points', detail)
    if agent == 'data-analysis' and m:
        return (f'format valid: analysis has {m[1]} answers and a {m[2]} chart with {m[3]} points. '
                'The answers were not checked.')
    return detail


def contract_check(agent, ws):
    """Output-contract validation of a live run. Code is checked for valid Python syntax; every other agent's real file
    is opened by `validators/files.py` (slide count, text present, file opens). The JSON suite validators are not used here."""
    if agent != 'code':
        return file_contract.validate_files(agent, {}, ws)
    if agent == 'code':
        path = ws / 'out' / 'solution.py'
        if not path.is_file():
            return {'passed': False, 'detail': 'missing artifact out/solution.py'}
        try:
            ast.parse(path.read_text())
        except SyntaxError as e:
            return {'passed': False, 'detail': f'solution.py has a syntax error: {e.msg} (line {e.lineno})'}
        if not path.read_text().strip():
            return {'passed': False, 'detail': 'solution.py is empty'}
        return {'passed': True, 'detail': 'solution.py parses'}
    result = validate(agent, {}, ws)
    if result['passed']:
        result = {**result, 'detail': free_text_detail(agent, result['detail'])}
    return result


def read_artifact_files(agent, ws):
    """The files of a live run: text files as text, Office files as sizes (the backend serves and previews the bytes)."""
    ws = pathlib.Path(ws)
    files, binary = {}, {}
    for rel in file_contract.ARTIFACTS[agent]:
        path = ws / rel
        if not path.is_file():
            continue
        if path.suffix in TEXT_SUFFIXES:
            files[path.name] = path.read_bytes()[:TEXT_LIMIT].decode('utf-8', errors='replace')
        else:
            binary[path.name] = path.stat().st_size
    # A request the router sent to the wrong agent can still end in a real file under another name (a deck written by
    # the diagram agent). Keep it so the panel shows it, even though the run misses its own contract.
    out = ws / 'out'
    for path in sorted(out.glob('*')) if out.is_dir() else []:
        if not path.is_file() or path.name in files or path.name in binary or not re.fullmatch(r'[\w.-]{1,80}', path.name):
            continue
        if path.suffix == '.html':
            files[path.name] = path.read_bytes()[:TEXT_LIMIT].decode('utf-8', errors='replace')
        elif path.suffix in ('.pptx', '.docx', '.xlsx'):
            binary[path.name] = path.stat().st_size
    return {'agent': agent, 'files': files, 'binary': binary, 'contract': 'files'}


def read_artifact(agent, ws):
    """The artifact files an agent writes, as text, for the UI. A missing file is left out."""
    ws = pathlib.Path(ws)
    files = {}
    for rel in ARTIFACTS[agent]:
        path = ws / rel
        if path.is_file() and not rel.endswith('.docx'):
            files[pathlib.Path(rel).name] = path.read_bytes()[:TEXT_LIMIT].decode('utf-8', errors='replace')
    docx = ws / 'out' / 'document.docx'
    return {'agent': agent, 'files': files, 'binary': {'document.docx': docx.stat().st_size} if docx.is_file() else {}}


def summarize_event(ev):
    """One progress line per OpenCode event, or None for events with nothing to show."""
    kind, part = ev.get('type'), ev.get('part') or {}
    if kind == 'reasoning':
        text = (part.get('text') or '').strip()
        return {'kind': 'thinking', 'text': text[:2000]} if text else None
    if kind == 'tool_use':
        state = part.get('state') or {}
        inp = state.get('input') or {}
        detail = inp.get('command') or inp.get('filePath') or inp.get('path') or inp.get('pattern') or ''
        status = state.get('status')
        if part.get('tool') == 'skill':
            detail = f"loaded {inp.get('id') or inp.get('name') or 'a skill'}"
        if status == 'error':
            detail = f'{detail} (error)'
        return {'kind': 'tool', 'tool': part.get('tool', 'tool'), 'text': str(detail).strip().splitlines()[0][:160] if detail else ''}
    if kind == 'text':
        return {'kind': 'text', 'text': (part.get('text') or '')[:2000]}
    if kind == 'step_finish':
        tok = part.get('tokens') or {}
        return {'kind': 'tokens', 'input': tok.get('input', 0), 'output': tok.get('output', 0)}
    if kind == 'error':
        err = ev.get('error') or {}
        return {'kind': 'error', 'text': str(err.get('message') or err.get('data') or err)[:300]}
    return None


def run_adhoc(run_dir, text, agent, model, proxy, emit, csv=None, timeout_s=900):
    """Run `agent` on `text` with `model` (a base ID such as deepseek/deepseek-v4.1-flash). Returns a result dict.

    `emit(event)` receives progress events. `csv` is an optional (name, body) input file. Never raises on a failed
    run: the result's `status` is passed, failed, stopped, or error.
    """
    run_dir = pathlib.Path(run_dir)
    ws = run_dir / 'work'
    inputs = {csv[0]: csv[1]} if csv else None
    prepare_workspace(ws, {'inputs': inputs})
    prompt = text if not csv else f'{text}\n\nThe input file is inputs/{csv[0]}.'
    token = proxy.new_token()
    env = {'CC_BASE_URL': proxy.url, 'CC_RUN_TOKEN': token}
    name = f'ar-{uuid.uuid4().hex[:12]}'
    argv = docker_argv(name, ws, agent, f'cc/{model}', prompt, env, contract='files')
    start = time.time()
    emit({'kind': 'start', 'agent': agent, 'model': model})
    lines, timed_out = [], False
    stderr_path = run_dir / 'stderr.txt'
    with stderr_path.open('w') as err_file:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=err_file, text=True, bufsize=1)
        killed = threading.Event()

        def kill():
            killed.set()
            subprocess.run(['docker', 'kill', name], capture_output=True)

        timer = threading.Timer(timeout_s, kill)
        timer.start()
        try:
            for line in proc.stdout:
                lines.append(line)
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                out = summarize_event(ev)
                if out:
                    out['t'] = round(time.time() - start, 1)
                    emit(out)
            proc.wait()
        finally:
            timed_out = killed.is_set()
            timer.cancel()
    wall = time.time() - start
    stdout = ''.join(lines)
    (run_dir / 'events.jsonl').write_text(stdout)
    stderr = stderr_path.read_text()[-2000:] if stderr_path.exists() else ''
    usage = proxy.take(token) or {'usd': 0.0, 'requests': 0, 'prompt_tokens': 0, 'cached_tokens': 0,
                                  'completion_tokens': 0, 'usage_missing': 0}
    stats = parse_events(stdout)
    err_text = ' '.join(stats['errors']) + ' ' + stderr
    base = {'wall_s': round(wall, 2), 'cost_usd': round(usage['usd'], 6), 'proxy_requests': usage['requests'],
            'input_tokens': stats['input_tokens'] + stats['cache_read_tokens'], 'output_tokens': stats['output_tokens'],
            'tool_calls': stats['tool_calls'], 'final_text': stats['final_text'], 'errors': stats['errors'][:5]}
    if proxy.stopped or any(m in err_text for m in STOP_MARKERS):
        reason = proxy.stopped or cmdproxy.WEEKLY_MARKER
        return {**base, 'status': 'stopped', 'detail': f'provider limit: {reason}', 'contract': None}
    if timed_out:
        contract = contract_check(agent, ws)
        if contract['passed']:
            return {**base, 'status': 'passed', 'contract': contract,
                    'detail': f'cut off at {timeout_s} s while polishing, but the file is complete: {contract["detail"]}'}
        return {**base, 'status': 'failed', 'detail': f'timed out after {timeout_s} s', 'contract': contract}
    if stats['errors'] and is_rate_limited(err_text) and not any((ws / 'out').iterdir()):
        return {**base, 'status': 'error', 'detail': 'rate limited: ' + err_text.strip()[:200], 'contract': None}
    contract = contract_check(agent, ws)
    return {**base, 'status': 'passed' if contract['passed'] else 'failed', 'detail': contract['detail'],
            'contract': contract}
