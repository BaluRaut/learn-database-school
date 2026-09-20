INSERT INTO classes (id, name) VALUES (1, '3A'), (2, '3B');
INSERT INTO students (id, name, roll_no, class_id) VALUES
  (1, 'Aarav', '3A-01', 1), (2, 'Sita', '3A-02', 1), (3, 'Kabir', '3A-03', 1),
  (4, 'Meera', '3B-01', 2), (5, 'Rohan', '3B-02', 2);
INSERT INTO grades (student_id, subject, term, grade) VALUES
  (1, 'maths', 1, 'A'),  (1, 'science', 1, 'B+'),
  (2, 'maths', 1, 'A+'), (2, 'science', 1, 'A+'),
  (3, 'maths', 1, 'B+'), (3, 'science', 1, 'B'),
  (4, 'maths', 1, 'A'),  (4, 'science', 1, 'A'),
  (5, 'maths', 1, 'B'),  (5, 'science', 1, 'C');
INSERT INTO homework (class_id, title, due) VALUES (1, 'read lesson 03', '2026-10-03'), (2, 'draw the ER diagram', '2026-10-05');
