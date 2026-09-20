# 🔒 Lesson 07 — Concurrency & isolation: two clerks, one register

**📍 You are here:** Lesson **07** of 12 — Part 2 begins! · Previous: `lesson-06-indexes` · Next: `lesson-08-migrations`

---

## 📦 What's in this branch

Lessons 01–06, **plus** what happens when two clerks want the same
register at the same time: **locks**, **isolation levels**, and the
**deadlock** handshake.

## 🧒 Explain like I'm 5

Clerk 2 opens the students register, writes in pencil "Sita → Sita K"
(`BEGIN`, `UPDATE`) and walks off to check something before inking it.
Clerk 1 arrives:

- **Clerk 1 reads Sita's line.** She sees the *old* name. Pencil marks
  are private until inked — that is **isolation**. No peeking at
  half-done work.
- **Clerk 1 wants to write Sita's line too.** The register is held by
  clerk 2's pencil. Clerk 1 **waits** for the lock… and after a while
  gives up: "database is locked". The lock protected the line from two
  pencils at once.

How much pencil may a reader see? That dial is the **isolation level**:
from "only inked lines" (read committed, the usual default) to "as if
one clerk worked at a time" (serializable). Stricter means safer and
means more waiting.

And the classic trap — the **deadlock**: clerk 1 holds the students
register and wants grades; clerk 2 holds grades and wants students.
Neither can move. The archivist picks one, tears up their pencil work,
and tells them to start over. The cure is boring: **keep transactions
short, and take registers in the same order every time.**

## 🗺️ Diagram

```mermaid
sequenceDiagram
    participant A as 🧑‍💼 clerk 1
    participant DB as 🗄️ register
    participant B as 🧑‍💼 clerk 2
    B->>DB: 1 BEGIN; UPDATE students SET name='Sita K' WHERE id=2 (pencil, not committed)
    A->>DB: 2 SELECT name WHERE id=2
    DB-->>A: 'Sita' — the old, inked value (isolation)
    A->>DB: 3 UPDATE students SET name='Sita R' WHERE id=2
    DB-->>A: ⏳ waits for the lock… 'database is locked'
    B->>DB: 4 ROLLBACK (pencil erased) — the register is free again
```

## ❓ What

- **Locks**: writers take a lock on what they change; other writers
  wait. SQLite locks the whole database file for writes (one writer at a
  time, many readers with WAL mode); Postgres and MySQL lock **rows**,
  so two clerks on different students do not wait for each other.
- **Isolation levels** (SQL standard): *read uncommitted* (see pencil —
  almost never used), *read committed* (Postgres default), *repeatable
  read* (MySQL default; the same read returns the same rows within a
  transaction), *serializable* (as if sequential; may abort with
  "retry me").
- **Anomalies** the looser levels allow: dirty read, non-repeatable
  read, phantom rows, **lost update** (two clerks read 5, both write 6).
  For counters and money: `SELECT … FOR UPDATE`, or serializable, or an
  atomic `UPDATE … SET n = n + 1`.
- **Deadlock**: a cycle of waits. The database detects it and aborts one
  transaction; your code must be ready to **retry**.
- **Timeouts**: every lock wait needs one (`timeout=1.0` in our
  connection) — a wait without a timeout is a hang.

## 🤔 Why

Because "shared" (lesson 01's second promise) is the hardest of the
three. The bugs here are invisible in tests (one user) and catastrophic
in production (a sale, a ticket drop, a payroll run): double-booked
seats and lost updates are isolation problems wearing a business
costume.

## 🔧 How (in this repo)

`locks()` in [db/demo.py](../../db/demo.py) opens a second connection,
starts `BEGIN IMMEDIATE` (the write lock) with an uncommitted `UPDATE`,
then shows clerk 1 reading the old value and failing to write within the
timeout.

## 🧪 Try it

```bash
python3 db/demo.py locks
python3 - <<'EOF'
import sqlite3, threading
def clerk(name, delta):
    c = sqlite3.connect("db/school.db", timeout=5)
    with c:                                                       # atomic increment: no lost update
        c.execute("UPDATE homework SET title = title || ?", (delta,))
    print(name, "done")
ts = [threading.Thread(target=clerk, args=(f"clerk {i}", "!")) for i in range(5)]
[t.start() for t in ts]; [t.join() for t in ts]
c = sqlite3.connect("db/school.db"); print(c.execute("SELECT title FROM homework").fetchall())
EOF
```

## ✅ Verify — what you should see

`locks` prints the old name for clerk 1's read and then `database is locked` after the timeout. Your five threads each append one `!` — every title ends with exactly five `!`: the lock serialised the writers and no update was lost.

## 🏁 What you just proved

Readers never see pencil, writers wait for the lock, and five concurrent updates landed as five — not as one overwriting the others.

## ⚠️ Common mistakes

- read-then-write in two statements (`SELECT n` … `UPDATE SET n = 6`) — the lost update; use `SET n = n + 1` or a row lock
- transactions that stay open while waiting for a user — everyone else waits too
- no retry logic for deadlocks/serialization failures — the database *will* abort you sometimes
- assuming your ORM's default isolation is serializable — it is almost always read committed
- lock waits with no timeout

> 🏭 **Why this matters in production:** the "flash sale sold 101 of 100 items" story is a lost update; the "checkout hangs at 9 pm" story is a long transaction holding a lock. Both are a lesson-07 sentence to diagnose once you have felt them here.

## ⏭️ Next

The registers must change while school is open: **migrations** —
versioned scripts, the logbook, and expand → migrate → contract.

```bash
git checkout lesson-08-migrations
```
