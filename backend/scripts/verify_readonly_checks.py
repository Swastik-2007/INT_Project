"""
Read-only GPS processing check using a temporary directory,
and SQLite database non-destructive verification.
"""
import hashlib, tempfile, shutil, json
from pathlib import Path
import sqlite3

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw_surveys"
DB_PATH = PROJECT_ROOT / "lpu_wayfinder.db"

GPX_FILES = [
    "Main_gate to Admission & class area.gpx",
    "Block 30 to 32.gpx",
    "Block 32 to 34.gpx",
    "Block 34 to BH4.gpx",
]

print("=== 1. VERIFYING ORIGINAL GPX FILES IN data/raw_surveys/ ===")
hashes_before = {}
for fname in GPX_FILES:
    fpath = RAW_DIR / fname
    assert fpath.exists(), f"Missing file: {fpath}"
    with open(fpath, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    hashes_before[fname] = h
    print(f"  {fname}: {h[:16]}... (size: {fpath.stat().st_size:,} bytes)")

print("\n=== 2. RUNNING READ-ONLY GPS PARSING INTO A TEMP DIRECTORY ===")
import sys
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from scripts import analyze_gpx_surveys

with tempfile.TemporaryDirectory() as tmpdir:
    tmp_path = Path(tmpdir)
    print(f"  Created temp dir: {tmp_path}")
    
    # Run analysis using temp output dir
    all_parsed = []
    all_results = []
    for fname in GPX_FILES:
        p = analyze_gpx_surveys.parse_gpx(RAW_DIR / fname)
        r = analyze_gpx_surveys.analyze_track(p, fname)
        all_parsed.append(p)
        all_results.append(r)
    
    gaps = analyze_gpx_surveys.analyze_gaps(all_results)
    geojson = analyze_gpx_surveys.tracks_to_geojson(all_parsed, all_results)
    
    # Save to temp directory
    with open(tmp_path / "test_report.json", "w") as f:
        json.dump(all_results, f)
    with open(tmp_path / "test_overlay.geojson", "w") as f:
        json.dump(geojson, f)
    
    print(f"  Parsed {len(all_results)} tracks in temp dir successfully.")
    print(f"  Features in GeoJSON: {len(geojson['features'])}")
    line_features = [f for f in geojson['features'] if f['geometry']['type'] == 'LineString']
    point_features = [f for f in geojson['features'] if f['geometry']['type'] == 'Point']
    print(f"  LineString features (tracks): {len(line_features)}")
    print(f"  Point features (start/end markers): {len(point_features)}")
    
    # Confirm exactly 4 tracks and no fabricated connectors
    assert len(line_features) == 4, f"Expected 4 tracks, got {len(line_features)}"
    for lf in line_features:
        assert lf['properties']['verified'] is False
        assert lf['properties']['type'] == 'recorded_track'
    print("  ✓ Confirmed exactly 4 unverified LineString tracks.")
    
    # Confirm gaps are NOT connected
    assert len(gaps) == 3
    print(f"  ✓ Confirmed 3 unrecorded physical gaps (e.g. Block 34 indoor gap = {gaps[2]['gap_distance_m']}m).")

print("\n=== 3. CONFIRMING ORIGINAL GPX FILES ARE 100% UNCHANGED ===")
for fname in GPX_FILES:
    fpath = RAW_DIR / fname
    with open(fpath, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    assert h == hashes_before[fname], f"HASH MISMATCH on {fname}!"
    print(f"  ✓ {fname}: hash identical")

print("\n=== 4. CONFIRMING SQLITE DATABASE INTEGRITY ===")
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("SELECT id, block_number, name, category, verified FROM location ORDER BY id")
rows = cur.fetchall()
conn.close()

assert len(rows) == 5, f"Expected 5 locations, got {len(rows)}"
expected = [
    (1, "28", "Block 28", "Academic Block", 0),
    (2, "29", "Block 29", "Academic Block", 0),
    (3, "30", "Block 30", "Academic Block", 0),
    (4, "34", "Block 34", "Academic Block", 0),
    (5, "36", "Block 36", "Academic Block", 0),
]
for actual, exp in zip(rows, expected):
    assert actual == exp, f"Mismatch: actual {actual} vs expected {exp}"
    print(f"  ✓ Location preserved: id={actual[0]} {actual[2]} (verified={actual[4]})")

print("\nALL READ-ONLY VERIFICATION CHECKS PASSED.")
