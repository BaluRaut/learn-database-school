-- Lesson 14: code that lives in the room — the PostgreSQL version.
-- SQLite (this repo's lab) has no stored procedures; db/demo.py procs runs the closest SQLite pieces.
-- This file is checked with PostgreSQL's own parser (pglast); run it in any Postgres 11+ against the same schema.

CREATE TABLE audit_log (id bigserial PRIMARY KEY, what text NOT NULL, at timestamptz NOT NULL DEFAULT now());

CREATE FUNCTION points(g text) RETURNS int
LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE g WHEN 'A+' THEN 10 WHEN 'A' THEN 9 WHEN 'B+' THEN 8 WHEN 'B' THEN 7 ELSE 6 END
$$;

CREATE PROCEDURE transfer_pupil(p_student int, p_class int)
LANGUAGE plpgsql AS $$
BEGIN
  IF (SELECT count(*) FROM students WHERE class_id = p_class) >= 3 THEN
    RAISE EXCEPTION 'class % is full (3 pupils)', p_class;
  END IF;
  UPDATE students SET class_id = p_class WHERE id = p_student;
  INSERT INTO audit_log (what) VALUES ('pupil ' || p_student || ' moved to class ' || p_class);
END
$$;

CALL transfer_pupil(1, 2);
SELECT s.name, sum(points(g.grade)) AS pts FROM grades g JOIN students s ON s.id = g.student_id GROUP BY s.name;
GRANT EXECUTE ON PROCEDURE transfer_pupil(int, int) TO school_api;
