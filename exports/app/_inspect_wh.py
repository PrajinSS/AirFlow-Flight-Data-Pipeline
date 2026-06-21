import sqlite3, json
PROJECT_ROOT = "d:/AirFlow"
db = PROJECT_ROOT + "/warehouse/warehouse.db"
conn = sqlite3.connect(db)
tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
schema = {}
for t in tables:
    cols = [(c[1], c[2]) for c in conn.execute(f"PRAGMA table_info({t})").fetchall()]
    count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    schema[t] = {"columns": cols, "row_count": count}
conn.close()
print(json.dumps(schema, indent=2))
