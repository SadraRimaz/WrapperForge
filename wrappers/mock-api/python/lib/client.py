from __future__ import annotations

from typing import Any, Optional

import requests

from .errors import TaskNotFoundError, TaskValidationError
from .models import BulkUpdateFailure, BulkUpdateResult, Task

_UNSET = object()


class TasksClient:
    """Client for the Tasks API's real HTTP backend (see contract.md)."""

    def __init__(self, base_url: str, session: Optional[requests.Session] = None):
        self._base_url = base_url.rstrip("/")
        if session is not None:
            self._session = session
        else:
            self._session = requests.Session()
            # Always talks to a local backend — ignore ambient system/env
            # proxy config so it can't intercept and mis-route these calls.
            self._session.trust_env = False

    def create(self, title: str, due_date: str) -> Task:
        resp = self._session.post(
            f"{self._base_url}/tasks",
            json={"title": title, "due_date": due_date},
        )
        if resp.status_code == 422:
            raise TaskValidationError("Invalid input for create", detail=self._safe_json(resp))
        resp.raise_for_status()
        return Task.from_dict(resp.json())

    def get(self, task_id: str) -> Task:
        resp = self._session.get(f"{self._base_url}/tasks/{task_id}")
        if resp.status_code == 404:
            raise TaskNotFoundError(task_id, detail=self._safe_json(resp))
        resp.raise_for_status()
        return Task.from_dict(resp.json())

    def list(self, done: Optional[bool] = None) -> list[Task]:
        params = {}
        if done is not None:
            params["done"] = str(done).lower()
        resp = self._session.get(f"{self._base_url}/tasks", params=params)
        resp.raise_for_status()
        return [Task.from_dict(t) for t in resp.json()]

    def update(
        self,
        task_id: str,
        title: Any = _UNSET,
        done: Any = _UNSET,
        due_date: Any = _UNSET,
    ) -> Task:
        fields: dict = {}
        if title is not _UNSET:
            fields["title"] = title
        if done is not _UNSET:
            fields["done"] = done
        if due_date is not _UNSET:
            fields["due_date"] = due_date

        resp = self._session.patch(f"{self._base_url}/tasks/{task_id}", json=fields)
        if resp.status_code == 404:
            raise TaskNotFoundError(task_id, detail=self._safe_json(resp))
        if resp.status_code == 422:
            raise TaskValidationError("Invalid input for update", detail=self._safe_json(resp))
        resp.raise_for_status()
        return Task.from_dict(resp.json())

    def delete(self, task_id: str) -> None:
        resp = self._session.delete(f"{self._base_url}/tasks/{task_id}")
        if resp.status_code == 404:
            raise TaskNotFoundError(task_id, detail=self._safe_json(resp))
        resp.raise_for_status()

    def bulk_update(self, items: list[dict]) -> BulkUpdateResult:
        """`items`: list of `{"id": str, "fields": {title?, done?, due_date?}}`."""
        resp = self._session.post(f"{self._base_url}/tasks/bulk_update", json={"items": items})
        resp.raise_for_status()
        body = resp.json()
        succeeded = [Task.from_dict(t) for t in body["succeeded"]]
        failed = [BulkUpdateFailure(id=f["id"], error=f["error"]) for f in body["failed"]]
        return BulkUpdateResult(succeeded=succeeded, failed=failed)

    @staticmethod
    def _safe_json(resp: "requests.Response") -> Any:
        try:
            return resp.json()
        except ValueError:
            return None
