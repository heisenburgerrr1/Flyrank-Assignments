-- Stage 4: SQL run directly against week2/tasks.db (outside the API) while the
-- API server was running. Each query's real result is pasted underneath it.

SELECT * FROM tasks;                  -- list every task
--   id | title | done
--   1 | Buy milk | 0
--   2 | Walk the dog | 1
--   3 | Finish assignment | 0
--   4 | Stage 2 task A | 0
--   5 | Stage 2 task B | 0
--   (5 rows)

SELECT * FROM tasks WHERE done = 1;   -- only completed tasks
--   id | title | done
--   2 | Walk the dog | 1
--   (1 row)

SELECT COUNT(*) FROM tasks;           -- how many tasks are there?
--   COUNT(*)
--   5
--   (1 row)

UPDATE tasks SET done = 1;            -- mark every task completed
--   5 rows changed.
--   GET /tasks straight afterwards, no restart:
--   [{"id":1,"title":"Buy milk","done":true},{"id":2,"title":"Walk the dog","done":true},{"id":3,"title":"Finish assignment","done":true},{"id":4,"title":"Stage 2 task A","done":true},{"id":5,"title":"Stage 2 task B","done":true}]

DELETE FROM tasks WHERE done = 1;     -- delete all completed tasks
--   5 rows changed.
--   GET /tasks straight afterwards, no restart:
--   []
-- After that last DELETE the table was empty. On the next server start the
-- "seed only when the table is empty" rule kicked in and put the 3 example
-- tasks back. GET /tasks after the restart:
--   [{"id":1,"title":"Buy milk","done":false},{"id":2,"title":"Walk the dog","done":true},{"id":3,"title":"Finish assignment","done":false}]
