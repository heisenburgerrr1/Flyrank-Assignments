from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A small in-memory CRUD API for a to-do list. Data lives in a "
    "Python list, so everything resets when the server restarts.",
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


def starting_tasks():
    return [
        Task(id=1, title="Buy milk", done=False),
        Task(id=2, title="Walk the dog", done=True),
        Task(id=3, title="Finish assignment", done=False),
    ]


tasks = starting_tasks()


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
    done = len([t for t in tasks if t.done])
    return {"total": len(tasks), "done": done, "open": len(tasks) - done}


@app.get("/tasks", response_model=list[Task], summary="List tasks")
def get_tasks(
    done: Optional[bool] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
):
    """
    Return the tasks, newest last.

    Optional filters: `done=true` keeps only finished tasks, `search=milk` keeps
    tasks whose title contains that word, and `limit`/`offset` page the result.
    """
    found = tasks

    if done is not None:
        found = [t for t in found if t.done == done]

    if search:
        found = [t for t in found if search.lower() in t.title.lower()]

    found = found[offset:]

    if limit is not None:
        found = found[:limit]

    return found


@app.get(
    "/tasks/{task_id}",
    response_model=Task,
    summary="Get one task",
    responses={404: {"model": Error, "description": "No task with that id"}},
)
def get_task(task_id: int):
    """Return the single task with this id, or 404 if there is none."""
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


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

    next_id = max((t.id for t in tasks), default=0) + 1
    task = Task(id=next_id, title=new_task.title, done=False)
    tasks.append(task)
    return task


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

    for task in tasks:
        if task.id == task_id:
            if updated.title is not None:
                task.title = updated.title
            if updated.done is not None:
                task.done = updated.done
            return task

    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Delete a task",
    responses={404: {"model": Error, "description": "No task with that id"}},
)
def delete_task(task_id: int):
    """Remove a task. Returns 204 and an empty body."""
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@app.post("/reset", response_model=list[Task], summary="Reset the demo data")
def reset_tasks():
    """Throw away every change and put the 3 example tasks back. Handy for demos."""
    global tasks
    tasks = starting_tasks()
    return tasks
