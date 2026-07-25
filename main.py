from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI()



class Task(BaseModel):
    id: int
    title: str
    done: bool = False


class TaskCreate(BaseModel):
    title: Optional[str] = None


tasks = [
    Task(id=1, title="Buy milk", done=False),
    Task(id=2, title="Walk the dog", done=True),
    Task(id=3, title="Finish assignment", done=False),
]


@app.get("/")
def read_root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/tasks")
def get_tasks():
    return tasks


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


# @app.post("/tasks", status_code=201)
# def create_task(new_task: TaskCreate):
#     if not new_task.title or not new_task.title.strip():
#         raise HTTPException(status_code=400, detail="Title is required")

#     next_id = max((t.id for t in tasks), default=0) + 1
#     task = Task(id=next_id, title=new_task.title, done=False)
#     tasks.append(task)
#     return task


# @app.put("/tasks/{task_id}")
# def update_task(task_id: int, updated: TaskCreate):
#     if not updated.title or not updated.title.strip():
#         raise HTTPException(status_code=400, detail="Title is required")

#     for task in tasks:
#         if task.id == task_id:
#             task.title = updated.title
#             return task

#     raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


# @app.delete("/tasks/{task_id}", status_code=204)
# def delete_task(task_id: int):
#     for i, task in enumerate(tasks):
#         if task.id == task_id:
#             tasks.pop(i)
#             return
#     raise HTTPException(status_code=404, detail=f"Task {task_id} not found")