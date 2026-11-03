"""Convert an agent's Office file into page images for the artifact panel.

Agent output is untrusted, so LibreOffice runs in a throwaway container with no network, a read-only root and
read-only input. The container is the same image the agents run in (`ar-preview` inside it does the work). Results
are cached beside the run: <out>/page-N.jpg, thumb-N.jpg, file.pdf, manifest.json, and sheets.json for workbooks.
"""
import json
import pathlib
import shutil
import subprocess
import threading
import uuid

IMAGE = 'agent-route-opencode'
OFFICE = {'.pptx', '.docx', '.xlsx'}
_locks = {}
_locks_guard = threading.Lock()


class PreviewError(Exception):
    pass


def preview_argv(name, src_dir, file_name, out_dir):
    return ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only', '--tmpfs', '/tmp:rw,size=768m',
            '--memory', '2g', '--cpus', '2', '--pids-limit', '256', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '-e', 'HOME=/tmp', '-v', f'{src_dir}:/in:ro', '-v', f'{out_dir}:/out', IMAGE, 'ar-preview', f'/in/{file_name}', '/out']


def build_preview(src, out_dir, timeout_s=240):
    """Return the manifest for `src`, converting once and caching under `out_dir`."""
    src, out_dir = pathlib.Path(src).resolve(), pathlib.Path(out_dir).resolve()
    if src.suffix.lower() not in OFFICE:
        raise PreviewError(f'{src.name} is not a PowerPoint, Word or Excel file')
    if not src.is_file():
        raise PreviewError(f'{src.name} does not exist')
    manifest = out_dir / 'manifest.json'
    with _locks_guard:
        lock = _locks.setdefault(str(out_dir), threading.Lock())
    with lock:
        if manifest.is_file() and manifest.stat().st_mtime >= src.stat().st_mtime:
            return json.loads(manifest.read_text())
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True)
        out_dir.chmod(0o777)  # the container runs as uid 1000, which may not own this directory
        name = f'ar-prev-{uuid.uuid4().hex[:10]}'
        try:
            proc = subprocess.run(preview_argv(name, src.parent, src.name, out_dir), capture_output=True, text=True,
                                  timeout=timeout_s)
        except subprocess.TimeoutExpired:
            subprocess.run(['docker', 'kill', name], capture_output=True)
            raise PreviewError(f'Converting {src.name} took longer than {timeout_s} s and was stopped.')
        if proc.returncode != 0 or not manifest.is_file():
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ['no output']
            raise PreviewError(f'LibreOffice could not convert {src.name}: {tail[0][:200]}')
        return json.loads(manifest.read_text())
