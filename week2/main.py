import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Literal, Optional

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A small CRUD API for a to-do list. Tasks are stored in a SQLite "
    "database (tasks.db), so they survive server restarts.",
)


class Task(BaseModel):
    id: int
    title: str
    done: bool = False


class TaskCreate(BaseModel):
    title: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


class Error(BaseModel):
    error: str


# tasks.db sits next to this file, whatever folder the server is started from.
DB_PATH = Path(__file__).parent / "tasks.db"

SEED_TASKS = [("Buy milk", False), ("Walk the dog", True), ("Finish assignment", False)]


@contextmanager
def connect():
    """Open tasks.db (creating the file if it is missing), commit if the block
    succeeds, roll back if it raises, and always close the connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def seed(db):
    """Insert the 3 example tasks. It runs inside the caller's transaction, so
    either all 3 go in or, if anything fails, none of them do."""
    db.executemany(
        "INSERT INTO tasks (title, done, created_at, updated_at) "
        "VALUES (?, ?, datetime('now'), datetime('now'))",
        SEED_TASKS,
    )


def init_db():
    """Create the tasks table if needed and seed it, but only when it is empty."""
    with connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "id INTEGER PRIMARY KEY, "
            "title TEXT NOT NULL, "
            "done BOOLEAN NOT NULL DEFAULT 0, "
            "created_at TEXT, "
            "updated_at TEXT)"
        )

        # CREATE TABLE IF NOT EXISTS skips a table that already exists, so a
        # tasks.db made before the timestamp columns existed needs them added.
        columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)")}
        if "created_at" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN created_at TEXT")
        if "updated_at" not in columns:
            db.execute("ALTER TABLE tasks ADD COLUMN updated_at TEXT")

        # Lets WHERE done = ? jump to the matching rows instead of reading them all.
        db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks (done)")

        count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            seed(db)


def row_to_task(row):
    """Turn a database row into a Task. SQLite stores done as 0/1."""
    return Task(id=row["id"], title=row["title"], done=bool(row["done"]))


init_db()


# FastAPI's own errors look like {"detail": "..."}, but this API promises
# {"error": "..."}, so both error types get rewritten on the way out.
@app.exception_handler(HTTPException)
def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
def validation_error(request: Request, exc: RequestValidationError):
    problem = exc.errors()[0]
    where = ".".join(str(part) for part in problem["loc"][1:]) or "body"
    return JSONResponse(
        status_code=400, content={"error": f"Invalid {where}: {problem['msg']}"}
    )


@app.get("/", summary="About this API")
def read_root():
    """Front door: name, version and where to find the tasks."""
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", summary="Health check")
def health_check():
    """Says "ok" if the server is alive. Used by monitoring tools."""
    return {"status": "ok"}


@app.get("/stats", summary="Count tasks")
def get_stats():
    """How many tasks there are in total, how many are done and how many are open."""
    with connect() as db:
        total = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        done = db.execute("SELECT COUNT(*) FROM tasks WHERE done = 1").fetchone()[0]
    return {"total": total, "done": done, "open": total - done}


@app.get("/tasks", response_model=list[Task], summary="List tasks")
def get_tasks(
    done: Optional[bool] = None,
    search: Optional[str] = None,
    sort: Literal["id", "title"] = "id",
    limit: Optional[int] = Query(None, ge=0),
    offset: int = Query(0, ge=0),
):
    """
    Return the tasks, oldest first.

    Optional filters: `done=true` keeps only finished tasks, `search=milk` keeps
    tasks whose title contains that word, `sort=title` orders them A to Z, and
    `limit`/`offset` page the result. All of it is done by the SQL query.
    """
    where, params = [], []
    if done is not None:
        where.append("done = ?")
        params.append(done)
    if search:
        # % and _ are wildcards in LIKE, so escape them to match them literally.
        pattern = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("title LIKE ? ESCAPE '\\'")
        params.append(f"%{pattern}%")

    sql = "SELECT * FROM tasks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY title COLLATE NOCASE, id" if sort == "title" else " ORDER BY id"
    sql += " LIMIT ? OFFSET ?"
    params += [-1 if limit is None else limit, offset]

    with connect() as db:
        rows = db.execute(sql, params).fetchall()
    return [row_to_task(row) for row in rows]


@app.get(
    "/tasks/{task_id}",
    response_model=Task,
    summary="Get one task",
    responses={404: {"model": Error, "description": "No task with that id"}},
)
def get_task(task_id: int):
    """Return the single task with this id, or 404 if there is none."""
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return row_to_task(row)


@app.post(
    "/tasks",
    response_model=Task,
    status_code=201,
    summary="Create a task",
    responses={400: {"model": Error, "description": "Title missing or empty"}},
)
def create_task(new_task: TaskCreate):
    """Add a task. It gets the next free id and starts out not done."""
    if not new_task.title or not new_task.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")

    with connect() as db:
        task_id = db.execute(
            "INSERT INTO tasks (title, done, created_at, updated_at) "
            "VALUES (?, ?, datetime('now'), datetime('now'))",
            (new_task.title, False),
        ).lastrowid
    return Task(id=task_id, title=new_task.title, done=False)


@app.put(
    "/tasks/{task_id}",
    response_model=Task,
    summary="Update a task",
    responses={
        400: {"model": Error, "description": "Nothing to update, or empty title"},
        404: {"model": Error, "description": "No task with that id"},
    },
)
def update_task(task_id: int, updated: TaskUpdate):
    """Change a task's title, its done flag, or both. Send at least one of them."""
    if updated.title is None and updated.done is None:
        raise HTTPException(status_code=400, detail="Send a title and/or done")

    if updated.title is not None and not updated.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        task = row_to_task(row)
        if updated.title is not None:
            task.title = updated.title
        if updated.done is not None:
            task.done = updated.done

        db.execute(
            "UPDATE tasks SET title = ?, done = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (task.title, task.done, task_id),
        )
    return task


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Delete a task",
    responses={404: {"model": Error, "description": "No task with that id"}},
)
def delete_task(task_id: int):
    """Remove a task. Returns 204 and an empty body."""
    with connect() as db:
        deleted = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,)).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@app.post("/reset", response_model=list[Task], summary="Reset the demo data")
def reset_tasks():
    """Delete every task in the database and put the 3 example tasks back."""
    with connect() as db:
        db.execute("DELETE FROM tasks")
        seed(db)
        rows = db.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    return [row_to_task(row) for row in rows]
