"""Free fixture: a hand-written openpyxl workbook with formulas, formatting, a frozen header and a native chart."""
import sys
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill

wb = Workbook()
ws = wb.active
ws.title = 'Sales'
head = ['Region', 'Units', 'Price', 'Revenue']
ws.append(head)
rows = [('North', 120, 4.5), ('South', 95, 4.5), ('East', 143, 4.25), ('West', 80, 4.75)]
for i, (r, u, p) in enumerate(rows, start=2):
    ws.append([r, u, p, f'=B{i}*C{i}'])
ws.append(['Total', '=SUM(B2:B5)', None, '=SUM(D2:D5)'])
for c in ws[1]:
    c.font = Font(name='Arial', bold=True, color='FFFFFF')
    c.fill = PatternFill('solid', fgColor='1F5C4A')
    c.alignment = Alignment(horizontal='center')
for row in ws.iter_rows(min_row=2):
    for c in row:
        c.font = Font(name='Arial', bold=(row[0].value == 'Total'))
for r in range(2, 7):
    ws.cell(r, 3).number_format = '$#,##0.00'
    ws.cell(r, 4).number_format = '$#,##0.00'
ws.column_dimensions['A'].width = 14
for col in 'BCD':
    ws.column_dimensions[col].width = 12
ws.freeze_panes = 'A2'
chart = BarChart()
chart.title = 'Revenue by region'
chart.y_axis.title = 'USD'
chart.add_data(Reference(ws, min_col=4, min_row=1, max_row=5), titles_from_data=True)
chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=5))
chart.legend = None
ws.add_chart(chart, 'F2')
notes = wb.create_sheet('Notes')
notes.append(['Assumption', 'Prices are per unit and held constant across the period.'])
wb.save(sys.argv[1] if len(sys.argv) > 1 else 'out/workbook.xlsx')
