"""The record room, live — every lesson's queries against a real SQLite database. (Lessons 01–12)

Zero dependencies: Python's built-in sqlite3. Run a section or all of them:
    python3 db/demo.py              # everything, in lesson order
    python3 db/demo.py join         # sections: reads join txn model index locks backup nplus1
"""
import os, sqlite3, sys, time, random, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "school.db")

def fresh():
    """Build school.db from schema + seed (lesson 02)."""
    if os.path.exists(DB): os.remove(DB)
    conn = sqlite3.connect(DB)
    conn.executescript(open(os.path.join(HERE, "schema.sql")).read())
    conn.executescript(open(os.path.join(HERE, "seed.sql")).read())
    conn.commit(); conn.close()
    print("🗄️  school.db built from schema.sql + seed.sql\n")

def connect():
    c = sqlite3.connect(DB, timeout=1.0)
    c.execute("PRAGMA foreign_keys = ON")
    return c

def show(title, rows):
    print(f"── {title}")
    for r in rows: print("   ", r)
    print()

def reads(c):                                             # lesson 03
    show("SELECT … WHERE … ORDER BY … LIMIT", c.execute(
        "SELECT name, roll_no FROM students WHERE class_id = 1 ORDER BY name LIMIT 2").fetchall())

def join(c):                                              # lesson 03
    show("JOIN — cross-referencing three registers", c.execute("""
        SELECT s.name, c.name AS class, g.subject, g.grade
        FROM grades g JOIN students s ON s.id = g.student_id JOIN classes c ON c.id = s.class_id
        WHERE g.subject = 'maths' ORDER BY g.grade, s.name""").fetchall())
    show("GROUP BY — one row per class", c.execute("""
        SELECT c.name, COUNT(*) AS students FROM students s JOIN classes c ON c.id = s.class_id GROUP BY c.name""").fetchall())

def txn(c):                                               # lesson 04
    before = c.execute("SELECT name, class_id FROM students WHERE id IN (1, 4) ORDER BY id").fetchall()
    show("before the transfer", before)
    try:
        with c:                                            # BEGIN … COMMIT, or ROLLBACK on any exception
            c.execute("UPDATE students SET class_id = 2 WHERE id = 1")          # Aarav → 3B
            c.execute("UPDATE students SET class_id = 99 WHERE id = 4")         # 💥 no class 99: FK fails
    except sqlite3.IntegrityError as e:
        print("   💥 second update failed:", e, "→ ROLLBACK\n")
    show("after — the pencil was erased, BOTH changes gone", c.execute(
        "SELECT name, class_id FROM students WHERE id IN (1, 4) ORDER BY id").fetchall())

def model(c):                                             # lesson 05
    show("one fact, one place — the class name lives in ONE row", c.execute("SELECT * FROM classes").fetchall())
    try:
        c.execute("INSERT INTO students (name, roll_no, class_id) VALUES ('Dup', '3A-02', 1)")
    except sqlite3.IntegrityError as e:
        print("   💥 duplicate roll_no refused by the schema:", e, "\n")
    try:
        c.execute("INSERT INTO grades (student_id, subject, term, grade) VALUES (1, 'maths', 1, 'Z')")
    except sqlite3.IntegrityError as e:
        print("   💥 impossible grade refused by CHECK:", e, "\n")

def index(c):                                             # lesson 06
    c.execute("CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY, student_id INTEGER, day TEXT, present INTEGER)")
    if c.execute("SELECT COUNT(*) FROM attendance").fetchone()[0] == 0:
        random.seed(1)
        c.executemany("INSERT INTO attendance (student_id, day, present) VALUES (?, ?, ?)",
                      [(random.randint(1, 5000), f"2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}", random.randint(0, 1)) for _ in range(200_000)])
        c.commit()
    q = "SELECT COUNT(*) FROM attendance WHERE student_id = 4242"
    def timed():
        t = time.perf_counter(); n = c.execute(q).fetchone()[0]; return n, (time.perf_counter() - t) * 1000
    plan = c.execute("EXPLAIN QUERY PLAN " + q).fetchall()
    n, ms = timed(); print(f"── without an index: {plan[0][3]} → {n} rows in {ms:.1f} ms")
    c.execute("CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id)")
    plan = c.execute("EXPLAIN QUERY PLAN " + q).fetchall()
    n, ms = timed(); print(f"── with the card catalogue: {plan[0][3]} → {n} rows in {ms:.1f} ms\n")

def locks(c):                                             # lesson 07
    other = sqlite3.connect(DB, timeout=0.2)
    other.execute("BEGIN IMMEDIATE")                                    # clerk 2 takes the write lock
    other.execute("UPDATE students SET name = 'Sita K' WHERE id = 2")   # …and has not committed yet
    show("clerk 1 reads while clerk 2's change is uncommitted (isolation)", c.execute("SELECT id, name FROM students WHERE id = 2").fetchall())
    try:
        c.execute("UPDATE students SET name = 'Sita R' WHERE id = 2")   # clerk 1 wants the same register
    except sqlite3.OperationalError as e:
        print("   ⏳ clerk 1 waited, then:", e, "— the lock protects the register\n")
    other.rollback(); other.close()

def backup(c):                                            # lesson 09
    copy = sqlite3.connect(os.path.join(HERE, "school.backup.db"))
    c.backup(copy); copy.close()                                        # the fireproof copy
    c.execute("DELETE FROM students WHERE id = 5"); c.commit()
    show("after the accident — Rohan is gone", c.execute("SELECT id, name FROM students ORDER BY id").fetchall())
    c.close(); shutil.copy(os.path.join(HERE, "school.backup.db"), DB)
    c2 = connect()
    show("after the restore — from the copy we tested", c2.execute("SELECT id, name FROM students ORDER BY id").fetchall())
    return c2

def nplus1(c):                                            # lesson 12
    t = time.perf_counter(); out = []
    for sid, name in c.execute("SELECT id, name FROM students").fetchall():          # 1 query …
        grades = c.execute("SELECT subject, grade FROM grades WHERE student_id = ?", (sid,)).fetchall()   # … + N more
        out.append((name, len(grades)))
    slow = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    one = c.execute("SELECT s.name, COUNT(g.id) FROM students s LEFT JOIN grades g ON g.student_id = s.id GROUP BY s.id").fetchall()
    fast = (time.perf_counter() - t) * 1000
    print(f"── N+1: {len(out)+1} queries, {slow:.2f} ms · one JOIN: 1 query, {fast:.2f} ms — same answer {one[:2]}…\n")

SECTIONS = dict(reads=reads, join=join, txn=txn, model=model, index=index, locks=locks, backup=backup, nplus1=nplus1)

if __name__ == "__main__":
    fresh()
    c = connect()
    for name in (sys.argv[1:] or list(SECTIONS)):
        print(f"═══ {name} ═══")
        r = SECTIONS[name](c)
        if r is not None: c = r
    c.close()
    print("✅ done — the record room survived every lesson")
