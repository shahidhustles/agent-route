"""Build the phase 2 agent task suite.

    .venv/bin/python agents/tasks/build_tasks.py --version agents-v1

Writes benchmarking/suites/<version>.jsonl and <version>.manifest.json. Each task:

    {"id", "group", "agents": [acceptable agents, first is the gold label], "prompt",
     "inputs": {filename: text}, "checks": {agent: check spec}, "source"}

Single-agent tasks list one agent. Overlap tasks list every acceptable agent and
carry a check for each. Data tasks use seeded synthetic CSVs whose expected
values are computed here with pandas. Code tasks come from LiveCodeBench and
MBPP+ items that no earlier suite used.
"""
import argparse
import hashlib
import io
import json
import pathlib
import random
import re
import sys

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUITES = ROOT / 'benchmarking' / 'suites'
sys.path.insert(0, str(HERE))
import specs  # noqa: E402

REGIONS = ['North', 'South', 'East', 'West']
PRODUCTS = {'Widget': 12.5, 'Gadget': 24.0, 'Gizmo': 7.75, 'Doohickey': 41.0}
REPS = ['Asha', 'Ben', 'Chen', 'Dara', 'Eli', 'Farah', 'Gus', 'Hana']
TEAMS = ['Billing', 'Tech', 'Accounts']
PRIORITIES = ['Low', 'Medium', 'High', 'Urgent']
DEPTS = ['Engineering', 'Sales', 'Marketing', 'Finance', 'HR']
CITIES = ['Pune', 'Bengaluru', 'Mumbai', 'Delhi', 'Hyderabad']
FIRST = ['Aarav', 'Diya', 'Kabir', 'Meera', 'Rohan', 'Isha', 'Vikram', 'Sara', 'Arjun', 'Nisha', 'Dev', 'Tara',
         'Omar', 'Lena', 'Ravi', 'Zoya', 'Ian', 'Maya', 'Neel', 'Ana']
LAST = ['Shah', 'Iyer', 'Rao', 'Khan', 'Patel', 'Das', 'Mehta', 'Nair', 'Gupta', 'Singh', 'Joshi', 'Bose']


def csv_text(df):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def r4(x):
    return round(float(x), 4)


# --- datasets -------------------------------------------------------------

def make_sales(rng):
    rows = []
    dates = pd.date_range('2026-01-01', '2026-09-30', freq='D')
    for i in range(240):
        product = rng.choice(list(PRODUCTS))
        price = round(PRODUCTS[product] * rng.uniform(0.85, 1.15), 2)
        units = rng.randint(1, 50)
        rows.append({'order_id': f'O{1001 + i}', 'date': str(rng.choice(dates).date()), 'region': rng.choice(REGIONS),
                     'product': product, 'rep': rng.choice(REPS), 'units': units, 'unit_price': price,
                     'revenue': round(units * price, 2)})
    return pd.DataFrame(rows).sort_values(['date', 'order_id']).reset_index(drop=True)


def make_tickets(rng):
    rows = []
    dates = pd.date_range('2026-07-01', '2026-09-30', freq='D')
    for i in range(200):
        status = 'Closed' if rng.random() < 0.8 else 'Open'
        priority = rng.choices(PRIORITIES, weights=[4, 4, 2, 1])[0]
        hours = round(rng.uniform(0.5, 72) / (1 + PRIORITIES.index(priority)), 1) if status == 'Closed' else None
        csat = rng.randint(1, 5) if status == 'Closed' else None
        rows.append({'ticket_id': f'T{5001 + i}', 'opened': str(rng.choice(dates).date()), 'team': rng.choice(TEAMS),
                     'priority': priority, 'status': status, 'resolution_hours': hours, 'csat': csat})
    return pd.DataFrame(rows)


def make_employees(rng):
    rows, salaries = [], rng.sample(range(420, 2400), 120)
    for i in range(120):
        rows.append({'emp_id': f'E{301 + i}', 'name': f'{rng.choice(FIRST)} {rng.choice(LAST)}',
                     'dept': rng.choice(DEPTS), 'city': rng.choice(CITIES), 'salary': salaries[i] * 1000,
                     'start_year': rng.randint(2014, 2026), 'rating': rng.randint(1, 5)})
    return pd.DataFrame(rows)


def make_inventory(rng):
    cats = {'Electronics': ['Cable', 'Charger', 'Mouse', 'Keyboard', 'Headset'],
            'Office': ['Stapler', 'Binder', 'Notebook', 'Pen set', 'Desk lamp'],
            'Kitchen': ['Mug', 'Kettle', 'Bottle', 'Lunchbox'],
            'Cleaning': ['Spray', 'Wipes', 'Mop', 'Gloves']}
    suppliers = ['Acme Supply', 'Brightline', 'Corbel Ltd', 'Delta Traders', 'Evergreen Co']
    rows, i = [], 0
    for cat, items in cats.items():
        for item in items:
            for variant in ('S', 'M', 'L'):
                i += 1
                rows.append({'sku': f'SKU{100 + i}', 'item': f'{item} {variant}', 'category': cat,
                             'stock': rng.randint(0, 400), 'reorder_level': rng.choice([25, 50, 75, 100]),
                             'unit_cost': round(rng.uniform(1.5, 120), 2), 'supplier': rng.choice(suppliers)})
    return pd.DataFrame(rows)


def make_students(rng):
    rows = []
    for i in range(90):
        base = rng.uniform(40, 90)
        rows.append({'student_id': f'S{201 + i}', 'name': f'{rng.choice(FIRST)} {rng.choice(LAST)}',
                     'section': rng.choice('ABC'),
                     'math': min(100, max(0, round(base + rng.gauss(0, 10)))),
                     'science': min(100, max(0, round(base + rng.gauss(0, 10)))),
                     'english': min(100, max(0, round(rng.uniform(40, 95)))),
                     'attendance_pct': round(rng.uniform(60, 100), 1)})
    return pd.DataFrame(rows)


def make_weather(rng):
    base = {'Pune': 26, 'Delhi': 33, 'Chennai': 31}
    rows = []
    for d in pd.date_range('2026-06-01', '2026-08-31', freq='D'):
        for city, t in base.items():
            rain = round(max(0.0, rng.gauss(4 if city != 'Pune' else 9, 9)), 1)
            rows.append({'date': str(d.date()), 'city': city, 'temp_c': round(t + rng.gauss(0, 2.5) - rain * 0.08, 1),
                         'rain_mm': rain})
    return pd.DataFrame(rows)


STORE_SITES = [
    ('Pune Koregaon Park', 'Pune', 'Maharashtra', 'West', 73.8937, 18.5362),
    ('Pune Hinjewadi', 'Pune', 'Maharashtra', 'West', 73.7389, 18.5913),
    ('Mumbai Andheri', 'Mumbai', 'Maharashtra', 'West', 72.8697, 19.1136),
    ('Mumbai Lower Parel', 'Mumbai', 'Maharashtra', 'West', 72.8302, 18.9984),
    ('Nagpur Sitabuldi', 'Nagpur', 'Maharashtra', 'Central', 79.0806, 21.1458),
    ('Ahmedabad Navrangpura', 'Ahmedabad', 'Gujarat', 'West', 72.5600, 23.0365),
    ('Delhi Connaught Place', 'Delhi', 'Delhi', 'North', 77.2167, 28.6315),
    ('Gurugram Cyber City', 'Gurugram', 'Haryana', 'North', 77.0890, 28.4950),
    ('Jaipur MI Road', 'Jaipur', 'Rajasthan', 'North', 75.8069, 26.9157),
    ('Lucknow Hazratganj', 'Lucknow', 'Uttar Pradesh', 'North', 80.9462, 26.8500),
    ('Bengaluru Indiranagar', 'Bengaluru', 'Karnataka', 'South', 77.6408, 12.9784),
    ('Bengaluru Whitefield', 'Bengaluru', 'Karnataka', 'South', 77.7500, 12.9698),
    ('Chennai T Nagar', 'Chennai', 'Tamil Nadu', 'South', 80.2341, 13.0418),
    ('Hyderabad Hitech City', 'Hyderabad', 'Telangana', 'South', 78.3772, 17.4435),
    ('Kochi MG Road', 'Kochi', 'Kerala', 'South', 76.2875, 9.9658),
    ('Kolkata Park Street', 'Kolkata', 'West Bengal', 'East', 88.3520, 22.5530),
    ('Bhubaneswar Saheed Nagar', 'Bhubaneswar', 'Odisha', 'East', 85.8440, 20.2900),
    ('Guwahati Paltan Bazaar', 'Guwahati', 'Assam', 'East', 91.7500, 26.1820),
]


def make_stores(rng):
    sales = rng.sample(range(180, 990), len(STORE_SITES))
    staff = rng.sample(range(12, 75), len(STORE_SITES))
    return pd.DataFrame([{'store': s, 'city': c, 'state': st, 'region': rg, 'lat': lat, 'lon': lon,
                          'opened_year': rng.randint(2012, 2025), 'employees': staff[i], 'sales_2026': sales[i] * 1000}
                         for i, (s, c, st, rg, lon, lat) in enumerate(STORE_SITES)])


def messy(df, rng, text_cols, blank_col, n_blank=6, n_dup=5, blank_sentinel=''):
    """Add stray spaces, blanks in one column, and exact duplicate rows. Returns (messy_df, blanked keys)."""
    out = df.copy().astype(object)
    for col in text_cols:
        for i in rng.sample(range(len(out)), len(out) // 5):
            out.at[i, col] = rng.choice(['  ', ' ']) + str(out.at[i, col]) + rng.choice(['', ' ', '  '])
    blanked = rng.sample(range(len(out)), n_blank)
    for i in blanked:
        out.at[i, blank_col] = blank_sentinel
    dups = out.iloc[rng.sample(range(len(out)), n_dup)]
    out = pd.concat([out, dups]).sample(frac=1, random_state=rng.randint(0, 10**6)).reset_index(drop=True)
    return out, [df.iloc[i, 0] for i in blanked]


def clean_text(df, cols):
    df = df.copy()
    for c in cols:
        df[c] = df[c].astype(str).str.strip()
    return df


def pick(df, n, rng):
    idx = sorted(rng.sample(range(len(df)), min(n, len(df))))
    return df.iloc[idx]


def cells(df, key_cols, value_cols, rows):
    out = []
    for _, r in rows.iterrows():
        key = {k: (str(r[k]) if not isinstance(r[k], (int, float, np.integer, np.floating)) else r4(r[k])) for k in key_cols}
        for c in value_cols:
            v = r[c]
            out.append({'key': key, 'column': c, 'value': r4(v) if isinstance(v, (int, float, np.integer, np.floating)) else str(v)})
    return out


# --- spreadsheet tasks ----------------------------------------------------

def spreadsheet_tasks(rng, data):
    tasks = []

    def add(n, file, prompt, check, extra_inputs=None):
        tasks.append({'id': f'sheet-{n:02d}', 'group': 'spreadsheet', 'agents': ['spreadsheet'],
                      'prompt': f'{prompt} The data is in inputs/{file}.', 'inputs': {file: data[file]['text']},
                      'checks': {'spreadsheet': check}, 'source': 'synthetic'})

    s = data['sales_messy.csv']
    df, blanked = s['df'], s['blanked']
    text = ['region', 'product', 'rep']
    clean = clean_text(df, text).drop_duplicates().reset_index(drop=True)
    filled = clean.copy()
    filled['region'] = filled['region'].replace('', 'Unknown')
    add(1, 'sales_messy.csv', 'Clean this sales sheet: trim leading and trailing spaces in region, product, and rep, remove exact duplicate rows, and fill blank region values with "Unknown".',
        {'expect_rows': len(filled), 'expect_cells': cells(filled, ['order_id'], ['region'], filled[filled.order_id.isin(blanked[:3])])
         + cells(filled, ['order_id'], ['region', 'product'], pick(filled, 3, rng))})

    priced = clean.copy()
    priced['unit_price'] = priced['unit_price'].astype(str).str.replace('$', '', regex=False).astype(float)
    priced['revenue'] = priced['units'].astype(float) * priced['unit_price']
    priced = priced.sort_values('revenue', ascending=False, kind='stable')
    add(2, 'sales_messy.csv', 'unit_price is stored as text with a dollar sign. Remove exact duplicate rows, convert unit_price to a number, add a revenue column equal to units times unit_price, and sort by revenue from highest to lowest.',
        {'expect_rows': len(priced), 'expect_columns': ['revenue'],
         'expect_order': {'column': 'order_id', 'values': list(priced.order_id[:3])},
         'expect_cells': cells(priced, ['order_id'], ['revenue', 'unit_price'], pick(priced, 3, rng))})

    units = clean.groupby('product', as_index=False).agg(total_units=('units', lambda x: x.astype(int).sum()))
    add(3, 'sales_messy.csv', 'Trim spaces in the text columns, remove exact duplicate rows, then make a summary table with one row per product and a total_units column (sum of units).',
        {'expect_rows': len(units), 'expect_cells': cells(units, ['product'], ['total_units'], units)})

    west = clean[(clean.region == 'West') & (clean.units.astype(int) >= 20)].drop(columns=['notes'])
    add(4, 'sales_messy.csv', 'Trim spaces in the text columns and remove exact duplicate rows. Keep only orders from the West region with 20 or more units, and drop the notes column.',
        {'expect_rows': len(west), 'forbid_columns': ['notes'],
         'expect_cells': cells(west, ['order_id'], ['units', 'rep'], pick(west, 3, rng))})

    reps = priced.groupby('rep', as_index=False).agg(total_revenue=('revenue', 'sum')).sort_values('total_revenue', ascending=False)
    add(5, 'sales_messy.csv', 'Trim spaces, remove exact duplicate rows, convert unit_price (text with a dollar sign) to a number, compute revenue as units times unit_price, then summarise total_revenue per rep, sorted from highest to lowest.',
        {'expect_rows': len(reps), 'expect_order': {'column': 'rep', 'values': list(reps.rep[:3])},
         'expect_cells': cells(reps, ['rep'], ['total_revenue'], reps.head(4))})

    t = data['tickets_messy.csv']
    tdf = clean_text(t['df'], ['team']).drop_duplicates().reset_index(drop=True)
    cs = pd.to_numeric(tdf.csat.replace('', np.nan))
    filled = tdf.copy()
    filled['csat'] = cs.fillna(cs.median())
    add(6, 'tickets_messy.csv', 'Remove exact duplicate rows, then fill blank csat values with the median csat of the remaining rows.',
        {'expect_rows': len(filled),
         'expect_cells': cells(filled, ['ticket_id'], ['csat'], filled[filled.ticket_id.isin(t['blanked'][:3])])
         + cells(filled, ['ticket_id'], ['csat'], pick(filled[cs.notna()], 2, rng))})

    hot = tdf[tdf.priority.isin(['Urgent', 'High']) & (tdf.status == 'Open')].sort_values(['opened', 'ticket_id'])
    add(7, 'tickets_messy.csv', 'Remove exact duplicate rows. Keep only open tickets with priority Urgent or High, sorted by opened date, oldest first.',
        {'expect_rows': len(hot), 'expect_names': list(hot.ticket_id)})

    closed = tdf[tdf.status == 'Closed'].copy()
    closed['resolution_hours'] = pd.to_numeric(closed.resolution_hours)
    avg = closed.groupby('team', as_index=False).agg(avg_resolution_hours=('resolution_hours', 'mean'))
    add(8, 'tickets_messy.csv', 'Trim spaces in team and remove exact duplicate rows. For closed tickets only, make a table with one row per team and its avg_resolution_hours.',
        {'expect_rows': len(avg), 'expect_cells': cells(avg, ['team'], ['avg_resolution_hours'], avg)})

    counts = tdf.groupby(['team', 'priority'], as_index=False).agg(tickets=('ticket_id', 'count'))
    add(9, 'tickets_messy.csv', 'Trim spaces in team, remove exact duplicate rows, and count tickets for each team and priority combination in a column named tickets.',
        {'expect_rows': len(counts), 'expect_cells': cells(counts, ['team', 'priority'], ['tickets'], pick(counts, 4, rng))})

    e = data['employees.csv']['df']
    emp = e.rename(columns={'dept': 'department'}).assign(monthly_salary=e.salary / 12)
    add(10, 'employees.csv', 'Rename the dept column to department and add a monthly_salary column equal to salary divided by 12.',
        {'expect_rows': len(emp), 'expect_columns': ['department', 'monthly_salary'], 'forbid_columns': ['dept'],
         'expect_cells': cells(emp, ['emp_id'], ['monthly_salary', 'department'], pick(emp, 3, rng))})

    ranked = e.assign(salary_rank=e.groupby('dept').salary.rank(ascending=False, method='min').astype(int))
    add(11, 'employees.csv', 'Add a salary_rank column ranking employees by salary within their department, where rank 1 is the highest salary.',
        {'expect_rows': len(ranked), 'expect_cells': cells(ranked, ['emp_id'], ['salary_rank'], pick(ranked, 5, rng))})

    dept = e.groupby('dept', as_index=False).agg(avg_salary=('salary', 'mean'), headcount=('emp_id', 'count'))
    add(12, 'employees.csv', 'Summarise by dept: avg_salary (mean salary) and headcount (number of employees), one row per dept.',
        {'expect_rows': len(dept), 'expect_cells': cells(dept, ['dept'], ['avg_salary', 'headcount'], dept)})

    vet = e[(e.start_year <= 2020) & (e.rating >= 4)].drop(columns=['city'])
    add(13, 'employees.csv', 'Keep only employees who started in 2020 or earlier and have a rating of 4 or higher, and drop the city column.',
        {'expect_rows': len(vet), 'forbid_columns': ['city'], 'expect_names': list(vet.emp_id)})

    inv = data['inventory.csv']['df']
    short = inv.assign(shortfall=inv.reorder_level - inv.stock)
    short = short[short.shortfall > 0].sort_values('shortfall', ascending=False, kind='stable')
    add(14, 'inventory.csv', 'Add a shortfall column equal to reorder_level minus stock, keep only items whose shortfall is greater than 0, and sort by shortfall from largest to smallest.',
        {'expect_rows': len(short), 'expect_names': list(short.sku),
         'expect_cells': cells(short, ['sku'], ['shortfall'], short.head(3))})

    val = inv.assign(stock_value=inv.stock * inv.unit_cost).groupby('category', as_index=False).agg(stock_value=('stock_value', 'sum'))
    add(15, 'inventory.csv', 'Compute the stock value of each item (stock times unit_cost), then summarise total stock_value per category, one row per category.',
        {'expect_rows': len(val), 'expect_cells': cells(val, ['category'], ['stock_value'], val)})

    im = data['inventory_messy.csv']
    idf = clean_text(im['df'], ['supplier', 'item'])
    uc = pd.to_numeric(idf.unit_cost.replace('', np.nan))
    idf['unit_cost'] = uc.fillna(uc.mean())
    idf = idf.drop_duplicates(subset=['sku'])
    add(16, 'inventory_messy.csv', 'Trim spaces in supplier and item, fill blank unit_cost values with the mean unit_cost of the non-blank rows (computed before removing duplicates), then remove duplicate rows by sku, keeping the first.',
        {'expect_rows': len(idf), 'expect_cells': cells(idf, ['sku'], ['unit_cost'], idf[idf.sku.isin(im['blanked'][:3])])
         + cells(idf, ['sku'], ['supplier'], pick(idf, 2, rng))}, )
    st = data['students.csv']['df']
    tot = st.assign(total=st.math + st.science + st.english).sort_values('total', ascending=False, kind='stable')
    add(17, 'students.csv', 'Add a total column equal to math + science + english, and sort students by total from highest to lowest.',
        {'expect_rows': len(tot), 'expect_columns': ['total'],
         'expect_cells': cells(tot, ['student_id'], ['total'], pick(tot, 4, rng))})

    sec = st.groupby('section', as_index=False).agg(avg_math=('math', 'mean'))
    add(18, 'students.csv', 'Make a table with one row per section and the average math score as avg_math.',
        {'expect_rows': len(sec), 'expect_cells': cells(sec, ['section'], ['avg_math'], sec)})

    w = data['weather.csv']['df']
    wet = w[(w.city == 'Pune') & (w.rain_mm > 10)].sort_values('rain_mm', ascending=False, kind='stable')
    add(19, 'weather.csv', 'Keep only Pune rows with more than 10 mm of rain and sort them by rain_mm from highest to lowest.',
        {'expect_rows': len(wet), 'expect_cells': cells(wet, ['date', 'city'], ['rain_mm'], wet.head(3))})

    mx = w.groupby('city', as_index=False).agg(max_temp_c=('temp_c', 'max'))
    add(20, 'weather.csv', 'Make a table with one row per city and its highest temperature as max_temp_c.',
        {'expect_rows': len(mx), 'expect_cells': cells(mx, ['city'], ['max_temp_c'], mx)})
    return tasks


# --- data-analysis tasks --------------------------------------------------

def analysis_tasks(data):
    s, t, e = data['sales.csv']['df'], data['tickets.csv']['df'], data['employees.csv']['df']
    inv, st, w = data['inventory.csv']['df'], data['students.csv']['df'], data['weather.csv']['df']
    month = s.assign(month=s.date.str[:7]).groupby('month').revenue.sum()
    closed = t[t.status == 'Closed']
    st_tot = st.assign(total=st.math + st.science + st.english)
    by_rep = s.groupby('rep').revenue.sum()
    dl = w[w.city == 'Delhi']
    pune_jul = w[(w.city == 'Pune') & w.date.str.startswith('2026-07')]
    supplier_cost = inv.groupby('supplier').unit_cost.mean()
    inv_val = inv.assign(v=inv.stock * inv.unit_cost)
    q2 = s[(s['product'] == 'Gadget') & (s.date >= '2026-04-01') & (s.date <= '2026-06-30')]
    specs_ = [
        ('sales.csv', 'q1: total revenue across all orders. q2: the region with the highest total revenue. q3: the mean revenue per order. Chart revenue by region.',
         {'q1': s.revenue.sum(), 'q2': s.groupby('region').revenue.sum().idxmax(), 'q3': s.revenue.mean()}, None),
        ('sales.csv', 'q1: the month (YYYY-MM) with the highest total revenue. q2: the total revenue in that month. Chart the monthly revenue trend.',
         {'q1': month.idxmax(), 'q2': month.max()}, ['line', 'area', 'bar']),
        ('sales.csv', 'q1: how many orders have 40 or more units? q2: the median units per order.',
         {'q1': int((s.units >= 40).sum()), 'q2': s.units.median()}, None),
        ('sales.csv', 'q1: the percentage of total revenue that comes from the Widget product (0-100). Chart revenue share by product.',
         {'q1': 100 * s[s['product'] == 'Widget'].revenue.sum() / s.revenue.sum()}, ['pie', 'bar']),
        ('tickets.csv', 'q1: the mean resolution_hours of closed tickets. q2: the team with the most tickets. q3: the percentage of tickets with priority Urgent (0-100).',
         {'q1': closed.resolution_hours.mean(), 'q2': t.team.value_counts().idxmax(), 'q3': 100 * (t.priority == 'Urgent').mean()}, None),
        ('tickets.csv', 'q1: the average csat of closed Tech tickets. q2: the Pearson correlation between resolution_hours and csat over closed tickets.',
         {'q1': closed[closed.team == 'Tech'].csat.mean(), 'q2': closed.resolution_hours.corr(closed.csat)}, None),
        ('employees.csv', 'q1: the median salary. q2: the dept with the highest average salary. q3: the sample standard deviation of salary.',
         {'q1': e.salary.median(), 'q2': e.groupby('dept').salary.mean().idxmax(), 'q3': e.salary.std()}, None),
        ('employees.csv', 'q1: the number of employees in Engineering. q2: the average rating of employees whose start_year is after 2022. q3: the number of distinct cities.',
         {'q1': int((e.dept == 'Engineering').sum()), 'q2': e[e.start_year > 2022].rating.mean(), 'q3': e.city.nunique()}, None),
        ('inventory.csv', 'q1: the total stock value (sum of stock times unit_cost). q2: how many items have stock below their reorder_level? q3: the category with the highest stock value.',
         {'q1': inv_val.v.sum(), 'q2': int((inv.stock < inv.reorder_level).sum()), 'q3': inv_val.groupby('category').v.sum().idxmax()}, None),
        ('students.csv', 'q1: the mean math score. q2: the Pearson correlation between math and science. q3: how many students have attendance_pct below 75?',
         {'q1': st.math.mean(), 'q2': st.math.corr(st.science), 'q3': int((st.attendance_pct < 75).sum())}, ['scatter', 'bar', 'histogram']),
        ('students.csv', 'q1: the section with the highest average total score (math + science + english). q2: that section\'s average total.',
         {'q1': st_tot.groupby('section').total.mean().idxmax(), 'q2': st_tot.groupby('section').total.mean().max()}, None),
        ('weather.csv', 'q1: the date (YYYY-MM-DD) of the hottest day in Delhi. q2: its temp_c. q3: the total rain_mm in Chennai.',
         {'q1': dl.loc[dl.temp_c.idxmax(), 'date'], 'q2': dl.temp_c.max(), 'q3': w[w.city == 'Chennai'].rain_mm.sum()}, None),
        ('weather.csv', 'q1: the average temp_c in Pune in July 2026. q2: the number of days in Pune with rain_mm greater than 0 over the whole file.',
         {'q1': pune_jul.temp_c.mean(), 'q2': int(((w.city == 'Pune') & (w.rain_mm > 0)).sum())}, None),
        ('sales.csv', 'q1: the rep with the highest total revenue. q2: that rep\'s total revenue. Show the distribution of order revenue as a histogram.',
         {'q1': by_rep.idxmax(), 'q2': by_rep.max()}, ['histogram']),
        ('tickets.csv', 'q1: the median resolution_hours of closed Urgent tickets. q2: the median resolution_hours of closed Low tickets.',
         {'q1': closed[closed.priority == 'Urgent'].resolution_hours.median(), 'q2': closed[closed.priority == 'Low'].resolution_hours.median()}, None),
        ('employees.csv', 'q1: the 90th percentile of salary, using linear interpolation (the pandas default). q2: the average salary in Pune.',
         {'q1': e.salary.quantile(0.9), 'q2': e[e.city == 'Pune'].salary.mean()}, None),
        ('inventory.csv', 'q1: the supplier with the highest average unit_cost. q2: that average unit_cost. q3: the number of distinct suppliers.',
         {'q1': supplier_cost.idxmax(), 'q2': supplier_cost.max(), 'q3': inv.supplier.nunique()}, None),
        ('students.csv', 'q1: the percentage of students (0-100) who scored 60 or more in all three subjects (math, science, english).',
         {'q1': 100 * ((st.math >= 60) & (st.science >= 60) & (st.english >= 60)).mean()}, None),
        ('weather.csv', 'q1: the Pearson correlation between temp_c and rain_mm for Delhi. q2: the mean temp_c in Delhi. Show the relationship as a scatter chart.',
         {'q1': dl.temp_c.corr(dl.rain_mm), 'q2': dl.temp_c.mean()}, ['scatter']),
        ('sales.csv', 'q1: total units of Gadget sold in Q2 2026 (April to June, inclusive). q2: the number of distinct reps.',
         {'q1': int(q2.units.sum()), 'q2': s.rep.nunique()}, None),
    ]
    tasks = []
    for i, (file, questions, answers, chart_types) in enumerate(specs_, 1):
        # Correlations get a looser tolerance: agents may round them to two decimals.
        check = {'answers': {q: {'value': v if isinstance(v, str) else r4(v),
                                 **({'tol': 0.03} if f'{q}: the Pearson' in questions else {})}
                             for q, v in answers.items()}}
        if chart_types:
            check['chart_types'] = chart_types
        tasks.append({'id': f'analysis-{i:02d}', 'group': 'data-analysis', 'agents': ['data-analysis'],
                      'prompt': f'Analyse inputs/{file}. Answer these questions: {questions}',
                      'inputs': {file: data[file]['text']}, 'checks': {'data-analysis': check}, 'source': 'synthetic'})
    return tasks


# --- overlap: data tasks any of spreadsheet, data-analysis, code can do -----

def data_overlap_tasks(data):
    s, t, e = data['sales.csv']['df'], data['tickets.csv']['df'], data['employees.csv']['df']
    inv, st, w = data['inventory.csv']['df'], data['students.csv']['df'], data['weather.csv']['df']
    closed = t[t.status == 'Closed']
    q3 = s[s.date >= '2026-07-01']
    dl = w[w.city == 'Delhi'].assign(month=lambda d: d.date.str[:7])
    items = [
        ('sales.csv', 'Show total revenue per region.', s.groupby('region').revenue.sum()),
        ('sales.csv', 'Show total revenue for each month from January to September 2026.', s.groupby(s.date.str[:7]).revenue.sum()),
        ('sales.csv', 'How many units of each product did we sell in total?', s.groupby('product').units.sum()),
        ('sales.csv', 'What is the average revenue per order in each region?', s.groupby('region').revenue.mean()),
        ('tickets.csv', 'How many tickets did each team get?', t.team.value_counts()),
        ('tickets.csv', 'Compare average CSAT across teams for closed tickets.', closed.groupby('team').csat.mean()),
        ('tickets.csv', 'What is the average resolution time, in hours, of closed tickets for each priority?', closed.groupby('priority').resolution_hours.mean()),
        ('employees.csv', 'Show the average salary per department (the dept column).', e.groupby('dept').salary.mean()),
        ('employees.csv', 'How many employees work in each city?', e.city.value_counts()),
        ('inventory.csv', 'Show the total stock value (stock times unit_cost) for each category.', inv.assign(v=inv.stock * inv.unit_cost).groupby('category').v.sum()),
        ('students.csv', 'What are the class averages for math, science, and english?', st[['math', 'science', 'english']].mean()),
        ('students.csv', 'Compare the average total score (math + science + english) of each section.', st.assign(t=st.math + st.science + st.english).groupby('section').t.mean()),
        ('weather.csv', 'What was the average temperature in each city this summer?', w.groupby('city').temp_c.mean()),
        ('weather.csv', 'Show total rainfall per city.', w.groupby('city').rain_mm.sum()),
        ('sales.csv', 'Chart last quarter\'s sales (July to September 2026) by product, as total revenue.', q3.groupby('product').revenue.sum()),
        ('sales.csv', 'Who are the top 5 reps by total revenue, and how much did each bring in?', s.groupby('rep').revenue.sum().nlargest(5)),
        ('tickets.csv', 'How many tickets are open and how many are closed?', t.status.value_counts()),
        ('employees.csv', 'What is the average performance rating in each department (the dept column)?', e.groupby('dept').rating.mean()),
        ('inventory.csv', 'How many items does each supplier provide?', inv.supplier.value_counts()),
        ('weather.csv', 'What was the highest temperature in Delhi in each month (June, July, August 2026)?', dl.groupby('month').temp_c.max()),
    ]
    tasks = []
    for i, (file, question, series) in enumerate(items, 1):
        nums = [r4(v) for v in series.values]
        tasks.append({'id': f'overlap-data-{i:02d}', 'group': 'overlap', 'agents': ['data-analysis', 'spreadsheet', 'code'],
                      'prompt': f'{question} The data is in inputs/{file}.', 'inputs': {file: data[file]['text']},
                      'checks': {'data-analysis': {'expect_numbers': nums},
                                 'spreadsheet': {'expect_numbers': nums},
                                 'code': {'type': 'code_numbers', 'inputs': [file], 'expect_numbers': nums}},
                      'source': 'synthetic'})
    return tasks


def store_overlap_tasks(data):
    st = data['stores.csv']['df']
    lo5 = st.nsmallest(5, 'sales_2026')
    items = [
        ('Show the stores with 2026 sales above 600,000.', st[st.sales_2026 > 600_000]),
        ('Show all our stores in Maharashtra.', st[st.state == 'Maharashtra']),
        ('Show the stores opened after 2020.', st[st.opened_year > 2020]),
        ('Show the five stores with the lowest 2026 sales.', lo5),
        ('Show the stores in the South region.', st[st.region == 'South']),
        ('Show the stores with more than 40 employees.', st[st.employees > 40]),
    ]
    tasks = []
    for i, (question, sub) in enumerate(items, 1):
        names = list(sub.store)
        places = [{'name': r.store, 'lon': r.lon, 'lat': r.lat, 'tol_km': 2} for r in sub.itertuples()]
        tasks.append({'id': f'overlap-stores-{i:02d}', 'group': 'overlap', 'agents': ['map', 'spreadsheet'],
                      'prompt': f'{question} The store list, with coordinates, is in inputs/stores.csv.',
                      'inputs': {'stores.csv': data['stores.csv']['text']},
                      'checks': {'map': {'min_features': len(names), 'geometry_types': ['Point'], 'places': places, 'expect_names': names},
                                 'spreadsheet': {'expect_rows': len(names), 'expect_names': names}},
                      'source': 'synthetic'})
    return tasks


# --- open-ended tasks from specs.py ----------------------------------------

def spec_tasks():
    tasks = []
    for agent, prefix, rows in [('docx', 'docx', specs.DOCX), ('slides', 'slides', specs.SLIDES),
                                ('diagram', 'diagram', specs.DIAGRAM), ('map', 'map', specs.MAP),
                                ('scene-3d', 'scene', specs.SCENE)]:
        for i, (slug, prompt, check) in enumerate(rows, 1):
            tasks.append({'id': f'{prefix}-{i:02d}-{slug}', 'group': agent, 'agents': [agent], 'prompt': prompt,
                          'inputs': {}, 'checks': {agent: check}, 'source': 'hand-written'})
    for i, (slug, prompt, kws) in enumerate(specs.DOCX_OR_SLIDES, 1):
        tasks.append({'id': f'overlap-doc-{i:02d}-{slug.removeprefix("ov-")}', 'group': 'overlap', 'agents': ['docx', 'slides'],
                      'prompt': prompt, 'inputs': {},
                      'checks': {'docx': {'min_words': 200, 'keywords': kws}, 'slides': {'min_slides': 3, 'keywords': kws}},
                      'source': 'hand-written'})
    for i, (slug, prompt, kws, types) in enumerate(specs.DIAGRAM_OR_SLIDES, 1):
        tasks.append({'id': f'overlap-process-{i:02d}-{slug.removeprefix("ov-")}', 'group': 'overlap',
                      'agents': ['diagram', 'slides'], 'prompt': prompt, 'inputs': {},
                      'checks': {'diagram': {'diagram_types': types, 'keywords': kws},
                                 'slides': {'min_slides': 3, 'keywords': kws}},
                      'source': 'hand-written'})
    return tasks


# --- code tasks -----------------------------------------------------------

STDIO_SUFFIX = ('Write a complete Python 3 program that reads from standard input and writes to standard output. '
                'Your program will be run against hidden tests.')
FUNC_SUFFIX = 'Write the function in Python. It will be checked against hidden tests.'


def code_tasks(seed, n_lcb, n_mbpp):
    sys.path.insert(0, str(ROOT / 'benchmarking' / 'pool'))
    import build_suite as bs
    for version in ('pilot-v1', 'full-v1'):
        with open(SUITES / f'{version}.jsonl') as f:
            for line in f:
                m = re.search(r'"family_id": "([^"]+)"', line)
                if m:
                    bs.EXCLUDE.add(m.group(1))
    out = []
    for c in bs.livecodebench(random.Random(f'{seed}:lcb'), n_lcb):
        prompt = c['messages'][-1]['content'].replace(bs.CODE_SUFFIX, STDIO_SUFFIX)
        out.append((c, prompt))
    # test6 AtCoder items left after the earlier suites run short; MBPP+ fills the gap.
    n_mbpp += n_lcb - len(out)
    for c in bs.mbppplus(random.Random(f'{seed}:mbpp'), n_mbpp):
        prompt = c['messages'][-1]['content'].split('\n\nReply with')[0] + '\n\n' + FUNC_SUFFIX
        out.append((c, prompt))
    tasks = []
    for i, (c, prompt) in enumerate(out, 1):
        tasks.append({'id': f'code-{i:02d}-{c["id"]}', 'group': 'code', 'agents': ['code'], 'prompt': prompt,
                      'inputs': {}, 'checks': {'code': c['scoring']}, 'source': c['family_id'],
                      **({'difficulty': c['difficulty']} if 'difficulty' in c else {})})
    return tasks


def build_data(seed):
    rng = random.Random(f'{seed}:data')
    data = {}
    sales = make_sales(rng)
    data['sales.csv'] = {'df': sales}
    ms = sales.drop(columns=['revenue']).copy()
    ms['unit_price'] = ms['unit_price'].map(lambda p: f'${p:.2f}')
    ms['notes'] = [rng.choice(['', '', '', 'rush', 'gift wrap', 'call first']) for _ in range(len(ms))]
    m, blanked = messy(ms, rng, ['region', 'product', 'rep'], 'region')
    data['sales_messy.csv'] = {'df': m, 'blanked': blanked}
    tickets = make_tickets(rng)
    data['tickets.csv'] = {'df': tickets}
    tm = tickets.copy()
    closed_idx = [i for i in range(len(tm)) if tm.at[i, 'status'] == 'Closed']
    m, _ = messy(tm, rng, ['team'], 'csat', n_blank=0)
    m['csat'] = m['csat'].map(lambda v: '' if pd.isna(v) else str(int(v)))
    blank_ids = rng.sample([tm.at[i, 'ticket_id'] for i in closed_idx], 6)
    m.loc[m.ticket_id.isin(blank_ids), 'csat'] = ''
    m['resolution_hours'] = m['resolution_hours'].map(lambda v: '' if pd.isna(v) else v)
    data['tickets_messy.csv'] = {'df': m, 'blanked': blank_ids}
    data['employees.csv'] = {'df': make_employees(rng)}
    inv = make_inventory(rng)
    data['inventory.csv'] = {'df': inv}
    m, blanked = messy(inv, rng, ['supplier', 'item'], 'unit_cost', n_blank=5, n_dup=4)
    data['inventory_messy.csv'] = {'df': m, 'blanked': blanked}
    data['students.csv'] = {'df': make_students(rng)}
    data['weather.csv'] = {'df': make_weather(rng)}
    data['stores.csv'] = {'df': make_stores(rng)}
    for d in data.values():
        d['text'] = csv_text(d['df'])
    # Messy files are re-read as text, the way an agent sees them.
    for name in ('sales_messy.csv', 'tickets_messy.csv', 'inventory_messy.csv'):
        df = pd.read_csv(io.StringIO(data[name]['text']), keep_default_na=False, dtype=str)
        data[name]['df'] = df
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--version', required=True)
    parser.add_argument('--seed', type=int, default=20261028)
    parser.add_argument('--lcb', type=int, default=8)
    parser.add_argument('--mbpp', type=int, default=12)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)
    path = SUITES / f'{args.version}.jsonl'
    if path.exists() and not args.force:
        raise SystemExit(f'{path} exists; suites are immutable, pick a new version')
    data = build_data(args.seed)
    rng = random.Random(f'{args.seed}:checks')
    tasks = (code_tasks(args.seed, args.lcb, args.mbpp) + spreadsheet_tasks(rng, data) + analysis_tasks(data)
             + spec_tasks() + data_overlap_tasks(data) + store_overlap_tasks(data))
    ids = [t['id'] for t in tasks]
    assert len(ids) == len(set(ids)), 'duplicate task IDs'
    body = ''.join(json.dumps(t, ensure_ascii=False, default=float) + '\n' for t in tasks)
    path.write_text(body)
    groups, runs = {}, {}
    for t in tasks:
        groups[t['group']] = groups.get(t['group'], 0) + 1
        for a in t['agents']:
            runs[a] = runs.get(a, 0) + 1
    n_lcb = sum(t['source'].startswith('livecodebench') for t in tasks)
    manifest = {'version': args.version, 'seed': args.seed, 'tasks': len(tasks), 'groups': groups,
                'runs_per_model': runs, 'runs_per_model_total': sum(runs.values()),
                'code_sources': {'livecodebench': n_lcb, 'mbppplus': groups['code'] - n_lcb},
                'excluded_suites': ['pilot-v1', 'full-v1'], 'sha256': hashlib.sha256(body.encode()).hexdigest()}
    path.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=1))


if __name__ == '__main__':
    main()
