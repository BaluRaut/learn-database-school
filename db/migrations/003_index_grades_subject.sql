-- a new question became common ("all maths grades") → a new card in the catalogue (lesson 06/08)
CREATE INDEX IF NOT EXISTS idx_grades_subject ON grades(subject);
