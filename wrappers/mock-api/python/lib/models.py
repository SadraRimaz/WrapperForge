from dataclasses import dataclass


@dataclass
class Task:
    id: str
    title: str
    done: bool
    due_date: str
    priority_score: float
    created_at: str

    @staticmethod
    def from_dict(d: dict) -> "Task":
        return Task(
            id=d["id"],
            title=d["title"],
            done=d["done"],
            due_date=d["due_date"],
            priority_score=d["priority_score"],
            created_at=d["created_at"],
        )


@dataclass
class BulkUpdateFailure:
    id: str
    error: str


@dataclass
class BulkUpdateResult:
    succeeded: list[Task]
    failed: list[BulkUpdateFailure]
