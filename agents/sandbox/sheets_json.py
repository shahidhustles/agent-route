#!/usr/bin/env python3
"""Print a workbook as JSON for the preview: per sheet, the displayed cell text with fill, font and alignment.

    ar-sheets-json <file.xlsx>

Values come from the cached results (`data_only`), falling back to the formula text when a cell was never
calculated. Number formats are applied for the common cases (percent, thousands, currency, dates, fixed decimals).
"""
import datetime
import json
import re
import sys

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

MAX_ROWS, MAX_COLS = 200, 40


def color(c):
    if c is not None and getattr(c, 'type', None) == 'rgb' and isinstance(c.rgb, str) and len(c.rgb) == 8 and c.rgb != '00000000':
        return '#' + c.rgb[2:]
    return None


def display(value, fmt):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, (int, float)):
        decimals = len(m[1]) if (m := re.search(r'0\.(0+)', fmt)) else 0
        if '%' in fmt:
            return f'{value * 100:,.{decimals}f}%'
        text = f'{abs(value):,.{decimals}f}' if ',' in fmt or '$' in fmt else f'{abs(value):.{decimals}f}' if '0.0' in fmt else f'{abs(value):g}'
        if '$' in fmt:
            text = '$' + text
        if value < 0:
            text = f'({text})' if '(' in fmt else '-' + text
        return text
    return str(value)


def main(path):
    values = load_workbook(path, data_only=True)
    formulas = load_workbook(path)
    sheets = []
    for ws in formulas.worksheets:
        vs = values[ws.title]
        rows, cols = min(ws.max_row, MAX_ROWS), min(ws.max_column, MAX_COLS)
        cells = []
        for r in range(1, rows + 1):
            row = []
            for c in range(1, cols + 1):
                cell, v = ws.cell(r, c), vs.cell(r, c).value
                if v is None and isinstance(cell.value, str) and cell.value.startswith('='):
                    v = cell.value
                fill = color(cell.fill.fgColor) if cell.fill and cell.fill.fill_type == 'solid' else None
                row.append({'v': display(v, cell.number_format), 'b': bool(cell.font.b), 'i': bool(cell.font.i),
                            'fg': color(cell.font.color), 'bg': fill, 'al': cell.alignment.horizontal,
                            'num': isinstance(v, (int, float)) and not isinstance(v, bool)})
            cells.append(row)
        widths = [(ws.column_dimensions[get_column_letter(c)].width or 10) for c in range(1, cols + 1)]
        sheets.append({'name': ws.title, 'rows': ws.max_row, 'cols': ws.max_column, 'cells': cells, 'widths': widths,
                       'merges': [str(m) for m in ws.merged_cells.ranges], 'charts': len(ws._charts), 'images': len(ws._images),
                       'freeze': ws.freeze_panes})
    print(json.dumps({'sheets': sheets}))


if __name__ == '__main__':
    main(sys.argv[1])
