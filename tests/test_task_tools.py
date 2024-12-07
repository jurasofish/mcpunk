import json
from datetime import UTC, datetime, timedelta

import mcp.types as mcp_types
import pytest
import sqlalchemy as sa

from mcpunk import db, tools
from mcpunk.dependencies import deps
from mcpunk.settings import Settings


def test_add_tasks() -> None:
    """Test that add_tasks creates tasks with correct properties."""
    actions = ["task one", "task two"]
    prefix = "common stuff"
    tools.add_tasks(task_actions=actions, common_prefix=prefix)

    with deps.session_maker().begin() as sess:
        tasks = sess.scalars(sa.select(db.Task).order_by(db.Task.id)).all()
        assert len(tasks) == 2
        for task, action in zip(tasks, actions, strict=True):
            assert task.action == f"{prefix} {action}"
            assert task.state == db.TaskState.TODO
            assert task.outcome is None
            assert task.last_picked_up_at is None
            assert task.follow_up_criticality is None


def test_get_task() -> None:
    """Test that get_task returns and updates task correctly."""
    # Create tasks
    tools.add_tasks(task_actions=["task one", "task two"])

    # Get first task
    task_info_raw = tools.get_task()
    task_info_dict = json.loads(_squash_resp(task_info_raw))
    assert task_info_dict["action"] == "task one"
    task_id = task_info_dict["id"]

    # Verify task state updated
    with deps.session_maker().begin() as sess:
        task = sess.get_one(db.Task, task_id)
        assert task.state == db.TaskState.DOING
        assert task.last_picked_up_at is not None
        # Second task still in to do state
        other_task = sess.execute(sa.select(db.Task).where(db.Task.id != task_id)).scalar_one()
        assert other_task.state == db.TaskState.TODO


def test_get_task_none_available() -> None:
    """Test get_task when no tasks available."""
    result = tools.get_task()
    result_text = _squash_resp(result)
    assert result_text == "no tasks"


def test_mark_task_done() -> None:
    """Test marking a task as done with an outcome."""
    tools.add_tasks(task_actions=["task one"])

    with deps.session_maker().begin() as sess:
        task_id = sess.scalars(sa.select(db.Task)).one().id

    outcome = "completed successfully"
    result = tools.mark_task_done(
        task_id=task_id,
        outcome=outcome,
        follow_up_criticality="no_followup",
    )
    result_text = _squash_resp(result)
    assert result_text == "ok"

    with deps.session_maker().begin() as sess:
        task = sess.get_one(db.Task, task_id)
        assert task.state == db.TaskState.DONE
        assert task.outcome == outcome
        assert task.follow_up_criticality == db.TaskFollowUpCriticality.NO_FOLLOWUP


def test_mark_task_done_invalid_id() -> None:
    """Test marking a non-existent task as done."""
    invalid_id = 12345
    with pytest.raises(ValueError, match=f"No task found with id {invalid_id}"):
        tools.mark_task_done(
            task_id=invalid_id,
            outcome="doesn't matter",
            follow_up_criticality="no_followup",
        )


def _squash_resp(resp: tools.ToolResponse) -> str:
    if isinstance(resp, mcp_types.TextContent):
        return resp.text
    elif isinstance(resp, list):
        if not all(isinstance(x, mcp_types.TextContent) for x in resp):
            raise NotImplementedError(f"Unexpected type: {type(resp)}")
        squashed = " ".join(x.text for x in resp)
        return squashed
    else:
        raise NotImplementedError(f"Unexpected type: {type(resp)}")


def test_get_task_visibility_timeout() -> None:
    """Test that tasks become visible again after timeout."""
    # We want to ensure it's a large number so that we don't fly past it and cause
    # a flaky test.
    settings = Settings(task_queue_visibility_timeout_seconds=10_000)

    with deps.override(settings_partial=settings):
        tools.add_tasks(task_actions=["task one"])

        # Pick up task
        task_info_raw = tools.get_task()
        task_info_dict = json.loads(_squash_resp(task_info_raw))
        task_id = task_info_dict["id"]

        # Verify task unavailable immediately
        no_task_info = tools.get_task()
        assert _squash_resp(no_task_info) == "no tasks"

        # Move task pickup time to before timeout
        with deps.session_maker().begin() as sess:
            task = sess.get_one(db.Task, task_id)
            task.last_picked_up_at = (
                datetime.now(UTC)
                - deps.settings().task_queue_visibility_timeout
                - timedelta(seconds=1)
            )

        # Task should be available again
        task_info_raw = tools.get_task()
        task_info_dict = json.loads(_squash_resp(task_info_raw))
        assert task_info_dict["id"] == task_id  # Same task picked up
