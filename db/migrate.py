"""Renovate the record room while school is open. (Lesson 08)

Applies db/migrations/*.sql in order, once each, remembering what ran in schema_migrations.
    python3 db/migrate.py            # apply pending
    python3 db/migrate.py status     # what has run
"""
import os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "school.db")

def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))")
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    files = sorted(f for f in os.listdir(os.path.join(HERE, "migrations")) if f.endswith(".sql"))
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        for f in files: print(("✅" if f in done else "⏳"), f)
        return
    for f in files:
        if f in done: continue
        sql = open(os.path.join(HERE, "migrations", f), encoding="utf-8").read()
        with conn:                                  # one migration = one transaction: all or nothing
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (f,))
        print("applied", f)
    print("up to date:", len(files), "migrations")

if __name__ == "__main__":
    main()
