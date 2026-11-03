#!/usr/bin/env python3
"""One-image review of a .pptx or .docx: ar-look <file> <out.jpg>

Converts the file to PDF, renders every page small, and tiles them into one labelled contact sheet (up to 12 pages;
more go to <out>-2.jpg and so on). Read the sheet once instead of opening each page. Zoom into one page with
`pdftoppm -jpeg -r 110 -f N -l N <out>.pdf` only when a detail is unclear. The PDF is kept next to the image.
"""
import pathlib
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

PER_SHEET = 12


def main(src, out):
    src, out = pathlib.Path(src), pathlib.Path(out)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['soffice', '--headless', f'-env:UserInstallation=file://{tmp}/profile', '--convert-to', 'pdf',
                        '--outdir', tmp, str(src)], check=True, capture_output=True, timeout=150)
        pdf = pathlib.Path(tmp) / (src.stem + '.pdf')
        out.with_suffix('.pdf').write_bytes(pdf.read_bytes())
        subprocess.run(['pdftoppm', '-jpeg', '-r', '70', str(pdf), f'{tmp}/p'], check=True, capture_output=True, timeout=120)
        pages = sorted(pathlib.Path(tmp).glob('p-*.jpg'))
        if not pages:
            raise SystemExit('no pages rendered')
        for n, start in enumerate(range(0, len(pages), PER_SHEET)):
            chunk = pages[start:start + PER_SHEET]
            ims = [Image.open(p) for p in chunk]
            w, h = ims[0].size
            cols = 2 if w >= h else 4
            rows = -(-len(ims) // cols)
            sheet = Image.new('RGB', (cols * (w + 12) + 12, rows * (h + 34) + 12), (60, 60, 60))
            draw = ImageDraw.Draw(sheet)
            for i, im in enumerate(ims):
                x, y = 12 + (i % cols) * (w + 12), 12 + (i // cols) * (h + 34)
                draw.text((x, y + 4), f'page {start + i + 1}', fill=(255, 255, 255))
                sheet.paste(im, (x, y + 22))
            dest = out if n == 0 else out.with_name(f'{out.stem}-{n + 1}{out.suffix}')
            sheet.save(dest, quality=82)
            print(dest)
        print(f'{len(pages)} pages')


if __name__ == '__main__':
    main(*sys.argv[1:3])
