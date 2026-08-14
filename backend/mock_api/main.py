"""
Mock Tasks API — a hand-written, in-memory FastAPI backend.

Purpose: the fixed "provider" that every language wrapper/QC-server
pair is tested against. It is started fresh with a SEED env var so
that server-generated fields (priority_score, created_at) are
reproducible across separate process starts given the same seed and
the same sequence of calls.

Run standalone:
    SEED=42 uvicorn main:app --reload --port 8000
    $env:SEED=42; uvicorn main:app --reload --port 8000

Endpoints:
    GET    /health
    POST   /tasks
    GET    /tasks
    GET    /tasks/{task_id}
    PATCH  /tasks/{task_id}
    DELETE /tasks/{task_id}
    POST   /tasks/bulk_update
"""

import os
import uuid
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from seed import SeededGenerator

SEED = int(os.environ.get("SEED", "0"))
generator = SeededGenerator(SEED)

app = FastAPI(
    title="Mock Tasks API",
    version="1.0.0",
    description=(
        "A minimal, seeded, in-memory Tasks CRUD API used as the "
        "reference backend for the WrapperForge differential-QC "
        "pipeline. Server-generated fields (priority_score, "
        "created_at) are deterministic for a given SEED and call "
        "sequence."
    ),
)

# In-memory store: task_id -> task dict
_tasks: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str = Field(..., description="Task title.")
    due_date: date = Field(..., description="Due date, ISO 8601 (YYYY-MM-DD).")


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, description="New title, if changing.")
    done: Optional[bool] = Field(None, description="New done state, if changing.")
    due_date: Optional[date] = Field(None, description="New due date, if changing.")


class Task(BaseModel):
    id: str = Field(..., description="Server-generated unique task id (UUID4).")
    title: str
    done: bool
    due_date: date
    priority_score: float = Field(
        ..., description="Server-generated, seeded-random score in [0, 100)."
    )
    created_at: str = Field(
        ..., description="Server-generated ISO 8601 UTC timestamp, seeded jitter."
    )


class BulkUpdateItem(BaseModel):
    id: str
    fields: TaskUpdate


class BulkUpdateRequest(BaseModel):
    items: list[BulkUpdateItem]


class BulkUpdateError(BaseModel):
    id: str
    error: str


class BulkUpdateResponse(BaseModel):
    succeeded: list[Task]
    failed: list[BulkUpdateError]


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_task(title: str, due_date: date) -> dict:
    task = {
        "id": str(uuid.uuid4()),
        "title": title,
        "done": False,
        "due_date": due_date.isoformat(),
        "priority_score": generator.priority_score(),
        "created_at": generator.created_at(),
    }
    _tasks[task["id"]] = task
    return task


def _apply_update(task: dict, fields: TaskUpdate) -> dict:
    if fields.title is not None:
        task["title"] = fields.title
    if fields.done is not None:
        task["done"] = fields.done
    if fields.due_date is not None:
        task["due_date"] = fields.due_date.isoformat()
    return task


def _seed_fixture_tasks() -> None:
    """Deterministically pre-populate a few fixed-id tasks at startup.

    core/mock-api/cases.json needs literal, known-in-advance task ids for
    get/update/delete/bulk_update happy-path QC cases; tests/audit.py
    deliberately does no live derivation or response-chaining between
    cases, and normal create() ids are random uuid4s the client can't
    predict or set. These fixtures close that gap. Their priority_score
    / created_at still come from the seeded generator, so process
    restarts with the same SEED remain fully reproducible.
    """
    fixtures = [
        ("seed-task-1", "Seed Task One", date(2026, 1, 15)),
        ("seed-task-2", "Seed Task Two", date(2026, 2, 20)),
        ("seed-task-3", "Seed Task Three", date(2026, 3, 25)),
    ]
    for task_id, title, due_date in fixtures:
        _tasks[task_id] = {
            "id": task_id,
            "title": title,
            "done": False,
            "due_date": due_date.isoformat(),
            "priority_score": generator.priority_score(),
            "created_at": generator.created_at(),
        }


_seed_fixture_tasks()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", summary="Health check", response_model=dict)
def health():
    """Returns 200 with the active seed once the process is ready to serve."""
    return {"status": "ok", "seed": SEED}


@app.post(
    "/tasks",
    response_model=Task,
    status_code=201,
    summary="Create a task",
)
def create_task(payload: TaskCreate):
    """Creates a task. `id`, `priority_score`, and `created_at` are
    server-generated; `done` defaults to false."""
    task = _new_task(payload.title, payload.due_date)
    return task


@app.get("/tasks", response_model=list[Task], summary="List tasks")
def list_tasks(done: Optional[bool] = None):
    """Lists all tasks, optionally filtered by `done` state."""
    values = list(_tasks.values())
    if done is not None:
        values = [t for t in values if t["done"] == done]
    return values


@app.get(
    "/tasks/{task_id}",
    response_model=Task,
    responses={404: {"model": ErrorResponse}},
    summary="Get a task by id",
)
def get_task(task_id: str):
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.patch(
    "/tasks/{task_id}",
    response_model=Task,
    responses={404: {"model": ErrorResponse}},
    summary="Update a task",
)
def update_task(task_id: str, payload: TaskUpdate):
    """Partial update. Only fields present in the payload are changed.
    `priority_score` and `created_at` are never modified by update."""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task = _apply_update(task, payload)
    return task


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a task",
)
def delete_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    del _tasks[task_id]
    return JSONResponse(status_code=204, content=None)


@app.post(
    "/tasks/bulk_update",
    response_model=BulkUpdateResponse,
    summary="Bulk update tasks, tolerating partial failure",
)
def bulk_update(payload: BulkUpdateRequest):
    """Applies each item's field changes independently. Items with an
    unknown `id` fail individually and do not abort the batch; all
    other items still succeed. This is the deliberate partial-failure
    friction point described in the plan: each language wrapper/server
    must choose its own idiomatic way to represent a response that is
    part success, part failure."""
    succeeded: list[dict] = []
    failed: list[dict] = []

    for item in payload.items:
        task = _tasks.get(item.id)
        if task is None:
            failed.append({"id": item.id, "error": "Task not found"})
            continue
        task = _apply_update(task, item.fields)
        succeeded.append(task)

    return {"succeeded": succeeded, "failed": failed}
