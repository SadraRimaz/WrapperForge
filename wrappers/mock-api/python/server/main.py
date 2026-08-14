import os
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lib import Task, TaskNotFoundError, TaskValidationError, TasksClient

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
client = TasksClient(BACKEND_URL)

app = FastAPI(title="Tasks API — Python QC Server")


class TaskCreateBody(BaseModel):
    title: str
    due_date: str


class TaskUpdateBody(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None
    due_date: Optional[str] = None


class BulkUpdateItemBody(BaseModel):
    id: str
    fields: TaskUpdateBody


class BulkUpdateRequestBody(BaseModel):
    items: list[BulkUpdateItemBody]


def _task_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "done": task.done,
        "due_date": task.due_date,
        "priority_score": task.priority_score,
        "created_at": task.created_at,
    }


@app.exception_handler(TaskNotFoundError)
def handle_not_found(request: Request, exc: TaskNotFoundError):
    content = exc.detail if exc.detail is not None else {"detail": str(exc)}
    return JSONResponse(status_code=404, content=content)


@app.exception_handler(TaskValidationError)
def handle_validation(request: Request, exc: TaskValidationError):
    content = exc.detail if exc.detail is not None else {"detail": str(exc)}
    return JSONResponse(status_code=422, content=content)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/wrapper/create", status_code=201)
def create(body: TaskCreateBody):
    task = client.create(body.title, body.due_date)
    return _task_dict(task)


@app.get("/wrapper/get/{id}")
def get(id: str):
    task = client.get(id)
    return _task_dict(task)


@app.get("/wrapper/list")
def list_tasks(done: Optional[bool] = None):
    tasks = client.list(done=done)
    return [_task_dict(t) for t in tasks]


@app.patch("/wrapper/update/{id}")
def update(id: str, body: TaskUpdateBody = TaskUpdateBody()):
    fields = body.model_dump(exclude_unset=True)
    task = client.update(id, **fields)
    return _task_dict(task)


@app.delete("/wrapper/delete/{id}", status_code=204)
def delete(id: str):
    client.delete(id)
    return Response(status_code=204)


@app.post("/wrapper/bulk_update")
def bulk_update(body: BulkUpdateRequestBody):
    items = [
        {"id": item.id, "fields": item.fields.model_dump(exclude_unset=True)}
        for item in body.items
    ]
    result = client.bulk_update(items)
    return {
        "succeeded": [_task_dict(t) for t in result.succeeded],
        "failed": [{"id": f.id, "error": f.error} for f in result.failed],
    }
