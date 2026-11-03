#!/usr/bin/env python3
"""Turn an agent's .pptx, .docx or .xlsx into page images, inside the no-network preview container.

    ar-preview <input file> <output dir>

Writes <out>/page-N.jpg (readable size), <out>/thumb-N.jpg, <out>/file.pdf and <out>/manifest.json. A workbook also
gets <out>/sheets.json (cells, formatting, merges, column widths) from ar-sheets-json. The input is untrusted,
so the backend runs this with --network none and the input mounted read-only.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

MAX_PAGES = 80


def main(src, out):
    src, out = pathlib.Path(src), pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    kind = src.suffix.lower().lstrip('.')
    manifest = {'kind': kind, 'pages': 0, 'sheets': False}
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['soffice', '--headless', f'-env:UserInstallation=file://{tmp}/profile', '--convert-to', 'pdf',
                        '--outdir', tmp, str(src)], check=True, capture_output=True, timeout=150)
        pdf = pathlib.Path(tmp) / (src.stem + '.pdf')
        if not pdf.is_file():
            raise SystemExit('LibreOffice produced no PDF')
        (out / 'file.pdf').write_bytes(pdf.read_bytes())
        for prefix, args in (('page', ['-r', '90']), ('thumb', ['-scale-to', '240'])):
            subprocess.run(['pdftoppm', '-jpeg', '-l', str(MAX_PAGES), *args, str(pdf), f'{tmp}/{prefix}'], check=True,
                           capture_output=True, timeout=120)
            for path in pathlib.Path(tmp).glob(f'{prefix}-*.jpg'):
                n = int(re.search(r'-(\d+)\.jpg$', path.name)[1])
                (out / f'{prefix}-{n}.jpg').write_bytes(path.read_bytes())
        manifest['pages'] = len(list(out.glob('page-*.jpg')))
    if kind == 'xlsx':
        sheets = subprocess.run(['ar-sheets-json', str(src)], check=True, capture_output=True, text=True, timeout=60).stdout
        (out / 'sheets.json').write_text(sheets)
        manifest['sheets'] = True
    (out / 'manifest.json').write_text(json.dumps(manifest))


if __name__ == '__main__':
    main(*sys.argv[1:3])
