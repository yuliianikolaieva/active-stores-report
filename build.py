import csv, json
from collections import defaultdict

BASE = "/Users/yuliia.nikolaieva/Downloads/Active store"
SRC = "/Users/yuliia.nikolaieva/Downloads/Active store/active_stores_from_dbx.csv"
OUT = BASE + "/active-stores-dynamics.html"

rows = list(csv.DictReader(open(SRC)))
SEGS = ['ent','mm','smb']
MON  = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
MONF = {1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}

# ── Segment comes from Business Segment Code V2 ──
def seg_of(r):
    c = r['Business Segment Code V2']
    if c == 'ENT-NC': return 'ent'
    if c == 'MM': return 'mm'
    if c == 'SMB': return 'smb'
    return 'ent' if r['Delivery Vertical'] == 'store_3p_ent' else 'smb'

def is_archived(p): return '[Archived]' in p

# Data is WEEKLY snapshots (YYYY-MM-DD). Monthly metrics use the last snapshot of each month.
weeks = sorted(set(r['Report Time (dynamic)'] for r in rows))
final_week = weeks[-1]
month_strs = sorted(set(w[:7] for w in weeks))
month_end = {}
for w in weeks:
    month_end[w[:7]] = w  # weeks sorted asc -> last write is latest snapshot of that month
mkey   = {ms: MON[int(ms[5:7])].lower() for ms in month_strs}
mshort = {ms: MON[int(ms[5:7])] for ms in month_strs}

brand_week_stores = defaultdict(lambda: defaultdict(set))
brand_seg_votes = defaultdict(lambda: defaultdict(int))
provider_weeks = defaultdict(set)
provider_rec = {}   # provider -> [week, brand, seg] of its latest active snapshot

for r in rows:
    p = r['Provider Name']
    if is_archived(p): continue
    brand = r['Brand Name'].strip()
    if not brand: continue
    s = seg_of(r)
    w = r['Report Time (dynamic)']
    brand_week_stores[brand][w].add(p)
    brand_seg_votes[brand][s] += 1
    provider_weeks[p].add(w)
    if p not in provider_rec or w >= provider_rec[p][0]:
        provider_rec[p] = [w, brand, s]

brand_seg = {b: max(v, key=v.get) for b, v in brand_seg_votes.items()}

def bcount(b, ms):  # store count for a brand at the month-end snapshot
    return len(brand_week_stores[b].get(month_end[ms], ()))

provider_first_week  = {p: min(ws) for p, ws in provider_weeks.items()}
provider_first_month = {p: provider_first_week[p][:7] for p in provider_weeks}
provider_seg = {p: provider_rec[p][2] for p in provider_weeks}

monthly = {}
for ms in month_strs:
    c = {s:0 for s in SEGS}
    for b in brand_week_stores:
        c[brand_seg[b]] += bcount(b, ms)
    c['total'] = sum(c[s] for s in SEGS)
    monthly[mkey[ms]] = c

new_stores = {mkey[ms]: {**{s:0 for s in SEGS}, 'total':0} for ms in month_strs}
for p in provider_weeks:
    k = mkey[provider_first_month[p]]
    new_stores[k][provider_seg[p]] += 1
    new_stores[k]['total'] += 1

brand_first_month = {b: min(brand_week_stores[b])[:7] for b in brand_week_stores}

new_brands = {mkey[ms]: {**{s:0 for s in SEGS}, 'total':0, 'list':[]} for ms in month_strs}
for b in brand_week_stores:
    fm = brand_first_month[b]; s = brand_seg[b]; k = mkey[fm]
    new_brands[k][s]+=1; new_brands[k]['total']+=1
    new_brands[k]['list'].append((b, bcount(b, fm), s))

top_new = {}
for ms in month_strs:
    lst = sorted(new_brands[mkey[ms]]['list'], key=lambda x:-x[1])
    top_new[mkey[ms]] = {s: [[b,c] for (b,c,sg) in lst if sg==s][:12] for s in SEGS}

existing_add = {}
for i, ms in enumerate(month_strs):
    if i == 0: existing_add[mkey[ms]] = []; continue
    adds = []
    for b in brand_week_stores:
        if brand_first_month.get(b) == ms: continue
        cnt = sum(1 for p in brand_week_stores[b].get(month_end[ms], ()) if provider_first_month[p]==ms)
        if cnt: adds.append([b, cnt, brand_seg[b]])
    existing_add[mkey[ms]] = sorted(adds, key=lambda x:-x[1])[:15]

partner = []
for b in brand_week_stores:
    rec = {'brand': b, 'vertical': brand_seg[b]}
    for ms in month_strs: rec[mkey[ms]] = bcount(b, ms)
    partner.append(rec)
partner.sort(key=lambda d:-d.get('may', 0))

def peak(b): return max(bcount(b, ms) for ms in month_strs)
allb = [{'brand':b,'vertical':brand_seg[b],'peak':peak(b),
         'may':bcount(b,'2026-05') if '2026-05' in month_end else 0,
         'jun':bcount(b,'2026-06') if '2026-06' in month_end else 0,
         'first':mshort[brand_first_month[b]]} for b in brand_week_stores]
top = {s: sorted([x for x in allb if x['vertical']==s], key=lambda x:-x['peak'])[:10] for s in SEGS}

# ── Churn: stores that went inactive and did NOT return by the final snapshot ──
nxt = {weeks[i]: weeks[i+1] for i in range(len(weeks)-1)}
churn = []
for p in provider_weeks:
    last = max(provider_weeks[p])
    if last == final_week:  # still active in the latest snapshot
        continue
    since = nxt[last]
    churn.append({
        'addr': p, 'brand': provider_rec[p][1], 'seg': provider_seg[p],
        'first': provider_first_week[p], 'last': last, 'since': since, 'month': since[:7],
    })
churn.sort(key=lambda x: (x['since'], x['brand'], x['addr']), reverse=True)

from collections import Counter
wk_cnt = Counter(c['since'] for c in churn)
mo_cnt = Counter(c['month'] for c in churn)
churn_weeks  = [{'week': w, 'label': f"{mshort[w[:7]]} {int(w[8:10])}", 'count': wk_cnt.get(w, 0)} for w in weeks[1:]]
churn_months = [{'month': ms, 'label': f"{mshort[ms]} {ms[:4]}", 'count': mo_cnt.get(ms, 0)} for ms in month_strs]

DATA = {
    'monthly': monthly, 'newStores': new_stores,
    'newBrands': {k:{kk:new_brands[k][kk] for kk in (*SEGS,'total')} for k in new_brands},
    'topNew': top_new, 'existingAdd': existing_add,
    'topEnt': top['ent'], 'topMm': top['mm'], 'topSmb': top['smb'], 'partner': partner,
    'churn': churn, 'churnWeeks': churn_weeks, 'churnMonths': churn_months, 'finalWeek': final_week,
}

MONTHS_META = [
    {'key':'jan','label':'January 2026','short':'Jan','baseline':True},
    {'key':'feb','label':'February 2026','short':'Feb'},
    {'key':'mar','label':'March 2026','short':'Mar'},
    {'key':'apr','label':'April 2026','short':'Apr'},
    {'key':'may','label':'May 2026','short':'May'},
    {'key':'jun','label':'June 2026','short':'Jun','mtd':True},
]

data_js = json.dumps(DATA, ensure_ascii=False)
meta_js = json.dumps(MONTHS_META, ensure_ascii=False)

peak_total = max(monthly[m['key']]['total'] for m in MONTHS_META)
peak_label = {m['key']:m['short'] for m in MONTHS_META}[max(monthly, key=lambda k: monthly[k]['total'])]
organic_new = sum(new_stores[m['key']]['total'] for m in MONTHS_META[1:])
total_brands = len(partner)
start_brands = new_brands['jan']['total']
added_brands = total_brands - start_brands
mE, mM, mS = monthly['may']['ent'], monthly['may']['mm'], monthly['may']['smb']
tt = mE+mM+mS
pE, pM = round(mE/tt*100), round(mM/tt*100)
pS = 100-pE-pM

# ── build CSS from scratch (3-segment aware) ──
CSS = '''*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:#f5f5f4; --surface:#fff; --border:#e5e5e4;
  --text-primary:#1a1a18; --text-secondary:#6b6b66; --text-tertiary:#9b9b96;
  --accent:#1a6b43; --accent-light:#e8f5ee;
  --ent:#2563c0; --ent-light:#dbeafe;
  --mm:#7c3aed; --mm-light:#ede9fe;
  --smb:#d97706; --smb-light:#fef3c7;
  --radius:10px; --radius-sm:6px;
}
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:var(--bg); color:var(--text-primary); min-height:100vh; padding:0 0 60px; }
.page-header { background:var(--surface); border-bottom:1px solid var(--border); padding:28px 40px 24px; }
.page-header h1 { font-size:22px; font-weight:700; letter-spacing:-0.3px; }
.page-header .subtitle { font-size:13px; color:var(--text-secondary); margin-top:4px; }
.header-meta { display:flex; align-items:center; gap:12px; margin-top:14px; flex-wrap:wrap; }
.tag { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; padding:3px 10px; border-radius:99px; border:1px solid var(--border); color:var(--text-secondary); background:var(--bg); }
.container { max-width:1200px; margin:0 auto; padding:0 40px; }
.section { margin-top:36px; }
.section-title { font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; color:var(--text-secondary); margin-bottom:16px; }
.kpi-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
.kpi-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px 22px; }
.kpi-card.accent { background:var(--accent); border-color:var(--accent); color:#fff; }
.kpi-card.accent .kpi-label { color:rgba(255,255,255,0.7); }
.kpi-label { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; color:var(--text-secondary); margin-bottom:8px; }
.kpi-value { font-size:32px; font-weight:700; letter-spacing:-1px; line-height:1; }
.kpi-sub { font-size:12px; color:var(--text-secondary); margin-top:6px; }
.kpi-card.accent .kpi-sub { color:rgba(255,255,255,0.65); }
.charts-row { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.chart-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:22px 24px; }
.chart-card h3 { font-size:14px; font-weight:600; margin-bottom:4px; }
.chart-card .chart-desc { font-size:12px; color:var(--text-secondary); margin-bottom:18px; }
.chart-canvas-wrap { position:relative; height:220px; }
.tabs { display:flex; gap:4px; border-bottom:1px solid var(--border); flex-wrap:wrap; }
.tab-btn { padding:10px 20px; font-size:13px; font-weight:500; color:var(--text-secondary); background:none; border:none; border-bottom:2px solid transparent; cursor:pointer; transition:color .15s; margin-bottom:-1px; }
.tab-btn:hover { color:var(--text-primary); }
.tab-btn.active { color:var(--accent); border-bottom-color:var(--accent); font-weight:600; }
.month-panel { display:none; padding-top:20px; }
.month-panel.active { display:block; }
.month-summary-grid { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; margin-bottom:20px; }
.mini-stat { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius-sm); padding:14px 16px; }
.mini-stat.ent { border-left:3px solid var(--ent); }
.mini-stat.mm { border-left:3px solid var(--mm); }
.mini-stat.smb { border-left:3px solid var(--smb); }
.mini-stat.green { border-left:3px solid var(--accent); }
.mini-label { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:var(--text-secondary); margin-bottom:6px; }
.mini-value { font-size:24px; font-weight:700; letter-spacing:-0.5px; }
.mini-desc { font-size:11px; color:var(--text-secondary); margin-top:3px; }
.brands-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.brands-grid-3 { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
.brand-section { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
.brand-section-header { padding:14px 18px 12px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; }
.brand-section-header h4 { font-size:13px; font-weight:600; }
.segment-pill { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; padding:3px 10px; border-radius:99px; }
.segment-pill.ent { background:var(--ent-light); color:var(--ent); }
.segment-pill.mm { background:var(--mm-light); color:var(--mm); }
.segment-pill.smb { background:var(--smb-light); color:var(--smb); }
.brand-list { padding:8px 0; }
.brand-row { display:flex; align-items:center; padding:7px 18px; gap:10px; transition:background .1s; }
.brand-row:hover { background:var(--bg); }
.brand-rank { font-size:11px; color:var(--text-tertiary); width:18px; text-align:right; flex-shrink:0; }
.brand-name { flex:1; font-size:13px; font-weight:500; }
.brand-bar-wrap { flex:0 0 80px; height:6px; background:var(--bg); border-radius:3px; overflow:hidden; }
.brand-bar { height:100%; border-radius:3px; }
.brand-bar.ent { background:var(--ent); }
.brand-bar.mm { background:var(--mm); }
.brand-bar.smb { background:var(--smb); }
.brand-count { font-size:12px; font-weight:600; color:var(--text-secondary); width:36px; text-align:right; }
.all-brands-wrap { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; margin-top:16px; }
.all-brands-header { padding:14px 18px 12px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:12px; }
.all-brands-header h4 { font-size:13px; font-weight:600; }
table.brands-table { width:100%; border-collapse:collapse; font-size:12px; }
table.brands-table thead th { padding:9px 18px; text-align:left; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:var(--text-secondary); border-bottom:1px solid var(--border); background:var(--bg); }
table.brands-table tbody td { padding:8px 18px; border-bottom:1px solid var(--bg); vertical-align:middle; }
table.brands-table tbody tr:last-child td { border-bottom:none; }
table.brands-table tbody tr:hover td { background:var(--bg); }
.badge { display:inline-block; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.4px; padding:2px 8px; border-radius:99px; }
.badge.ent { background:var(--ent-light); color:var(--ent); }
.badge.mm { background:var(--mm-light); color:var(--mm); }
.badge.smb { background:var(--smb-light); color:var(--smb); }
.badge.new-brand { background:var(--accent-light); color:var(--accent); }
.note { font-size:12px; color:var(--text-secondary); padding:14px 18px; background:#fffbeb; border:1px solid #fde68a; border-radius:var(--radius-sm); margin-top:12px; }
.empty-state { text-align:center; padding:32px; color:var(--text-secondary); font-size:13px; }
.main-nav { background:var(--surface); border-bottom:1px solid var(--border); display:flex; }
.main-nav-btn { padding:13px 28px; font-size:13px; font-weight:500; color:var(--text-secondary); background:none; border:none; border-bottom:2px solid transparent; cursor:pointer; transition:color .15s; margin-bottom:-1px; }
.main-nav-btn:hover { color:var(--text-primary); }
.main-nav-btn.active { color:var(--accent); border-bottom-color:var(--accent); font-weight:600; }
.view { display:none; }
.view.active { display:block; }
.partner-controls { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:16px; }
.partner-search { flex:1; min-width:200px; max-width:320px; padding:8px 14px; font-size:13px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface); color:var(--text-primary); outline:none; }
.partner-search:focus { border-color:var(--accent); }
.filter-group { display:flex; gap:4px; }
.filter-btn { padding:7px 14px; font-size:12px; font-weight:600; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface); color:var(--text-secondary); cursor:pointer; transition:all .12s; }
.filter-btn:hover { border-color:var(--text-secondary); color:var(--text-primary); }
.filter-btn.active-all { background:var(--text-primary); border-color:var(--text-primary); color:#fff; }
.filter-btn.active-ent { background:var(--ent); border-color:var(--ent); color:#fff; }
.filter-btn.active-mm { background:var(--mm); border-color:var(--mm); color:#fff; }
.filter-btn.active-smb { background:var(--smb); border-color:var(--smb); color:#fff; }
.sort-select { padding:7px 12px; font-size:12px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface); color:var(--text-primary); cursor:pointer; outline:none; }
.partner-count { font-size:12px; color:var(--text-secondary); margin-left:auto; }
.partner-table-wrap { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
table.partner-table { width:100%; border-collapse:collapse; font-size:12px; }
table.partner-table thead th { padding:10px 14px; text-align:left; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:var(--text-secondary); border-bottom:1px solid var(--border); background:var(--bg); white-space:nowrap; cursor:pointer; user-select:none; }
table.partner-table thead th:hover { color:var(--text-primary); }
table.partner-table thead th.sorted { color:var(--accent); }
table.partner-table thead th .sort-arrow { opacity:0.4; font-size:9px; margin-left:3px; }
table.partner-table thead th.sorted .sort-arrow { opacity:1; }
table.partner-table tbody td { padding:8px 14px; border-bottom:1px solid var(--bg); vertical-align:middle; white-space:nowrap; }
table.partner-table tbody tr:last-child td { border-bottom:none; }
table.partner-table tbody tr:hover td { background:#fafaf9; }
.partner-name { font-weight:500; font-size:13px; max-width:200px; overflow:hidden; text-overflow:ellipsis; }
.num-cell { text-align:right; font-variant-numeric:tabular-nums; min-width:42px; }
.num-cell.zero { color:var(--text-tertiary); }
.delta { display:inline-block; font-size:10px; font-weight:700; margin-left:3px; }
.delta.up { color:#16a34a; }
.delta.down { color:#dc2626; }
.spark { display:block; }
.status-badge { display:inline-block; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.4px; padding:2px 8px; border-radius:99px; }
.status-badge.growing { background:#dcfce7; color:#16a34a; }
.status-badge.declining { background:#fee2e2; color:#dc2626; }
.status-badge.stable { background:var(--bg); color:var(--text-secondary); border:1px solid var(--border); }
.status-badge.new { background:var(--accent-light); color:var(--accent); }
.status-badge.churned { background:#fef3c7; color:#b45309; }
.partner-table-footer { padding:10px 14px; font-size:11px; color:var(--text-secondary); border-top:1px solid var(--border); background:var(--bg); }
.monthly-totals { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; margin-bottom:12px; }
.month-total-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius-sm); padding:12px 16px; display:flex; flex-direction:column; gap:4px; }
.month-total-card.highlight { border-color:var(--accent); }
.mtc-label { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; color:var(--text-secondary); }
.mtc-row { display:flex; align-items:baseline; gap:8px; }
.mtc-total { font-size:22px; font-weight:700; letter-spacing:-0.5px; }
.mtc-added { font-size:11px; font-weight:700; padding:1px 7px; border-radius:99px; }
.mtc-added.pos { background:#dcfce7; color:#16a34a; }
.mtc-added.neg { background:#fee2e2; color:#dc2626; }
.mtc-added.neu { background:var(--bg); color:var(--text-secondary); }
.mtc-sub { font-size:11px; color:var(--text-secondary); }
.toolbar { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:16px; }
.churn-summary { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px; }
.churn-chart-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:22px 24px; margin-bottom:16px; }
.churn-chart-card h3 { font-size:14px; font-weight:600; margin-bottom:4px; }
.churn-chart-card .chart-desc { font-size:12px; color:var(--text-secondary); margin-bottom:14px; }
.churn-chart-canvas { position:relative; height:240px; }
.addr-cell { white-space:normal; max-width:380px; font-size:12px; line-height:1.4; }
@media (max-width:900px) {
  .churn-summary { grid-template-columns:repeat(2,1fr); }
  .container { padding:0 20px; }
  .page-header { padding:20px; }
  .kpi-grid { grid-template-columns:repeat(2,1fr); }
  .charts-row, .brands-grid, .brands-grid-3 { grid-template-columns:1fr; }
  .month-summary-grid { grid-template-columns:repeat(3,1fr); }
}'''

head = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Active Stores — Monthly Dynamics</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<style>
{CSS}
</style>
</head>'''

def top_table(tid):
    return f'''<table class="brands-table">
        <thead><tr><th>#</th><th>Brand</th><th>Peak Active Stores</th><th>May</th><th>Jun (MTD)</th><th>First Seen</th><th>Segment</th></tr></thead>
        <tbody id="{tid}"></tbody>
      </table>'''

body = f'''<body>
<div class="page-header">
  <div class="container">
    <h1>Active Stores — Monthly Dynamics</h1>
    <p class="subtitle">New store openings, business-segment breakdown, and brand tracking · Ukraine · Jan – Jun 2026</p>
    <div class="header-meta">
      <span class="tag">Bolt Store</span>
      <span class="tag">ENT · MM · SMB</span>
      <span class="tag">Business Segment</span>
      <span class="tag">6 months</span>
      <span class="tag">Weekly · through Jun 8, 2026</span>
    </div>
  </div>
</div>

<nav class="main-nav">
  <button class="main-nav-btn active" onclick="switchView('overview', this)">Monthly Overview</button>
  <button class="main-nav-btn" onclick="switchView('partners', this)">Partner Dynamics</button>
  <button class="main-nav-btn" onclick="switchView('inactive', this)">Inactive Stores</button>
</nav>

<div id="view-overview" class="view active">
<div class="container">
  <div class="section">
    <p class="section-title">Overview</p>
    <div class="kpi-grid">
      <div class="kpi-card accent">
        <div class="kpi-label">Total Active Stores ({peak_label})</div>
        <div class="kpi-value">{peak_total:,}</div>
        <div class="kpi-sub">Peak month so far</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">New Stores Since Feb</div>
        <div class="kpi-value">{organic_new:,}</div>
        <div class="kpi-sub">Excl. Jan baseline</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Unique Brands Onboarded</div>
        <div class="kpi-value">{total_brands}</div>
        <div class="kpi-sub">{start_brands} at start + {added_brands} new later</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Segment Split (May)</div>
        <div class="kpi-value">{pE}/{pM}/{pS}</div>
        <div class="kpi-sub">ENT · MM · SMB %</div>
      </div>
    </div>
  </div>

  <div class="section">
    <p class="section-title">Monthly Trends</p>
    <div class="charts-row">
      <div class="chart-card">
        <h3>New Stores per Month</h3>
        <p class="chart-desc">First-time active stores, split by business segment</p>
        <div class="chart-canvas-wrap"><canvas id="chartNewStores"></canvas></div>
      </div>
      <div class="chart-card">
        <h3>Total Active Stores</h3>
        <p class="chart-desc">All active stores in portfolio each month</p>
        <div class="chart-canvas-wrap"><canvas id="chartTotal"></canvas></div>
      </div>
    </div>
  </div>

  <div class="section">
    <p class="section-title">Month-by-Month Breakdown</p>
    <div class="tabs" id="monthTabs"></div>
    <div id="monthPanels"></div>
  </div>

  <div class="section">
    <p class="section-title">Segment Comparison — Full Period</p>
    <div class="charts-row">
      <div class="chart-card">
        <h3>Segment Share of Active Stores</h3>
        <p class="chart-desc">By month, % of active stores</p>
        <div class="chart-canvas-wrap"><canvas id="chartShare"></canvas></div>
      </div>
      <div class="chart-card">
        <h3>New Brands Onboarded</h3>
        <p class="chart-desc">Unique brands making their first appearance</p>
        <div class="chart-canvas-wrap"><canvas id="chartBrands"></canvas></div>
      </div>
    </div>
  </div>

  <div class="section">
    <p class="section-title">Top ENT Brands — All Period</p>
    <div class="all-brands-wrap">{top_table('topEntBody')}</div>
  </div>
  <div class="section">
    <p class="section-title">Top MM Brands — All Period</p>
    <div class="all-brands-wrap">{top_table('topMmBody')}</div>
  </div>
  <div class="section">
    <p class="section-title">Top SMB Brands — All Period</p>
    <div class="all-brands-wrap">{top_table('topSmbBody')}</div>
  </div>
</div>
</div>

<div id="view-partners" class="view">
<div class="container">
  <div class="section">
    <p class="section-title">Partner Dynamics — Store Count per Month</p>
    <div class="partner-controls">
      <input class="partner-search" type="text" id="partnerSearch" placeholder="Search brand..." oninput="renderPartnerTable()" />
      <div class="filter-group">
        <button class="filter-btn active-all" id="segAll" onclick="setSegFilter('all',this)">All</button>
        <button class="filter-btn" id="segEnt" onclick="setSegFilter('ent',this)">ENT</button>
        <button class="filter-btn" id="segMm" onclick="setSegFilter('mm',this)">MM</button>
        <button class="filter-btn" id="segSmb" onclick="setSegFilter('smb',this)">SMB</button>
      </div>
      <div class="filter-group">
        <button class="filter-btn" id="stAll" onclick="setStatusFilter('all',this)">All Status</button>
        <button class="filter-btn" id="stGrowing" onclick="setStatusFilter('growing',this)">Growing</button>
        <button class="filter-btn" id="stDeclining" onclick="setStatusFilter('declining',this)">Declining</button>
        <button class="filter-btn" id="stNew" onclick="setStatusFilter('new',this)">New</button>
        <button class="filter-btn" id="stChurned" onclick="setStatusFilter('churned',this)">Churned</button>
      </div>
      <select class="sort-select" id="partnerSort" onchange="renderPartnerTable()">
        <option value="may">Sort: May (latest full)</option>
        <option value="jun">Sort: Jun MTD</option>
        <option value="brand">Sort: Brand A–Z</option>
        <option value="jan">Sort: Jan</option>
        <option value="feb">Sort: Feb</option>
        <option value="mar">Sort: Mar</option>
        <option value="apr">Sort: Apr</option>
        <option value="total">Sort: Total</option>
      </select>
      <span class="partner-count" id="partnerCount"></span>
    </div>
    <div class="monthly-totals" id="monthlyTotals"></div>
    <div class="partner-table-wrap">
      <table class="partner-table" id="partnerTable">
        <thead><tr id="partnerHead"></tr></thead>
        <tbody id="partnerTbody"></tbody>
      </table>
      <div class="partner-table-footer" id="partnerFooter"></div>
    </div>
  </div>
</div>
</div>

<div id="view-inactive" class="view">
<div class="container">
  <div class="section">
    <p class="section-title">Inactive Stores — Went Inactive &amp; Did Not Return (by Jun 8)</p>
    <div class="toolbar">
      <input class="partner-search" type="text" id="churnSearch" placeholder="Search address or brand..." oninput="renderChurn()" />
      <div class="filter-group">
        <button class="filter-btn active-all" id="chWeek" onclick="setChMode('week',this)">By Week</button>
        <button class="filter-btn" id="chMonth" onclick="setChMode('month',this)">By Month</button>
      </div>
      <div class="filter-group">
        <button class="filter-btn active-all" id="chSegAll" onclick="setChSeg('all',this)">All</button>
        <button class="filter-btn" id="chSegEnt" onclick="setChSeg('ent',this)">ENT</button>
        <button class="filter-btn" id="chSegMm" onclick="setChSeg('mm',this)">MM</button>
        <button class="filter-btn" id="chSegSmb" onclick="setChSeg('smb',this)">SMB</button>
      </div>
      <select class="sort-select" id="churnPeriod" onchange="renderChurn()"></select>
      <span class="partner-count" id="churnCount"></span>
    </div>
    <div class="churn-summary" id="churnSummary"></div>
    <div class="churn-chart-card">
      <h3 id="churnChartTitle">Stores Going Inactive per Week</h3>
      <p class="chart-desc">Stores that disappeared from the weekly snapshot and never returned. Click a bar to filter the table.</p>
      <div class="churn-chart-canvas"><canvas id="churnChart"></canvas></div>
    </div>
    <div class="partner-table-wrap">
      <table class="partner-table">
        <thead><tr>
          <th>Address</th><th>Brand</th><th>Seg</th>
          <th>First Active</th><th>Last Active</th><th id="chPeriodHead">Inactive Since (Week)</th>
        </tr></thead>
        <tbody id="churnTbody"></tbody>
      </table>
      <div class="partner-table-footer" id="churnFooter"></div>
    </div>
  </div>
</div>
</div>

<script>
const DATA = {data_js};
const MONTHS = {meta_js};
const MK = MONTHS.map(m=>m.key);
const SEGS = ['ent','mm','smb'];
const SEG_LABEL = {{ent:'ENT',mm:'MM',smb:'SMB'}};
const SEG_FULL = {{ent:'Enterprise',mm:'Mid-Market',smb:'SMB'}};
const LATEST_FULL = 'may';
const COL = {{ent:'#2563c0',mm:'#7c3aed',smb:'#d97706'}};
const accentColor='#1a6b43';

function brandListHTML(brands, segment) {{
  if(!brands.length) return '<div class="empty-state">No new brands this month</div>';
  const max = brands[0][1];
  return brands.slice(0,12).map(([name,count],i)=>`
    <div class="brand-row">
      <span class="brand-rank">${{i+1}}</span>
      <span class="brand-name">${{name}}</span>
      <div class="brand-bar-wrap"><div class="brand-bar ${{segment}}" style="width:${{Math.round(count/max*100)}}%"></div></div>
      <span class="brand-count">${{count}}</span>
    </div>`).join('');
}}

function buildMonths() {{
  document.getElementById('monthTabs').innerHTML = MONTHS.map((m,i)=>`<button class="tab-btn ${{i===0?'active':''}}" onclick="switchTab('${{m.key}}',this)">${{m.label}}${{m.mtd?' <span style=\\"font-size:10px;opacity:0.6\\">(MTD)</span>':''}}</button>`).join('');
  document.getElementById('monthPanels').innerHTML = MONTHS.map((m,i)=>{{
    const mn=DATA.monthly[m.key], ns=DATA.newStores[m.key], nb=DATA.newBrands[m.key];
    const diff = i>0 ? mn.total-DATA.monthly[MONTHS[i-1].key].total : 0;
    const diffTxt = m.baseline?'baseline':(diff>=0?`+${{diff}} vs ${{MONTHS[i-1].short}}`:`${{diff}} vs ${{MONTHS[i-1].short}}`);
    let note='';
    if(m.baseline) note=`<div class="note">January is the <strong>baseline month</strong> — the earliest data in this dataset. Its ${{ns.total.toLocaleString()}} stores represent the starting portfolio, not organic growth.</div>`;
    if(m.mtd) note=`<div class="note">June 2026 data is <strong>month-to-date (latest weekly snapshot Jun 8)</strong>. Counts will grow through the month; the dip vs May is expected this early.</div>`;
    const ea=DATA.existingAdd[m.key]||[];
    const eaRows=ea.map(([b,c,s])=>`<tr><td>${{b}}</td><td><strong>${{c}}</strong></td><td><span class="badge ${{s}}">${{SEG_LABEL[s]}}</span></td></tr>`).join('');
    const eaBlock=ea.length?`<div class="all-brands-wrap"><div class="all-brands-header"><h4>Existing Brands Adding New Stores in ${{m.short}}</h4></div><table class="brands-table"><thead><tr><th>Brand</th><th>New Stores Added</th><th>Segment</th></tr></thead><tbody>${{eaRows}}</tbody></table></div>`:'';
    const segStats = SEGS.map(s=>`<div class="mini-stat ${{s}}"><div class="mini-label">${{SEG_LABEL[s]}} New</div><div class="mini-value">${{ns[s]}}</div><div class="mini-desc">new stores</div></div>`).join('');
    const newBrandSections = SEGS.map(s=>`<div class="brand-section"><div class="brand-section-header"><h4>Top ${{SEG_LABEL[s]}} New Brands</h4><span class="segment-pill ${{s}}">${{SEG_FULL[s]}}</span></div><div class="brand-list">${{brandListHTML(DATA.topNew[m.key][s],s)}}</div></div>`).join('');
    return `<div id="panel-${{m.key}}" class="month-panel ${{i===0?'active':''}}">
      ${{note}}
      <div class="month-summary-grid" ${{note?'style="margin-top:16px"':''}}>
        <div class="mini-stat green"><div class="mini-label">Total Active${{m.mtd?' (MTD)':''}}</div><div class="mini-value">${{mn.total.toLocaleString()}}</div><div class="mini-desc">${{diffTxt}}</div></div>
        <div class="mini-stat green"><div class="mini-label">New${{m.mtd?' (MTD)':''}}</div><div class="mini-value">${{ns.total.toLocaleString()}}</div><div class="mini-desc">first-time active</div></div>
        ${{segStats}}
        <div class="mini-stat"><div class="mini-label">New Brands</div><div class="mini-value">${{nb.total}}</div><div class="mini-desc">unique brands</div></div>
      </div>
      <div class="brands-grid-3">${{newBrandSections}}</div>
      ${{eaBlock}}
    </div>`;
  }}).join('');
}}

function switchTab(key, btn) {{
  document.querySelectorAll('.month-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('panel-'+key).classList.add('active'); btn.classList.add('active');
}}

function fillTop(id, list) {{
  document.getElementById(id).innerHTML = list.map((x,i)=>`<tr>
    <td>${{i+1}}</td><td><strong>${{x.brand}}</strong></td><td>${{x.peak}}</td>
    <td>${{x.may}}</td><td>${{x.jun}}</td>
    <td>${{x.first}} 2026 ${{x.first!=='Jan'?'<span class="badge new-brand">NEW</span>':''}}</td>
    <td><span class="badge ${{x.vertical}}">${{SEG_LABEL[x.vertical]}}</span></td></tr>`).join('');
}}

function buildCharts() {{
  const labels = MONTHS.map(m=>m.short+' 2026');
  const segDS = src => SEGS.map(s=>({{label:SEG_LABEL[s],data:MK.map(k=>DATA[src][k][s]),backgroundColor:COL[s]}}));
  const stackOpt = {{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{font:{{size:11}},padding:12}}}}}},scales:{{x:{{stacked:true,grid:{{display:false}},ticks:{{font:{{size:11}}}}}},y:{{stacked:true,grid:{{color:'#f0f0ef'}},ticks:{{font:{{size:11}}}}}}}}}};
  new Chart(document.getElementById('chartNewStores'),{{type:'bar',data:{{labels,datasets:segDS('newStores')}},options:stackOpt}});
  new Chart(document.getElementById('chartTotal'),{{type:'line',data:{{labels,datasets:[{{label:'Active Stores',data:MK.map(k=>DATA.monthly[k].total),borderColor:accentColor,backgroundColor:'rgba(26,107,67,0.08)',fill:true,tension:0.3,pointRadius:5,pointBackgroundColor:accentColor}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{grid:{{display:false}},ticks:{{font:{{size:11}}}}}},y:{{min:900,grid:{{color:'#f0f0ef'}},ticks:{{font:{{size:11}}}}}}}}}}}});
  const shareDS = SEGS.map(s=>({{label:SEG_LABEL[s]+' %',data:MK.map(k=>Math.round(DATA.monthly[k][s]/DATA.monthly[k].total*100)),backgroundColor:COL[s]}}));
  new Chart(document.getElementById('chartShare'),{{type:'bar',data:{{labels,datasets:shareDS}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{font:{{size:11}},padding:12}}}}}},scales:{{x:{{stacked:true,grid:{{display:false}},ticks:{{font:{{size:11}}}}}},y:{{stacked:true,max:100,grid:{{color:'#f0f0ef'}},ticks:{{font:{{size:11}},callback:v=>v+'%'}}}}}}}}}});
  new Chart(document.getElementById('chartBrands'),{{type:'bar',data:{{labels,datasets:segDS('newBrands')}},options:stackOpt}});
}}

function switchView(name, btn) {{
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.querySelectorAll('.main-nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('view-'+name).classList.add('active'); btn.classList.add('active');
}}

const partnerData = DATA.partner;
function vals(d) {{ return MK.map(k=>d[k]); }}
function getStatus(d) {{
  const v=vals(d), firstNZ=v.findIndex(x=>x>0);
  if(firstNZ===-1) return 'churned';
  const lastTwoZero = v[v.length-1]===0 && v[v.length-2]===0;
  if(firstNZ>0) return lastTwoZero?'churned':'new';
  if(lastTwoZero) return 'churned';
  const first=v[0]; let latest=0; for(let i=v.length-1;i>=0;i--){{if(v[i]>0){{latest=v[i];break;}}}}
  if(latest>first*1.1) return 'growing';
  if(latest<first*0.85) return 'declining';
  return 'stable';
}}
function sparkline(d) {{
  const v=vals(d), max=Math.max(...v,1), W=84,H=28,pad=4,n=v.length;
  const xs=v.map((_,i)=>pad+i*(W-pad*2)/(n-1)), ys=v.map(x=>H-pad-(x/max)*(H-pad*2));
  const dots=xs.map((x,i)=>`<circle cx="${{x}}" cy="${{ys[i]}}" r="2" fill="${{v[i]>0?'#1a6b43':'#e5e5e4'}}"/>`).join('');
  return `<svg class="spark" width="${{W}}" height="${{H}}" viewBox="0 0 ${{W}} ${{H}}"><polyline points="${{xs.map((x,i)=>x+','+ys[i]).join(' ')}}" fill="none" stroke="#1a6b43" stroke-width="1.5" opacity="0.6"/>${{dots}}</svg>`;
}}
function delta(curr, prev) {{
  if(prev===0&&curr===0) return '';
  if(prev===0) return `<span class="delta up">+${{curr}}</span>`;
  const d=curr-prev; if(d===0) return '';
  return d>0?`<span class="delta up">+${{d}}</span>`:`<span class="delta down">${{d}}</span>`;
}}

let segFilter='all', statusFilter='all', sortCol='may', sortAsc=false;
function setSegFilter(seg, btn) {{
  segFilter=seg;
  document.querySelectorAll('#segAll,#segEnt,#segMm,#segSmb').forEach(b=>b.className='filter-btn');
  btn.classList.add(seg==='all'?'active-all':'active-'+seg);
  renderPartnerTable();
}}
function setStatusFilter(st, btn) {{
  statusFilter=st;
  document.querySelectorAll('#stAll,#stGrowing,#stDeclining,#stNew,#stChurned').forEach(b=>b.classList.remove('active-all'));
  btn.classList.add('active-all'); renderPartnerTable();
}}
function cycleSortCol(col) {{
  if(sortCol===col) sortAsc=!sortAsc; else {{ sortCol=col; sortAsc=col==='brand'; }}
  document.getElementById('partnerSort').value=col; updateHead(); renderPartnerTable();
}}
function buildHead() {{
  let html=`<th onclick="cycleSortCol('brand')" id="th-brand">Brand <span class="sort-arrow">↕</span></th><th>Seg</th>`;
  MONTHS.forEach(m=>{{ html+=`<th onclick="cycleSortCol('${{m.key}}')" id="th-${{m.key}}" class="num-cell">${{m.short}}${{m.mtd?' MTD':''}} <span class="sort-arrow">↕</span></th>`; }});
  html+=`<th style="min-width:90px">Trend</th><th>Status</th>`;
  document.getElementById('partnerHead').innerHTML=html; updateHead();
}}
function updateHead() {{
  ['brand',...MK,'total'].forEach(c=>{{
    const th=document.getElementById('th-'+c); if(!th) return;
    th.classList.toggle('sorted', c===sortCol);
    const a=th.querySelector('.sort-arrow'); if(a) a.textContent=c===sortCol?(sortAsc?'↑':'↓'):'↕';
  }});
}}
function renderPartnerTable() {{
  const search=document.getElementById('partnerSearch').value.toLowerCase();
  const sortKey=document.getElementById('partnerSort').value;
  if(sortKey!==sortCol){{sortCol=sortKey;sortAsc=sortKey==='brand';updateHead();}}
  let rows=partnerData.filter(d=>{{
    if(!d.brand) return false;
    if(segFilter!=='all'&&d.vertical!==segFilter) return false;
    if(search&&!d.brand.toLowerCase().includes(search)) return false;
    if(statusFilter!=='all'&&getStatus(d)!==statusFilter) return false;
    return true;
  }});
  const tot=d=>MK.reduce((s,k)=>s+d[k],0);
  rows.sort((a,b)=>{{
    let va=sortCol==='brand'?a.brand:(sortCol==='total'?tot(a):a[sortCol]);
    let vb=sortCol==='brand'?b.brand:(sortCol==='total'?tot(b):b[sortCol]);
    if(va<vb) return sortAsc?-1:1; if(va>vb) return sortAsc?1:-1; return 0;
  }});
  document.getElementById('partnerTbody').innerHTML=rows.map(d=>{{
    const st=getStatus(d);
    const seg=`<span class="badge ${{d.vertical}}">${{SEG_LABEL[d.vertical]}}</span>`;
    let cells='';
    MK.forEach((k,i)=>{{
      const prev=i>0?d[MK[i-1]]:0;
      if(i===0) cells+=`<td class="num-cell ${{d[k]===0?'zero':''}}">${{d[k]||'—'}}</td>`;
      else cells+=(d[k]===0&&prev===0)?`<td class="num-cell zero">—</td>`:`<td class="num-cell">${{d[k]}}${{delta(d[k],prev)}}</td>`;
    }});
    return `<tr><td class="partner-name" title="${{d.brand}}">${{d.brand}}</td><td>${{seg}}</td>${{cells}}<td>${{sparkline(d)}}</td><td><span class="status-badge ${{st}}">${{st}}</span></td></tr>`;
  }}).join('');
  document.getElementById('partnerCount').textContent=`${{rows.length}} partner${{rows.length!==1?'s':''}}`;
  document.getElementById('partnerFooter').textContent=`Showing ${{rows.length}} of ${{partnerData.length}} brands · monthly = last weekly snapshot of each month · June MTD (Jun 8)`;
  const totals=MK.map(k=>rows.reduce((s,d)=>s+d[k],0));
  const newAdds=MK.map((k,i)=> i===0?0:rows.filter(d=>d[MK[i-1]]===0&&d[k]>0).reduce((s,d)=>s+d[k],0));
  function badge(diff,base){{ if(base) return `<span class="mtc-added neu">baseline</span>`; if(diff===0) return `<span class="mtc-added neu">±0</span>`; return diff>0?`<span class="mtc-added pos">+${{diff}}</span>`:`<span class="mtc-added neg">${{diff}}</span>`; }}
  document.getElementById('monthlyTotals').innerHTML=MONTHS.map((m,i)=>{{
    const diff=i>0?totals[i]-totals[i-1]:0;
    const sub=m.baseline?'total stores':(newAdds[i]>0?`${{newAdds[i]}} new stores added`:'');
    return `<div class="month-total-card ${{m.key===LATEST_FULL?'highlight':''}}"><span class="mtc-label">${{m.short}} 2026 ${{m.mtd?'<span style=\\"font-weight:400;opacity:0.7\\">MTD</span>':''}}</span><div class="mtc-row"><span class="mtc-total">${{totals[i].toLocaleString()}}</span>${{badge(diff,m.baseline)}}</div><span class="mtc-sub">${{sub}}</span></div>`;
  }}).join('');
}}

/* ════ INACTIVE STORES ════ */
const churnData = DATA.churn;
const MONJS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const weekLabel = {{}}; DATA.churnWeeks.forEach(o=>weekLabel[o.week]=o.label);
const monthLabel = {{}}; DATA.churnMonths.forEach(o=>monthLabel[o.month]=o.label);
function fmtDate(d) {{ return d ? MONJS[parseInt(d.slice(5,7))-1]+' '+parseInt(d.slice(8,10)) : '—'; }}
let chMode='week', chSeg='all', churnChart=null;

function buildPeriodSelect() {{
  const sel=document.getElementById('churnPeriod');
  const list = chMode==='week' ? DATA.churnWeeks : DATA.churnMonths;
  const opts = ['<option value="all">All periods</option>'];
  list.filter(p=>p.count>0).slice().reverse().forEach(p=>{{
    const v = chMode==='week'?p.week:p.month;
    opts.push(`<option value="${{v}}">${{p.label}} (${{p.count}})</option>`);
  }});
  sel.innerHTML = opts.join('');
}}

function setChMode(mode, btn) {{
  chMode=mode;
  document.querySelectorAll('#chWeek,#chMonth').forEach(b=>b.classList.remove('active-all'));
  btn.classList.add('active-all');
  document.getElementById('churnChartTitle').textContent = mode==='week'?'Stores Going Inactive per Week':'Stores Going Inactive per Month';
  document.getElementById('chPeriodHead').textContent = mode==='week'?'Inactive Since (Week)':'Inactive In (Month)';
  buildPeriodSelect(); buildChurnChart(); renderChurn();
}}
function setChSeg(seg, btn) {{
  chSeg=seg;
  document.querySelectorAll('#chSegAll,#chSegEnt,#chSegMm,#chSegSmb').forEach(b=>b.className='filter-btn');
  btn.classList.add(seg==='all'?'active-all':'active-'+seg);
  buildChurnChart(); renderChurn();
}}

function buildChurnChart() {{
  const list = chMode==='week' ? DATA.churnWeeks : DATA.churnMonths;
  const labels = list.map(p=>p.label);
  const counts = list.map(p=>churnData.filter(c=>(chMode==='week'?c.since===p.week:c.month===p.month) && (chSeg==='all'||c.seg===chSeg)).length);
  if(churnChart) churnChart.destroy();
  churnChart = new Chart(document.getElementById('churnChart'),{{
    type:'bar',
    data:{{labels,datasets:[{{label:'Stores went inactive',data:counts,backgroundColor:'#dc2626'}}]}},
    options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},
      onClick:(e,els)=>{{ if(els.length){{ const i=els[0].index; const v=chMode==='week'?list[i].week:list[i].month; document.getElementById('churnPeriod').value=v; renderChurn(); }} }},
      scales:{{x:{{grid:{{display:false}},ticks:{{font:{{size:10}},maxRotation:60,minRotation:0}}}},y:{{grid:{{color:'#f0f0ef'}},ticks:{{font:{{size:11}},precision:0}}}}}}}}
  }});
}}

function renderChurn() {{
  const search=document.getElementById('churnSearch').value.toLowerCase();
  const period=document.getElementById('churnPeriod').value;
  const matchPeriod = c => period==='all' || (chMode==='week'?c.since===period:c.month===period);
  const matchSearch = c => !search || c.addr.toLowerCase().includes(search) || c.brand.toLowerCase().includes(search);
  const base = churnData.filter(c=>matchPeriod(c) && matchSearch(c));
  const rows = base.filter(c=>chSeg==='all'||c.seg===chSeg);
  rows.sort((a,b)=> a.brand<b.brand?-1 : a.brand>b.brand?1 : (a.since<b.since?1 : a.since>b.since?-1:0));
  document.getElementById('churnTbody').innerHTML = rows.map(c=>`<tr>
    <td class="addr-cell" title="${{c.addr}}">${{c.addr}}</td>
    <td>${{c.brand}}</td>
    <td><span class="badge ${{c.seg}}">${{SEG_LABEL[c.seg]}}</span></td>
    <td class="num-cell">${{fmtDate(c.first)}}</td>
    <td class="num-cell">${{fmtDate(c.last)}}</td>
    <td>${{chMode==='week'?(weekLabel[c.since]||c.since):(monthLabel[c.month]||c.month)}}</td>
  </tr>`).join('') || `<tr><td colspan="6" class="empty-state">No inactive stores match the filters</td></tr>`;
  document.getElementById('churnCount').textContent=`${{rows.length}} store${{rows.length!==1?'s':''}}`;
  document.getElementById('churnFooter').textContent=`Showing ${{rows.length}} of ${{churnData.length}} stores that went inactive · weekly snapshots Jan 5 – Jun 8, 2026`;
  const cnt = s => base.filter(c=>c.seg===s).length;
  document.getElementById('churnSummary').innerHTML = `
    <div class="month-total-card"><span class="mtc-label">Total Inactive</span><div class="mtc-row"><span class="mtc-total">${{base.length}}</span></div><span class="mtc-sub">${{period==='all'?'all periods':'selected period'}}</span></div>
    <div class="month-total-card" style="border-left:3px solid var(--ent)"><span class="mtc-label">ENT</span><div class="mtc-row"><span class="mtc-total">${{cnt('ent')}}</span></div><span class="mtc-sub">enterprise</span></div>
    <div class="month-total-card" style="border-left:3px solid var(--mm)"><span class="mtc-label">MM</span><div class="mtc-row"><span class="mtc-total">${{cnt('mm')}}</span></div><span class="mtc-sub">mid-market</span></div>
    <div class="month-total-card" style="border-left:3px solid var(--smb)"><span class="mtc-label">SMB</span><div class="mtc-row"><span class="mtc-total">${{cnt('smb')}}</span></div><span class="mtc-sub">small business</span></div>`;
}}

buildMonths();
buildCharts();
fillTop('topEntBody', DATA.topEnt);
fillTop('topMmBody', DATA.topMm);
fillTop('topSmbBody', DATA.topSmb);
buildHead();
renderPartnerTable();
buildPeriodSelect();
buildChurnChart();
renderChurn();
</script>
</body>
</html>'''

final = head + '\n' + body
open(OUT,'w',encoding='utf-8').write(final)
print("WROTE", OUT, len(final), "chars")
print("Peak", peak_label, peak_total, "| organic", organic_new, "| brands", total_brands, "| split", pE, pM, pS)
for m in MONTHS_META:
    k=m['key']
    print(m['short'], monthly[k], '| new', new_stores[k], '| nb', {s:new_brands[k][s] for s in (*SEGS,'total')})
