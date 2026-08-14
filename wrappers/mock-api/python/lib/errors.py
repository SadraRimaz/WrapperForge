class TaskNotFoundError(Exception):
    """Raised when a task id does not match any stored task."""

    def __init__(self, task_id: str, detail=None):
        self.task_id = task_id
        self.detail = detail
        super().__init__(f"Task not found: {task_id!r}")


class TaskValidationError(Exception):
    """Raised when the backend rejects a request as invalid input (422)."""

    def __init__(self, message: str, detail=None):
        self.detail = detail
        super().__init__(message)
