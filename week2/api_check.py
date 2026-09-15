"""Runs the Assignment 1 API contract against a running server.

    python api_check.py                         # checks http://localhost:8000
    python api_check.py http://localhost:8001   # checks another server

Only uses the standard library. It creates one task, changes it and deletes
it again, so the example tasks are left alone. Exit code 0 means every check
passed.
"""
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
MISSING_ID = 999999
failures = 0


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req) as res:
            status, raw = res.status, res.read()
    except HTTPError as err:
        status, raw = err.code, err.read()
    return status, (json.loads(raw) if raw else None)


def check(name, ok):
    global failures
    print(("PASS  " if ok else "FAIL  ") + name)
    failures += not ok


def is_task(value):
    return (
        isinstance(value, dict)
        and set(value) == {"id", "title", "done"}
        and isinstance(value["id"], int)
        and isinstance(value["title"], str)
        and isinstance(value["done"], bool)
    )


def is_error(status, body, expected):
    return status == expected and isinstance(body, dict) and isinstance(body.get("error"), str)


status, body = call("GET", "/")
check("GET / -> 200 with the API name", status == 200 and body.get("name") == "Task API")

status, body = call("GET", "/health")
check("GET /health -> 200 {status: ok}", status == 200 and body == {"status": "ok"})

status, body = call("GET", "/tasks")
check("GET /tasks -> 200 and a list of tasks", status == 200 and all(map(is_task, body)))

status, body = call("GET", f"/tasks/{MISSING_ID}")
check("GET /tasks/<missing> -> 404 + error JSON", is_error(status, body, 404))

status, body = call("POST", "/tasks", {})
check("POST {} -> 400 + error JSON", is_error(status, body, 400))

status, body = call("POST", "/tasks", {"title": "   "})
check("POST blank title -> 400 + error JSON", is_error(status, body, 400))

status, body = call("POST", "/tasks", {"title": 123})
check("POST non-text title -> 400 + error JSON", is_error(status, body, 400))

status, created = call("POST", "/tasks", {"title": "api_check task"})
check("POST {title} -> 201 + new task, done=false",
      status == 201 and is_task(created) and created["title"] == "api_check task" and created["done"] is False)
task_id = created["id"]

status, body = call("GET", f"/tasks/{task_id}")
check("GET /tasks/<new id> -> 200 + same task", status == 200 and body == created)

status, body = call("GET", "/tasks")
check("GET /tasks includes the new task", created in body)

status, body = call("PUT", f"/tasks/{task_id}", {"title": "api_check renamed"})
check("PUT {title} -> 200 + renamed task",
      status == 200 and is_task(body) and body["title"] == "api_check renamed" and body["done"] is False)

status, body = call("PUT", f"/tasks/{task_id}", {"done": True})
check("PUT {done} -> 200 + task marked done",
      status == 200 and body == {"id": task_id, "title": "api_check renamed", "done": True})

status, body = call("PUT", f"/tasks/{task_id}", {})
check("PUT {} -> 400 + error JSON", is_error(status, body, 400))

status, body = call("PUT", f"/tasks/{task_id}", {"title": ""})
check("PUT empty title -> 400 + error JSON", is_error(status, body, 400))

status, body = call("PUT", f"/tasks/{MISSING_ID}", {"title": "nope"})
check("PUT /tasks/<missing> -> 404 + error JSON", is_error(status, body, 404))

status, body = call("DELETE", f"/tasks/{task_id}")
check("DELETE -> 204 with an empty body", status == 204 and body is None)

status, body = call("DELETE", f"/tasks/{task_id}")
check("DELETE the same task again -> 404 + error JSON", is_error(status, body, 404))

status, body = call("GET", f"/tasks/{task_id}")
check("GET the deleted task -> 404 + error JSON", is_error(status, body, 404))

print(f"\n{'ALL PASSED' if failures == 0 else f'{failures} FAILED'} against {BASE}")
sys.exit(1 if failures else 0)
