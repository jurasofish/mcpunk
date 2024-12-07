import enum
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, String, TypeDecorator
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
)

from mcpunk.dependencies import deps
from mcpunk.unset import AnyUnset

CURRENT_DB_VERSION = "1"


def _remove_unset(d: dict[str, Any]) -> dict[str, Any]:
    """Return new dict with any key where the val is `shared_utils.unset.Unset` removed"""
    return {k: v for k, v in d.items() if v is not AnyUnset}


class TZDateTime(TypeDecorator):  # type: ignore[type-arg]
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        _ = dialect
        if value is not None and value.tzinfo is None:
            raise ValueError("DateTime must be timezone-aware")
        return value


class Base(DeclarativeBase):
    created: Mapped[datetime] = mapped_column(TZDateTime(), default=lambda: datetime.now(UTC))


@enum.unique
class TaskState(enum.StrEnum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"


@enum.unique
class TaskFollowUpCriticality(enum.StrEnum):
    NO_FOLLOWUP = "no_followup"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[TaskState] = mapped_column(
        Enum(
            TaskState,
            native_enum=False,
            create_constraint=True,
            values_callable=lambda py_enum: [e.value for e in py_enum],
        ),
        default=TaskState.TODO,
    )
    last_picked_up_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)
    action: Mapped[str] = mapped_column(String(2_000))
    outcome: Mapped[str | None] = mapped_column(String(10_000), nullable=True)
    follow_up_criticality: Mapped[TaskFollowUpCriticality] = mapped_column(
        Enum(
            TaskFollowUpCriticality,
            native_enum=False,
            create_constraint=True,
            values_callable=lambda py_enum: [e.value for e in py_enum],
        ),
        nullable=True,
    )

    @staticmethod
    def create(
        *,
        action: str,
    ) -> "Task":
        kwargs: dict[str, Any] = {
            "action": action,
        }
        return Task(**_remove_unset(kwargs))


class DBVersion(Base):
    __tablename__ = "db_version"
    id: Mapped[int] = mapped_column(primary_key=True)
    version = mapped_column(String(32))


class TaskManager:
    def __init__(self, session: Session) -> None:
        self.sess = session

    def add_task(self, action: str) -> None:
        task = Task.create(action=action)
        self.sess.add(task)

    def get_task(self) -> Task | None:
        stmt = (
            sa.select(Task)
            .where(
                sa.or_(
                    Task.state == TaskState.TODO,
                    sa.and_(
                        Task.state == TaskState.DOING,
                        sa.or_(
                            Task.last_picked_up_at == None,  # noqa: E711
                            Task.last_picked_up_at
                            < datetime.now(UTC) - deps.settings().task_queue_visibility_timeout,
                        ),
                    ),
                ),
            )
            .order_by(Task.created)
            .limit(1)
        )
        task = self.sess.execute(stmt).scalar_one_or_none()
        if task:
            task.state = TaskState.DOING
            task.last_picked_up_at = datetime.now(UTC)
        return task

    def set_task_done(
        self,
        task_id: int,
        outcome: str,
        follow_up_criticality: TaskFollowUpCriticality,
    ) -> None:
        task = self.sess.get(Task, task_id)
        if not task:
            raise ValueError(f"No task found with id {task_id}")

        task.state = TaskState.DONE
        task.outcome = outcome
        task.follow_up_criticality = follow_up_criticality


@contextmanager
def get_task_manager() -> Generator[TaskManager, None, None]:
    make_session = deps.session_maker()
    with make_session.begin() as sess:
        yield TaskManager(sess)


def _init_pragmas() -> None:
    """Call me liberally why not."""
    with deps.session_maker().begin() as sess:
        for stmt in [
            "PRAGMA journal_mode = WAL;",
            "PRAGMA synchronous = NORMAL;",
            "PRAGMA busy_timeout = 5000;",
            "PRAGMA cache_size = -20000;",
            "PRAGMA foreign_keys = ON;",
        ]:
            sess.execute(sa.text(stmt))


def _init_totally_new_db() -> None:
    db_path = deps.settings().db_path
    assert not db_path.exists()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _init_pragmas()
    with deps.session_maker().begin() as sess:
        Base.metadata.create_all(sess.get_bind())
        sess.add(DBVersion(version=CURRENT_DB_VERSION))


def init_db() -> None:
    if not deps.settings().db_path.exists():
        _init_totally_new_db()
    _init_pragmas()
    with deps.session_maker().begin() as sess:
        version = sess.scalars(sa.select(DBVersion.version)).one_or_none()
    if version != CURRENT_DB_VERSION:
        raise ValueError(
            f"Database version mismatch. Expected {CURRENT_DB_VERSION}, "
            f"got {version}. You might like to just delete the database and "
            f"it'll be automatically recreated.",
        )
