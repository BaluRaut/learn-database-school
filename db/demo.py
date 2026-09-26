"""The record room, live — every lesson's queries against a real SQLite database. (Lessons 01–18)

Zero dependencies: Python's built-in sqlite3. Run a section or all of them:
    python3 db/demo.py              # everything, in lesson order
    python3 db/demo.py join         # sections: reads join joins txn model index locks backup nplus1
                                    #           inject window procs wal replica appcode olap   (lessons 13–18)
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
    if not rows: print("    (no rows)")
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

def joins(c):                                             # lesson 03 — the JOIN family
    c.execute("DROP TABLE IF EXISTS library_cards")
    c.execute("CREATE TABLE library_cards (card INTEGER PRIMARY KEY, student_id INTEGER)")   # no FK: a visitor has a card too
    c.executemany("INSERT INTO library_cards VALUES (?, ?)", [(101, 1), (102, 2), (103, 4), (104, 9)])   # Aarav, Sita, Meera, a visitor
    on = "FROM students s {} library_cards l ON l.student_id = s.id"
    show("INNER JOIN — only pupils WITH a card (matches on both sides)", c.execute(
        "SELECT s.name, l.card " + on.format("INNER JOIN") + " ORDER BY l.card").fetchall())
    show("LEFT JOIN — every pupil; no card → NULL", c.execute(
        "SELECT s.name, l.card " + on.format("LEFT JOIN") + " ORDER BY s.id").fetchall())
    show("RIGHT JOIN — every card; a card with no pupil → NULL name", c.execute(
        "SELECT s.name, l.card " + on.format("RIGHT JOIN") + " ORDER BY l.card").fetchall())
    show("FULL OUTER JOIN — everyone from both sides", c.execute(
        "SELECT s.name, l.card " + on.format("FULL OUTER JOIN") + " ORDER BY s.id IS NULL, s.id").fetchall())
    show("anti-join (LEFT JOIN … WHERE card IS NULL) — pupils with NO card", c.execute(
        "SELECT s.name " + on.format("LEFT JOIN") + " WHERE l.card IS NULL ORDER BY s.id").fetchall())
    show("CROSS JOIN — every class × every subject (the timetable grid)", c.execute(
        "SELECT c.name, sub.subject FROM classes c CROSS JOIN (SELECT DISTINCT subject FROM grades) sub ORDER BY c.name, sub.subject").fetchall())
    show("self join — two pupils in the same class (study buddies)", c.execute("""
        SELECT a.name, b.name FROM students a JOIN students b ON a.class_id = b.class_id AND a.id < b.id ORDER BY a.id, b.id""").fetchall())
    c.execute("DROP TABLE library_cards"); c.commit()

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

def attendance(c):
    """200,000 attendance lines (lesson 06's big register; lesson 18 reports on it)."""
    c.execute("CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY, student_id INTEGER, day TEXT, present INTEGER)")
    if c.execute("SELECT COUNT(*) FROM attendance").fetchone()[0] == 0:
        random.seed(1)
        c.executemany("INSERT INTO attendance (student_id, day, present) VALUES (?, ?, ?)",
                      [(random.randint(1, 5000), f"2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}", random.randint(0, 1)) for _ in range(200_000)])
        c.commit()

def index(c):                                             # lesson 06
    attendance(c)
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

def inject(c):                                            # lesson 13
    typed = "x' OR '1'='1"                                               # what an attacker types as the roll number
    glued = "SELECT name FROM students WHERE roll_no = '" + typed + "'"   # ❌ gluing input into SQL
    print("── the glued query the database actually received:\n    " + glued)
    show("❌ string-glued login — every student leaks", c.execute(glued).fetchall())
    show("✅ parameterised (?) — the input is only ever a value", c.execute(
        "SELECT name FROM students WHERE roll_no = ?", (typed,)).fetchall())
    ro = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)                  # a read-only pass (least privilege)
    print("── the reporting app's read-only connection reads:", ro.execute("SELECT COUNT(*) FROM students").fetchone()[0], "students")
    try:
        ro.execute("DELETE FROM grades")
    except sqlite3.OperationalError as e:
        print("   🔒 …and cannot write:", e, "\n")
    ro.close()

POINTS = "CASE grade WHEN 'A+' THEN 10 WHEN 'A' THEN 9 WHEN 'B+' THEN 8 WHEN 'B' THEN 7 ELSE 6 END"

def window(c):                                            # lesson 14
    cte = f"WITH points AS (SELECT student_id, SUM({POINTS}) AS pts FROM grades GROUP BY student_id) "
    show("CTE + window: RANK() and a running total inside each class", c.execute(cte + """
        SELECT cl.name, s.name, p.pts,
               RANK() OVER (PARTITION BY cl.name ORDER BY p.pts DESC)            AS rank_in_class,
               SUM(p.pts) OVER (PARTITION BY cl.name ORDER BY p.pts DESC)        AS running_total
        FROM points p JOIN students s ON s.id = p.student_id JOIN classes cl ON cl.id = s.class_id
        ORDER BY cl.name, rank_in_class""").fetchall())
    show("subquery: above the school average (" + str(c.execute(cte + "SELECT AVG(pts) FROM points").fetchone()[0]) + ")", c.execute(cte + """
        SELECT s.name, p.pts FROM points p JOIN students s ON s.id = p.student_id
        WHERE p.pts > (SELECT AVG(pts) FROM points) ORDER BY p.pts DESC""").fetchall())
    c.execute(f"""CREATE VIEW IF NOT EXISTS report_card AS
        SELECT s.name, COUNT(*) AS subjects, SUM({POINTS}) AS pts FROM grades g JOIN students s ON s.id = g.student_id GROUP BY s.id""")
    show("VIEW report_card — a saved question, used like a table", c.execute("SELECT * FROM report_card ORDER BY pts DESC LIMIT 3").fetchall())

def procs(c):                                             # lesson 14 — code that lives in the room
    print("── SQLite has no stored procedures (it runs inside your app); db/postgres/procedures.sql is the Postgres version.")
    print("   The closest SQLite pieces: a function the SQL can call, and a rule the room enforces for every app.\n")
    c.create_function("points", 1, lambda g: {"A+": 10, "A": 9, "B+": 8, "B": 7}.get(g, 6), deterministic=True)
    show("points(grade) — a function used inside SQL (Postgres: CREATE FUNCTION points)", c.execute(
        "SELECT s.name, SUM(points(g.grade)) AS pts FROM grades g JOIN students s ON s.id = g.student_id GROUP BY s.id ORDER BY pts DESC LIMIT 3").fetchall())
    c.execute("""CREATE TRIGGER IF NOT EXISTS class_limit BEFORE UPDATE OF class_id ON students
                 WHEN (SELECT COUNT(*) FROM students WHERE class_id = NEW.class_id) >= 3
                 BEGIN SELECT RAISE(ABORT, 'class is full (3 pupils)'); END""")
    for sid, cls, who in ((4, 1, "Meera → 3A"), (1, 2, "Aarav → 3B")):
        try:
            with c: c.execute("UPDATE students SET class_id = ? WHERE id = ?", (cls, sid))
            print(f"   ✅ {who}: moved")
        except sqlite3.IntegrityError as e:
            print(f"   ⛔ {who}: {e} — refused by the room itself, whichever app asked")
    c.execute("UPDATE students SET class_id = 1 WHERE id = 1"); c.execute("DROP TRIGGER class_limit"); c.commit(); print()

def wal(c):                                               # lesson 15
    print("── journal mode before:", c.execute("PRAGMA journal_mode").fetchone()[0], "→ after:", c.execute("PRAGMA journal_mode=WAL").fetchone()[0])
    reader = sqlite3.connect(DB, isolation_level=None)
    reader.execute("BEGIN"); snap = reader.execute("SELECT name FROM students WHERE id = 1").fetchone()[0]
    c.execute("UPDATE students SET name = 'Aarav S' WHERE id = 1"); c.commit()   # the writer does NOT wait for the reader
    print(f"   ✍️  writer committed 'Aarav S' while the reader was mid-transaction — no 'database is locked'")
    print(f"   👀 reader, same transaction, still sees its snapshot: {reader.execute('SELECT name FROM students WHERE id = 1').fetchone()[0]!r} (was {snap!r})")
    reader.execute("COMMIT")
    print(f"   👀 reader, new transaction: {reader.execute('SELECT name FROM students WHERE id = 1').fetchone()[0]!r}")
    reader.close()
    print(f"   📼 school.db-wal holds the new pages first: {os.path.getsize(DB + '-wal'):,} bytes")
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    print(f"   🧹 checkpoint copies them into school.db: -wal now {os.path.getsize(DB + '-wal'):,} bytes")
    c.execute("UPDATE students SET name = 'Aarav' WHERE id = 1"); c.commit()
    print("── journal mode back to:", c.execute("PRAGMA journal_mode=DELETE").fetchone()[0], "\n")

def replica(c):                                           # lesson 16 — two SQLite rooms stand in for a primary and a replica
    rep = sqlite3.connect(":memory:"); c.backup(rep)                     # the base copy
    shipped = []                                                          # the change log on its way to the replica
    def write(sql, args): c.execute(sql, args); c.commit(); shipped.append((sql, args))
    def ship():
        for sql, args in shipped: rep.execute(sql, args)
        rep.commit(); shipped.clear()
    count = lambda db: db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    print("── (simulated: school.db is the primary, an in-memory copy is the replica, a Python list is the shipped log)")
    write("INSERT INTO students (name, roll_no, class_id) VALUES (?, ?, ?)", ("Diya", "3B-03", 2))
    print(f"── primary: {count(c)} students · replica, before the log arrives: {count(rep)} — replication lag")
    print("   ↳ a parent who just enrolled Diya and reloads from the replica sees NO Diya: read your own writes from the primary")
    ship(); print(f"── log shipped → replica: {count(rep)} students")
    write("INSERT INTO students (name, roll_no, class_id) VALUES (?, ?, ?)", ("Ishaan", "3B-04", 2))
    print("   💥 the primary dies before shipping Ishaan's line → promote the replica (failover)")
    names = [r[0] for r in rep.execute("SELECT name FROM students ORDER BY id").fetchall()]
    print(f"── new primary has {len(names)} students: Ishaan {'is there' if 'Ishaan' in names else 'is LOST'} — async replication can lose the last writes (RPO > 0);")
    print("   synchronous replication waits for the replica's 'got it' before COMMIT returns, so nothing is lost — each commit pays a round trip\n")
    rep.close()
    c.execute("DELETE FROM students WHERE roll_no IN ('3B-03', '3B-04')"); c.commit()

def appcode(c):                                           # lesson 17
    c.execute("CREATE TABLE IF NOT EXISTS visits (id INTEGER PRIMARY KEY, student_id INTEGER, at TEXT)")
    rows = [(i % 5 + 1, f"2026-09-{i % 28 + 1:02d}") for i in range(2000)]
    t = time.perf_counter()
    for r in rows: c.execute("INSERT INTO visits (student_id, at) VALUES (?, ?)", r); c.commit()   # commit per row
    each = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    with c: c.executemany("INSERT INTO visits (student_id, at) VALUES (?, ?)", rows)            # one transaction
    batch = (time.perf_counter() - t) * 1000
    print(f"── 2,000 inserts: commit per row {each:.0f} ms · one transaction {batch:.0f} ms — every COMMIT is a trip to the disk")
    other = sqlite3.connect(DB, timeout=0); other.execute("BEGIN IMMEDIATE")   # another app holds the write lock
    busy = sqlite3.connect(DB, timeout=0)
    for attempt in range(1, 5):
        try:
            with busy: busy.execute("UPDATE students SET name = name WHERE id = 1")
            print(f"   ✅ attempt {attempt}: done"); break
        except sqlite3.OperationalError as e:
            wait = 0.05 * 2 ** (attempt - 1)
            print(f"   ⏳ attempt {attempt}: {e} → retry in {wait*1000:.0f} ms (backoff)")
            if attempt == 2: other.rollback()                           # the other app finishes its work
            time.sleep(wait)
    other.close(); busy.close()
    c.execute("DROP TABLE visits"); c.commit(); print()

def olap(c):                                              # lesson 18
    attendance(c)
    report = "SELECT substr(day, 1, 7) AS month, ROUND(AVG(present) * 100, 1) FROM attendance GROUP BY month ORDER BY month LIMIT 3"
    t = time.perf_counter(); live = c.execute(report).fetchall(); ms_live = (time.perf_counter() - t) * 1000
    c.execute("DROP TABLE IF EXISTS attendance_by_month")
    c.execute("""CREATE TABLE attendance_by_month AS                          -- the nightly ETL job
                 SELECT substr(day, 1, 7) AS month, COUNT(*) AS lines, AVG(present) AS rate FROM attendance GROUP BY month""")
    t = time.perf_counter()
    warm = c.execute("SELECT month, ROUND(rate * 100, 1) FROM attendance_by_month ORDER BY month LIMIT 3").fetchall()
    ms_warm = (time.perf_counter() - t) * 1000
    print(f"── report on the live 200,000-line table: {ms_live:.1f} ms · on the nightly summary (12 rows): {ms_warm:.2f} ms")
    print(f"   same answer: {live == warm} → {warm}")
    c.execute("CREATE TABLE IF NOT EXISTS grade_changes (id INTEGER PRIMARY KEY, grade_id INTEGER, old TEXT, new TEXT, at TEXT DEFAULT CURRENT_TIMESTAMP)")
    c.execute("""CREATE TRIGGER IF NOT EXISTS cdc_grades AFTER UPDATE OF grade ON grades
                 BEGIN INSERT INTO grade_changes (grade_id, old, new) VALUES (OLD.id, OLD.grade, NEW.grade); END""")
    c.execute("UPDATE grades SET grade = 'A' WHERE student_id = 5 AND subject = 'maths'"); c.commit()
    show("CDC: a trigger records every grade change for the warehouse to pick up", c.execute("SELECT grade_id, old, new FROM grade_changes").fetchall())

SECTIONS = dict(reads=reads, join=join, joins=joins, txn=txn, model=model, index=index, locks=locks, backup=backup, nplus1=nplus1,
                inject=inject, window=window, procs=procs, wal=wal, replica=replica, appcode=appcode, olap=olap)

if __name__ == "__main__":
    fresh()
    c = connect()
    for name in (sys.argv[1:] or list(SECTIONS)):
        print(f"═══ {name} ═══")
        r = SECTIONS[name](c)
        if r is not None: c = r
    c.close()
    print("✅ done — the record room survived every lesson")
