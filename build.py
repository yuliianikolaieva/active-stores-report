import csv, json, re
from collections import defaultdict

BASE = "/Users/yuliia.nikolaieva/Downloads/Active store"
SRC = "/Users/yuliia.nikolaieva/Downloads/Active stores tracking 2026-06-09T1335.csv"
OUT = BASE + "/active-stores-dynamics.html"

rows = list(csv.DictReader(open(SRC)))
months = ['2026-01','2026-02','2026-03','2026-04','2026-05','2026-06']
mkey = {'2026-01':'jan','2026-02':'feb','2026-03':'mar','2026-04':'apr','2026-05':'may','2026-06':'jun'}
mshort = {'2026-01':'Jan','2026-02':'Feb','2026-03':'Mar','2026-04':'Apr','2026-05':'May','2026-06':'Jun'}

def vmap(v):
    if v == 'store_3p_ent': return 'ent'
    if v == 'store_3p_mm_smb': return 'smb'
    return 'unc'
def is_archived(p): return '[Archived]' in p

brand_month_stores = defaultdict(lambda: defaultdict(set))
brand_vertical_votes = defaultdict(lambda: defaultdict(int))
provider_months = defaultdict(set)
provider_vertical = {}

for r in rows:
    seg = vmap(r['Delivery Vertical'])
    if seg == 'unc': continue
    p = r['Provider Name']
    if is_archived(p): continue
    brand = r['Brand Name'].strip()
    if not brand: continue
    m = r['Report Time (dynamic)']
    brand_month_stores[brand][m].add(p)
    brand_vertical_votes[brand][seg] += 1
    provider_months[p].add(m)
    provider_vertical[p] = seg

brand_vertical = {b: max(v, key=v.get) for b, v in brand_vertical_votes.items()}

monthly = {}
for m in months:
    ent = smb = 0
    for b, md in brand_month_stores.items():
        n = len(md.get(m, ()))
        if brand_vertical[b] == 'ent': ent += n
        else: smb += n
    monthly[mkey[m]] = {'ent': ent, 'smb': smb, 'total': ent+smb}

first_month = {p: min(ms) for p, ms in provider_months.items()}
new_stores = {mkey[m]: {'ent':0,'smb':0,'total':0} for m in months}
for p, fm in first_month.items():
    new_stores[mkey[fm]][provider_vertical[p]] += 1
    new_stores[mkey[fm]]['total'] += 1

brand_first_month = {}
for b, md in brand_month_stores.items():
    present = [m for m in months if md.get(m)]
    if present: brand_first_month[b] = min(present)

new_brands = {mkey[m]: {'ent':0,'smb':0,'total':0,'list':[]} for m in months}
for b, fm in brand_first_month.items():
    seg = brand_vertical[b]
    k = mkey[fm]
    new_brands[k][seg]+=1; new_brands[k]['total']+=1
    new_brands[k]['list'].append((b, len(brand_month_stores[b][fm]), seg))

top_new = {}
for m in months:
    lst = sorted(new_brands[mkey[m]]['list'], key=lambda x:-x[1])
    top_new[mkey[m]] = {
        'ent': [[b,c] for (b,c,s) in lst if s=='ent'][:12],
        'smb': [[b,c] for (b,c,s) in lst if s=='smb'][:12],
    }

existing_add = {}
for mi, m in enumerate(months):
    if mi == 0:
        existing_add[mkey[m]] = []; continue
    adds = []
    for b, md in brand_month_stores.items():
        if brand_first_month.get(b) == m: continue
        new_here = [p for p in md.get(m, ()) if first_month[p]==m]
        if new_here: adds.append([b, len(new_here), brand_vertical[b]])
    existing_add[mkey[m]] = sorted(adds, key=lambda x:-x[1])[:15]

partner = []
for b in brand_month_stores:
    rec = {'brand': b, 'vertical': brand_vertical[b]}
    for m in months: rec[mkey[m]] = len(brand_month_stores[b].get(m, ()))
    partner.append(rec)
partner.sort(key=lambda d:-d['may'])

def peak(b): return max(len(brand_month_stores[b].get(m,())) for m in months)
allb = [{'brand':b,'vertical':brand_vertical[b],'peak':peak(b),
         'may':len(brand_month_stores[b].get('2026-05',())),
         'jun':len(brand_month_stores[b].get('2026-06',())),
         'first':mshort[brand_first_month[b]]} for b in brand_month_stores]
top_ent = sorted([x for x in allb if x['vertical']=='ent'], key=lambda x:-x['peak'])[:10]
top_smb = sorted([x for x in allb if x['vertical']=='smb'], key=lambda x:-x['peak'])[:10]

DATA = {
    'monthly': monthly, 'newStores': new_stores,
    'newBrands': {k:{kk:new_brands[k][kk] for kk in ('ent','smb','total')} for k in new_brands},
    'topNew': top_new, 'existingAdd': existing_add,
    'topEnt': top_ent, 'topSmb': top_smb, 'partner': partner,
}

# ---- extract head/css from existing file ----
html = open(OUT, encoding='utf-8').read()
head = html.split('</head>')[0]
# replace title subtitle/meta later via full body rewrite
head_css = head[:head.index('</style>')+len('</style>')]
head_css = head_css.replace(
    '<title>Active Stores — Monthly Dynamics</title>',
    '<title>Active Stores — Monthly Dynamics</title>')

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
peak_key = max(monthly, key=lambda k: monthly[k]['total'])
peak_label = {m['key']:m['short'] for m in MONTHS_META}[peak_key]
organic_new = sum(new_stores[m['key']]['total'] for m in MONTHS_META[1:])
total_brands = len(partner)
start_brands = new_brands['jan']['total']
added_brands = total_brands - start_brands
may_ent = monthly['may']['ent']; may_smb = monthly['may']['smb']
split_e = round(may_ent/(may_ent+may_smb)*100); split_s = 100-split_e

body = f'''
<div class="page-header">
  <div class="container">
    <h1>Active Stores — Monthly Dynamics</h1>
    <p class="subtitle">New store openings, partner segmentation, and brand tracking · Ukraine · Jan – Jun 2026</p>
    <div class="header-meta">
      <span class="tag">Bolt Store</span>
      <span class="tag">ENT &amp; SMB</span>
      <span class="tag">6 months</span>
      <span class="tag">As of Jun 9, 2026</span>
    </div>
  </div>
</div>

<nav class="main-nav">
  <button class="main-nav-btn active" onclick="switchView('overview', this)">Monthly Overview</button>
  <button class="main-nav-btn" onclick="switchView('partners', this)">Partner Dynamics</button>
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
        <div class="kpi-label">ENT vs SMB Split</div>
        <div class="kpi-value">{split_e}/{split_s}</div>
        <div class="kpi-sub">{may_ent} ENT · {may_smb} SMB (May)</div>
      </div>
    </div>
  </div>

  <div class="section">
    <p class="section-title">Monthly Trends</p>
    <div class="charts-row">
      <div class="chart-card">
        <h3>New Stores per Month</h3>
        <p class="chart-desc">First-time active stores, split by segment</p>
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
        <h3>ENT vs SMB Share of Active Stores</h3>
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
    <div class="all-brands-wrap">
      <table class="brands-table">
        <thead><tr><th>#</th><th>Brand</th><th>Peak Active Stores</th><th>May</th><th>Jun (MTD)</th><th>First Seen</th><th>Segment</th></tr></thead>
        <tbody id="topEntBody"></tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <p class="section-title">Top SMB Brands — All Period</p>
    <div class="all-brands-wrap">
      <table class="brands-table">
        <thead><tr><th>#</th><th>Brand</th><th>Peak Active Stores</th><th>May</th><th>Jun (MTD)</th><th>First Seen</th><th>Segment</th></tr></thead>
        <tbody id="topSmbBody"></tbody>
      </table>
    </div>
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
        <button class="filter-btn active-all" id="segAll"  onclick="setSegFilter('all',  this)">All</button>
        <button class="filter-btn"            id="segEnt"  onclick="setSegFilter('ent',  this)">ENT</button>
        <button class="filter-btn"            id="segSmb"  onclick="setSegFilter('smb',  this)">SMB</button>
      </div>
      <div class="filter-group">
        <button class="filter-btn" id="stAll"       onclick="setStatusFilter('all',      this)">All Status</button>
        <button class="filter-btn" id="stGrowing"   onclick="setStatusFilter('growing',  this)">Growing</button>
        <button class="filter-btn" id="stDeclining" onclick="setStatusFilter('declining',this)">Declining</button>
        <button class="filter-btn" id="stNew"       onclick="setStatusFilter('new',      this)">New</button>
        <button class="filter-btn" id="stChurned"   onclick="setStatusFilter('churned',  this)">Churned</button>
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

<script>
const DATA = {data_js};
const MONTHS = {meta_js};
const MK = MONTHS.map(m=>m.key);
const LATEST_FULL = 'may';
const entColor='#2563c0', smbColor='#d97706', accentColor='#1a6b43';

/* ── Month tabs + panels ── */
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
  const tabs = document.getElementById('monthTabs');
  const panels = document.getElementById('monthPanels');
  tabs.innerHTML = MONTHS.map((m,i)=>`<button class="tab-btn ${{i===0?'active':''}}" onclick="switchTab('${{m.key}}',this)">${{m.label}}${{m.mtd?' <span style=\\"font-size:10px;opacity:0.6\\">(MTD)</span>':''}}</button>`).join('');
  panels.innerHTML = MONTHS.map((m,i)=>{{
    const mn = DATA.monthly[m.key], ns = DATA.newStores[m.key], nb = DATA.newBrands[m.key];
    const prev = i>0 ? MONTHS[i-1].key : null;
    const diff = prev ? mn.total - DATA.monthly[prev].total : 0;
    const diffTxt = m.baseline ? 'baseline' : (diff>=0?`+${{diff}} vs ${{MONTHS[i-1].short}}`:`${{diff}} vs ${{MONTHS[i-1].short}}`);
    let note = '';
    if(m.baseline) note = `<div class="note">January is the <strong>baseline month</strong> — the earliest data in this dataset. Its ${{ns.total.toLocaleString()}} stores represent the starting portfolio, not organic growth.</div>`;
    if(m.mtd) note = `<div class="note">June 2026 data is <strong>month-to-date (as of Jun 9)</strong>. Counts will grow through the month; the dip vs May is expected this early.</div>`;
    const ea = DATA.existingAdd[m.key]||[];
    const eaRows = ea.map(([b,c,s])=>`<tr><td>${{b}}</td><td><strong>${{c}}</strong></td><td><span class="badge ${{s}}">${{s.toUpperCase()}}</span></td></tr>`).join('');
    const eaBlock = ea.length ? `
      <div class="all-brands-wrap">
        <div class="all-brands-header"><h4>Existing Brands Adding New Stores in ${{m.short}}</h4></div>
        <table class="brands-table">
          <thead><tr><th>Brand</th><th>New Stores Added</th><th>Segment</th></tr></thead>
          <tbody>${{eaRows}}</tbody>
        </table>
      </div>` : '';
    return `<div id="panel-${{m.key}}" class="month-panel ${{i===0?'active':''}}">
      ${{note}}
      <div class="month-summary-grid" ${{note?'style="margin-top:16px"':''}}>
        <div class="mini-stat green"><div class="mini-label">Total Active${{m.mtd?' (MTD)':''}}</div><div class="mini-value">${{mn.total.toLocaleString()}}</div><div class="mini-desc">${{diffTxt}}</div></div>
        <div class="mini-stat green"><div class="mini-label">New${{m.mtd?' (MTD)':''}}</div><div class="mini-value">${{ns.total.toLocaleString()}}</div><div class="mini-desc">first-time active</div></div>
        <div class="mini-stat ent"><div class="mini-label">ENT New</div><div class="mini-value">${{ns.ent}}</div><div class="mini-desc">store_3p_ent</div></div>
        <div class="mini-stat smb"><div class="mini-label">SMB New</div><div class="mini-value">${{ns.smb}}</div><div class="mini-desc">store_3p_mm_smb</div></div>
        <div class="mini-stat"><div class="mini-label">New Brands</div><div class="mini-value">${{nb.total}}</div><div class="mini-desc">unique brands</div></div>
      </div>
      <div class="brands-grid">
        <div class="brand-section">
          <div class="brand-section-header"><h4>Top ENT New Brands</h4><span class="segment-pill ent">Enterprise</span></div>
          <div class="brand-list">${{brandListHTML(DATA.topNew[m.key].ent,'ent')}}</div>
        </div>
        <div class="brand-section">
          <div class="brand-section-header"><h4>Top SMB New Brands</h4><span class="segment-pill smb">SMB</span></div>
          <div class="brand-list">${{brandListHTML(DATA.topNew[m.key].smb,'smb')}}</div>
        </div>
      </div>
      ${{eaBlock}}
    </div>`;
  }}).join('');
}}

function switchTab(key, btn) {{
  document.querySelectorAll('.month-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('panel-'+key).classList.add('active');
  btn.classList.add('active');
}}

/* ── Top brand tables ── */
function fillTop(id, list) {{
  document.getElementById(id).innerHTML = list.map((x,i)=>`<tr>
    <td>${{i+1}}</td><td><strong>${{x.brand}}</strong></td><td>${{x.peak}}</td>
    <td>${{x.may}}</td><td>${{x.jun}}</td>
    <td>${{x.first}} 2026 ${{x.first!=='Jan'?'<span class="badge new-brand">NEW</span>':''}}</td>
    <td><span class="badge ${{x.vertical}}">${{x.vertical.toUpperCase()}}</span></td></tr>`).join('');
}}

/* ── Charts ── */
function buildCharts() {{
  const labels = MONTHS.map(m=>m.short+' 2026');
  new Chart(document.getElementById('chartNewStores'),{{type:'bar',data:{{labels,datasets:[
    {{label:'ENT (store_3p_ent)',data:MK.map(k=>DATA.newStores[k].ent),backgroundColor:entColor}},
    {{label:'SMB (store_3p_mm_smb)',data:MK.map(k=>DATA.newStores[k].smb),backgroundColor:smbColor}}]}},
    options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{font:{{size:11}},padding:12}}}}}},
    scales:{{x:{{stacked:true,grid:{{display:false}},ticks:{{font:{{size:11}}}}}},y:{{stacked:true,grid:{{color:'#f0f0ef'}},ticks:{{font:{{size:11}}}}}}}}}}}});

  new Chart(document.getElementById('chartTotal'),{{type:'line',data:{{labels,datasets:[{{
    label:'Active Stores',data:MK.map(k=>DATA.monthly[k].total),borderColor:accentColor,
    backgroundColor:'rgba(26,107,67,0.08)',fill:true,tension:0.3,pointRadius:5,pointBackgroundColor:accentColor}}]}},
    options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},
    scales:{{x:{{grid:{{display:false}},ticks:{{font:{{size:11}}}}}},y:{{min:900,grid:{{color:'#f0f0ef'}},ticks:{{font:{{size:11}}}}}}}}}}}});

  new Chart(document.getElementById('chartShare'),{{type:'bar',data:{{labels,datasets:[
    {{label:'ENT %',data:MK.map(k=>Math.round(DATA.monthly[k].ent/DATA.monthly[k].total*100)),backgroundColor:entColor}},
    {{label:'SMB %',data:MK.map(k=>Math.round(DATA.monthly[k].smb/DATA.monthly[k].total*100)),backgroundColor:smbColor}}]}},
    options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{font:{{size:11}},padding:12}}}}}},
    scales:{{x:{{stacked:true,grid:{{display:false}},ticks:{{font:{{size:11}}}}}},y:{{stacked:true,max:100,grid:{{color:'#f0f0ef'}},ticks:{{font:{{size:11}},callback:v=>v+'%'}}}}}}}}}});

  new Chart(document.getElementById('chartBrands'),{{type:'bar',data:{{labels,datasets:[
    {{label:'New ENT Brands',data:MK.map(k=>DATA.newBrands[k].ent),backgroundColor:entColor}},
    {{label:'New SMB Brands',data:MK.map(k=>DATA.newBrands[k].smb),backgroundColor:smbColor}}]}},
    options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{font:{{size:11}},padding:12}}}}}},
    scales:{{x:{{stacked:true,grid:{{display:false}},ticks:{{font:{{size:11}}}}}},y:{{stacked:true,grid:{{color:'#f0f0ef'}},ticks:{{font:{{size:11}}}}}}}}}}}});
}}

/* ── View switch ── */
function switchView(name, btn) {{
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.querySelectorAll('.main-nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('view-'+name).classList.add('active');
  btn.classList.add('active');
}}

/* ════ PARTNER DYNAMICS ════ */
const partnerData = DATA.partner;
function vals(d) {{ return MK.map(k=>d[k]); }}
function getStatus(d) {{
  const v = vals(d);
  const firstNZ = v.findIndex(x=>x>0);
  if(firstNZ===-1) return 'churned';
  const lastTwoZero = v[v.length-1]===0 && v[v.length-2]===0;
  if(firstNZ>0) {{ if(lastTwoZero) return 'churned'; return 'new'; }}
  if(lastTwoZero) return 'churned';
  const first = v[0];
  let latest = 0; for(let i=v.length-1;i>=0;i--){{if(v[i]>0){{latest=v[i];break;}}}}
  if(latest > first*1.1) return 'growing';
  if(latest < first*0.85) return 'declining';
  return 'stable';
}}
function sparkline(d) {{
  const v = vals(d), max = Math.max(...v,1), W=84,H=28,pad=4,n=v.length;
  const xs = v.map((_,i)=>pad+i*(W-pad*2)/(n-1));
  const ys = v.map(x=>H-pad-(x/max)*(H-pad*2));
  const dots = xs.map((x,i)=>`<circle cx="${{x}}" cy="${{ys[i]}}" r="2" fill="${{v[i]>0?'#1a6b43':'#e5e5e4'}}"/>`).join('');
  return `<svg class="spark" width="${{W}}" height="${{H}}" viewBox="0 0 ${{W}} ${{H}}">
    <polyline points="${{xs.map((x,i)=>x+','+ys[i]).join(' ')}}" fill="none" stroke="#1a6b43" stroke-width="1.5" opacity="0.6"/>${{dots}}</svg>`;
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
  document.querySelectorAll('#segAll,#segEnt,#segSmb').forEach(b=>b.className='filter-btn');
  btn.classList.add(seg==='all'?'active-all':(seg==='ent'?'active-ent':'active-smb'));
  renderPartnerTable();
}}
function setStatusFilter(st, btn) {{
  statusFilter=st;
  document.querySelectorAll('#stAll,#stGrowing,#stDeclining,#stNew,#stChurned').forEach(b=>b.classList.remove('active-all'));
  btn.classList.add('active-all'); renderPartnerTable();
}}
function cycleSortCol(col) {{
  if(sortCol===col) sortAsc=!sortAsc; else {{ sortCol=col; sortAsc=col==='brand'; }}
  document.getElementById('partnerSort').value=col;
  updateHead(); renderPartnerTable();
}}
function buildHead() {{
  const head = document.getElementById('partnerHead');
  let html = `<th onclick="cycleSortCol('brand')" id="th-brand">Brand <span class="sort-arrow">↕</span></th><th>Seg</th>`;
  MONTHS.forEach(m=>{{ html += `<th onclick="cycleSortCol('${{m.key}}')" id="th-${{m.key}}" class="num-cell">${{m.short}}${{m.mtd?' MTD':''}} <span class="sort-arrow">↕</span></th>`; }});
  html += `<th style="min-width:90px">Trend</th><th>Status</th>`;
  head.innerHTML = html; updateHead();
}}
function updateHead() {{
  ['brand',...MK,'total'].forEach(c=>{{
    const th=document.getElementById('th-'+c); if(!th) return;
    th.classList.toggle('sorted', c===sortCol);
    const a=th.querySelector('.sort-arrow'); if(a) a.textContent = c===sortCol?(sortAsc?'↑':'↓'):'↕';
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
  const tot = d=>MK.reduce((s,k)=>s+d[k],0);
  rows.sort((a,b)=>{{
    let va=sortCol==='brand'?a.brand:(sortCol==='total'?tot(a):a[sortCol]);
    let vb=sortCol==='brand'?b.brand:(sortCol==='total'?tot(b):b[sortCol]);
    if(va<vb) return sortAsc?-1:1; if(va>vb) return sortAsc?1:-1; return 0;
  }});
  const tbody=document.getElementById('partnerTbody');
  tbody.innerHTML=rows.map(d=>{{
    const st=getStatus(d);
    const seg=`<span class="badge ${{d.vertical}}">${{d.vertical.toUpperCase()}}</span>`;
    let cells='';
    MK.forEach((k,i)=>{{
      const prev = i>0 ? d[MK[i-1]] : 0;
      if(i===0) cells += `<td class="num-cell ${{d[k]===0?'zero':''}}">${{d[k]||'—'}}</td>`;
      else cells += (d[k]===0&&prev===0)?`<td class="num-cell zero">—</td>`:`<td class="num-cell">${{d[k]}}${{delta(d[k],prev)}}</td>`;
    }});
    return `<tr><td class="partner-name" title="${{d.brand}}">${{d.brand}}</td><td>${{seg}}</td>${{cells}}<td>${{sparkline(d)}}</td><td><span class="status-badge ${{st}}">${{st}}</span></td></tr>`;
  }}).join('');
  document.getElementById('partnerCount').textContent=`${{rows.length}} partner${{rows.length!==1?'s':''}}`;
  document.getElementById('partnerFooter').textContent=`Showing ${{rows.length}} of ${{partnerData.length}} brands · June data is month-to-date (as of Jun 9, 2026)`;

  const totals = MK.map(k=>rows.reduce((s,d)=>s+d[k],0));
  const newAdds = MK.map((k,i)=> i===0?0:rows.filter(d=>d[MK[i-1]]===0&&d[k]>0).reduce((s,d)=>s+d[k],0));
  function badge(diff,base){{ if(base) return `<span class="mtc-added neu">baseline</span>`;
    if(diff===0) return `<span class="mtc-added neu">±0</span>`;
    return diff>0?`<span class="mtc-added pos">+${{diff}}</span>`:`<span class="mtc-added neg">${{diff}}</span>`; }}
  document.getElementById('monthlyTotals').innerHTML = MONTHS.map((m,i)=>{{
    const diff = i>0 ? totals[i]-totals[i-1] : 0;
    const sub = m.baseline ? 'total stores' : (newAdds[i]>0?`${{newAdds[i]}} new stores added`:'');
    return `<div class="month-total-card ${{m.key===LATEST_FULL?'highlight':''}}">
      <span class="mtc-label">${{m.short}} 2026 ${{m.mtd?'<span style=\\"font-weight:400;opacity:0.7\\">MTD</span>':''}}</span>
      <div class="mtc-row"><span class="mtc-total">${{totals[i].toLocaleString()}}</span>${{badge(diff,m.baseline)}}</div>
      <span class="mtc-sub">${{sub}}</span></div>`;
  }}).join('');
}}

/* init */
buildMonths();
buildCharts();
fillTop('topEntBody', DATA.topEnt);
fillTop('topSmbBody', DATA.topSmb);
buildHead();
renderPartnerTable();
</script>
</body>
</html>
'''

# adjust monthly-totals grid to 6 columns
head_css = head_css.replace(
    '.monthly-totals {\n      display: grid;\n      grid-template-columns: repeat(4, 1fr);',
    '.monthly-totals {\n      display: grid;\n      grid-template-columns: repeat(6, 1fr);')

final = head_css + '\n</head>\n<body>\n' + body
open(OUT,'w',encoding='utf-8').write(final)
print("WROTE", OUT, len(final), "chars")
print("Peak", peak_label, peak_total, "organic", organic_new, "brands", total_brands, "split", split_e, split_s)
