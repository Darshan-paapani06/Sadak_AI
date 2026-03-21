"""
SADAK AI — India Location Database Builder  (FINAL FIXED VERSION)
Reads LGD .xlsx files using direct XML parsing — handles inlineStr format.

Place files in lgd_data/ folder and run:
  python download_villages.py
"""
import os, sys, sqlite3, zipfile, re

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.path.join(BASE_DIR, "location.db")
LGD_FOLDER = os.path.join(BASE_DIR, "lgd_data")

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lgd_code TEXT, name TEXT NOT NULL UNIQUE, type TEXT DEFAULT 'STATE'
);
CREATE TABLE IF NOT EXISTS districts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lgd_code TEXT, state_id INTEGER REFERENCES states(id),
    name TEXT NOT NULL, UNIQUE(state_id, name)
);
CREATE TABLE IF NOT EXISTS localities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lgd_code TEXT, district_id INTEGER REFERENCES districts(id),
    name TEXT NOT NULL, type TEXT DEFAULT 'VILLAGE',
    UNIQUE(district_id, name)
);
CREATE INDEX IF NOT EXISTS idx_d_s ON districts(state_id);
CREATE INDEX IF NOT EXISTS idx_l_d ON localities(district_id);
"""

def read_xlsx_rows(path):
    """
    Read LGD xlsx by parsing XML directly.
    Handles inlineStr format that openpyxl misses.
    Returns (headers_list, data_rows_as_lists)
    Row 1 = title (skip), Row 2 = headers, Row 3+ = data
    """
    with zipfile.ZipFile(path) as z:
        xml = z.read('xl/worksheets/sheet1.xml').decode('utf-8', 'replace')

    raw_rows = re.findall(r'<row\b[^>]*>(.*?)</row>', xml, re.DOTALL)
    
    def parse_row(row_xml):
        cells_xml = re.findall(r'<c\b[^>]*r="([A-Z]+)\d+"[^>]*>(.*?)</c>', row_xml, re.DOTALL)
        result = {}
        for col_ref, cell_content in cells_xml:
            # inlineStr: <is><t>value</t></is>
            m = re.search(r'<is>.*?<t[^>]*>([^<]*)</t>', cell_content, re.DOTALL)
            if m:
                result[col_ref] = m.group(1).strip()
                continue
            # number or shared string: <v>value</v>
            m = re.search(r'<v>([^<]+)</v>', cell_content)
            if m:
                result[col_ref] = m.group(1).strip()
                continue
        return result

    if len(raw_rows) < 2:
        return [], []

    # Row 2 = headers (index 1)
    hdr_map = parse_row(raw_rows[1])
    # Convert col letters A,B,C... to index 0,1,2...
    def col_to_idx(col):
        n = 0
        for ch in col:
            n = n * 26 + (ord(ch) - ord('A') + 1)
        return n - 1

    max_col = max((col_to_idx(c) for c in hdr_map), default=0)
    headers = [''] * (max_col + 1)
    for col, val in hdr_map.items():
        headers[col_to_idx(col)] = val

    # Rows 3+ = data
    data = []
    for row_xml in raw_rows[2:]:
        cell_map = parse_row(row_xml)
        if not cell_map:
            continue
        row_vals = [''] * len(headers)
        for col, val in cell_map.items():
            idx = col_to_idx(col)
            if idx < len(row_vals):
                row_vals[idx] = val
        # Skip completely empty rows
        if not any(v.strip() for v in row_vals):
            continue
        data.append(dict(zip(headers, row_vals)))

    return headers, data

def find_file(folder, *keywords):
    if not os.path.exists(folder): return None
    for f in sorted(os.listdir(folder)):
        fl = f.lower()
        if any(k.lower() in fl for k in keywords):
            return os.path.join(folder, f)
    return None

def clean(v):
    v = str(v).strip()
    # Remove float suffix e.g. "28.0" -> "28"
    if re.match(r'^\d+\.0$', v):
        v = v[:-2]
    return v if v and v.lower() not in ('none','null','nan','') else ''

# ── MAIN ─────────────────────────────────────────────────
print("\n" + "="*55)
print("  SADAK AI — India Location Database Builder")
print("="*55)

if not os.path.exists(LGD_FOLDER) or not os.listdir(LGD_FOLDER):
    print(f"\n  Create folder: lgd_data/  and put your .xlsx files there.")
    input("Press Enter..."); sys.exit(0)

print(f"\n  Files found:")
for f in sorted(os.listdir(LGD_FOLDER)):
    kb = os.path.getsize(os.path.join(LGD_FOLDER,f))//1024
    print(f"    {f}  ({kb:,} KB)")

conn = sqlite3.connect(DB_PATH)
conn.executescript(DB_SCHEMA)

# ── STATES ────────────────────────────────────────────────
state_file = find_file(LGD_FOLDER, "state")
if state_file:
    print(f"\n{'─'*55}")
    print("  [1/4] Loading States...")
    headers, rows = read_xlsx_rows(state_file)
    print(f"  Headers: {headers}")
    print(f"  Data rows: {len(rows)}")
    added = 0
    for r in rows:
        name = clean(r.get('State Name (In English)', r.get('State Name','')))
        code = clean(r.get('State Code',''))
        flag = clean(r.get('State or UT','S'))
        if not name or len(name) < 2: continue
        stype = "UT" if flag == 'U' else "STATE"
        conn.execute("INSERT OR IGNORE INTO states(lgd_code,name,type) VALUES(?,?,?)", (code,name,stype))
        added += 1
    conn.commit()
    print(f"  States loaded: {added}")
    # Show sample
    sample = conn.execute("SELECT name,type FROM states LIMIT 5").fetchall()
    print(f"  Sample: {[s[0] for s in sample]}")

# ── DISTRICTS ─────────────────────────────────────────────
dist_file = find_file(LGD_FOLDER, "district")
if dist_file:
    print(f"\n{'─'*55}")
    print("  [2/4] Loading Districts...")
    headers, rows = read_xlsx_rows(dist_file)
    print(f"  Headers: {headers}")
    print(f"  Data rows: {len(rows)}")
    added = 0
    for r in rows:
        sname = clean(r.get('State Name (In English)', r.get('State Name','')))
        dname = clean(r.get('District Name(In English)', r.get('District Name','')))
        dcode = clean(r.get('District Code',''))
        if not sname or not dname: continue
        sid = conn.execute("SELECT id FROM states WHERE LOWER(name)=LOWER(?)",(sname,)).fetchone()
        if not sid:
            conn.execute("INSERT OR IGNORE INTO states(name) VALUES(?)",(sname,))
            conn.commit()
            sid = conn.execute("SELECT id FROM states WHERE LOWER(name)=LOWER(?)",(sname,)).fetchone()
        if not sid: continue
        conn.execute("INSERT OR IGNORE INTO districts(lgd_code,state_id,name) VALUES(?,?,?)", (dcode,sid[0],dname))
        added += 1
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM districts").fetchone()[0]
    print(f"  Districts loaded: {added}  (total in DB: {total})")

# ── VILLAGES ──────────────────────────────────────────────
vil_file = find_file(LGD_FOLDER, "village")
if vil_file:
    print(f"\n{'─'*55}")
    print("  [3/4] Loading Villages (46 MB — please wait 3-5 mins)...")
    headers, rows = read_xlsx_rows(vil_file)
    print(f"  Headers: {headers}")
    print(f"  Data rows: {len(rows):,}")
    added = 0; skipped = 0; batch = []
    for r in rows:
        dname = clean(r.get('District Name (In English)', r.get('District Name(In English)', r.get('District Name',''))))
        vname = clean(r.get('Village Name (In English)', r.get('Village Name','')))
        vcode = clean(r.get('Village Code', r.get('LGD Code','')))
        if not dname or not vname: skipped+=1; continue
        did = conn.execute("SELECT id FROM districts WHERE LOWER(name)=LOWER(?)",(dname,)).fetchone()
        if not did: skipped+=1; continue
        batch.append((vcode, did[0], vname, "VILLAGE"))
        if len(batch) >= 10000:
            conn.executemany("INSERT OR IGNORE INTO localities(lgd_code,district_id,name,type) VALUES(?,?,?,?)", batch)
            conn.commit(); added += len(batch); batch = []
            print(f"    {added:,} villages loaded...", end="\r", flush=True)
    if batch:
        conn.executemany("INSERT OR IGNORE INTO localities(lgd_code,district_id,name,type) VALUES(?,?,?,?)", batch)
        conn.commit(); added += len(batch)
    print(f"\n  Villages loaded: {added:,}  (skipped: {skipped:,})")

# ── SUB-DISTRICTS / TOWNS ─────────────────────────────────
sub_file = find_file(LGD_FOLDER, "sub_district","sub-district","subdistrict")
if sub_file:
    print(f"\n{'─'*55}")
    print("  [4/4] Loading Sub-Districts / Towns...")
    headers, rows = read_xlsx_rows(sub_file)
    print(f"  Headers: {headers}")
    print(f"  Data rows: {len(rows):,}")
    added = 0; batch = []
    for r in rows:
        dname = clean(r.get('District Name',''))
        tname = clean(r.get('Sub-district Name',''))
        tcode = clean(r.get('Sub-district Code',''))
        if not dname or not tname: continue
        did = conn.execute("SELECT id FROM districts WHERE LOWER(name)=LOWER(?)",(dname,)).fetchone()
        if not did: continue
        batch.append((tcode, did[0], tname, "TOWN"))
        if len(batch) >= 5000:
            conn.executemany("INSERT OR IGNORE INTO localities(lgd_code,district_id,name,type) VALUES(?,?,?,?)", batch)
            conn.commit(); added += len(batch); batch = []
    if batch:
        conn.executemany("INSERT OR IGNORE INTO localities(lgd_code,district_id,name,type) VALUES(?,?,?,?)", batch)
        conn.commit(); added += len(batch)
    print(f"  Sub-districts/Towns loaded: {added:,}")

# ── FINAL STATS ───────────────────────────────────────────
s = conn.execute("SELECT COUNT(*) FROM states").fetchone()[0]
d = conn.execute("SELECT COUNT(*) FROM districts").fetchone()[0]
v = conn.execute("SELECT COUNT(*) c FROM localities WHERE type='VILLAGE'").fetchone()[0]
t = conn.execute("SELECT COUNT(*) c FROM localities WHERE type='TOWN'").fetchone()[0]
conn.close()

print("\n" + "="*55)
print("  COMPLETE!")
print("="*55)
print(f"  States / UTs : {s}")
print(f"  Districts    : {d:,}")
print(f"  Villages     : {v:,}")
print(f"  Sub-districts: {t:,}")
print(f"  TOTAL        : {v+t:,}")
print(f"  DB           : {DB_PATH}")
print("="*55)
if v > 1000:
    print("\n  SUCCESS! Now run:  python app.py")
else:
    print("\n  Villages still 0 — the village file needs checking.")
    print("  Share the 'Headers:' line printed above with Claude.")
input("\nPress Enter to exit...")