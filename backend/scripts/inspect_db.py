"""Quick read-only database inspection script."""
import sqlite3, pathlib

DB = pathlib.Path(__file__).resolve().parent.parent.parent / "lpu_wayfinder.db"
conn = sqlite3.connect(str(DB))
c = conn.cursor()

print("=== Tables ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
for r in c.fetchall():
    print(f"  {r[0]}")

print("\n=== Locations ===")
c.execute("SELECT id, block_number, name, category, verified, entrance_point FROM location")
for r in c.fetchall():
    print(f"  id={r[0]} block={r[1]} name={r[2]} cat={r[3]} verified={r[4]} entrance={r[5]}")

print("\n=== Walkways ===")
c.execute("SELECT * FROM walkway")
rows = c.fetchall()
print(f"  {len(rows)} walkway records")
for r in rows:
    print(f"  {r}")

print("\n=== Surveys ===")
c.execute("SELECT id, name, verified, created_at FROM survey")
rows = c.fetchall()
print(f"  {len(rows)} survey records")
for r in rows:
    print(f"  id={r[0]} name={r[1]} verified={r[2]} created={r[3]}")

conn.close()
