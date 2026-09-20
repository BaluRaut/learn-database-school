-- expand: add a column with a default — old code keeps working, new code starts using it (lesson 08)
ALTER TABLE students ADD COLUMN house TEXT NOT NULL DEFAULT 'red';
