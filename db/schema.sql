-- The record room, drawn properly. (Lessons 02 & 05)  One fact, one place.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS classes (
  id    INTEGER PRIMARY KEY,
  name  TEXT NOT NULL UNIQUE                 -- '3A', '3B'
);

CREATE TABLE IF NOT EXISTS students (
  id        INTEGER PRIMARY KEY,
  name      TEXT NOT NULL,
  roll_no   TEXT NOT NULL UNIQUE,            -- the register number on the ID card
  class_id  INTEGER NOT NULL REFERENCES classes(id)   -- which register this student sits in
);

CREATE TABLE IF NOT EXISTS grades (
  id          INTEGER PRIMARY KEY,
  student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  subject     TEXT NOT NULL,
  term        INTEGER NOT NULL CHECK (term IN (1, 2, 3)),
  grade       TEXT NOT NULL CHECK (grade IN ('A+','A','B+','B','C')),
  UNIQUE (student_id, subject, term)         -- one grade per student per subject per term
);

CREATE TABLE IF NOT EXISTS homework (
  id        INTEGER PRIMARY KEY,
  class_id  INTEGER NOT NULL REFERENCES classes(id),
  title     TEXT NOT NULL,
  due       TEXT                              -- ISO date, e.g. 2026-10-03
);

-- the card catalogue (lesson 06): the questions we ask most
CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_id);
CREATE INDEX IF NOT EXISTS idx_grades_student ON grades(student_id);
