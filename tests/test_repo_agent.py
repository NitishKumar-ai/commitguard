"""Tests for commitguard_env.repo_agent — async job lifecycle."""

from __future__ import annotations

import asyncio

import pytest

from commitguard_env.models import ScanJob
from commitguard_env.repo_agent import AgentManager


# ---------------------------------------------------------------------------
# AgentManager tests
# ---------------------------------------------------------------------------


class TestAgentManager:
    """Test the async job queue manager."""

    def test_enqueue_returns_job_id(self) -> None:
        manager = AgentManager()
        # We need an event loop for enqueue (it creates asyncio tasks)
        loop = asyncio.new_event_loop()
        try:
            job_id = loop.run_until_complete(asyncio.coroutine(lambda: manager.enqueue("https://github.com/test/repo"))())
        except Exception:
            # enqueue isn't a coroutine, but it needs a running loop for asyncio.ensure_future
            asyncio.set_event_loop(loop)
            job_id = manager.enqueue("https://github.com/test/repo")
        finally:
            # Cancel pending tasks
            for task in asyncio.all_tasks(loop):
                task.cancel()
            loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
            loop.close()

        assert isinstance(job_id, str)
        assert len(job_id) > 0

    def test_get_status_returns_none_for_unknown_id(self) -> None:
        manager = AgentManager()
        assert manager.get_status("nonexistent-id") is None

    def test_get_findings_returns_empty_for_unknown_id(self) -> None:
        manager = AgentManager()
        assert manager.get_findings("nonexistent-id") == []

    def test_list_jobs_empty_initially(self) -> None:
        manager = AgentManager()
        assert manager.list_jobs() == []

    def test_job_tracked_after_enqueue(self) -> None:
        manager = AgentManager()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            job_id = manager.enqueue("https://github.com/test/repo")
            job = manager.get_status(job_id)
            assert job is not None
            assert job.repo_url == "https://github.com/test/repo"
            assert job.status == "queued"
            assert job.job_id == job_id
        finally:
            for task in asyncio.all_tasks(loop):
                task.cancel()
            loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
            loop.close()

    def test_multiple_jobs_tracked(self) -> None:
        manager = AgentManager()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            id1 = manager.enqueue("https://github.com/test/repo1")
            id2 = manager.enqueue("https://github.com/test/repo2")
            assert len(manager.list_jobs()) == 2
            assert id1 != id2
        finally:
            for task in asyncio.all_tasks(loop):
                task.cancel()
            loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
            loop.close()


# ---------------------------------------------------------------------------
# ScanJob model tests
# ---------------------------------------------------------------------------


class TestScanJobModel:
    """Test the ScanJob dataclass."""

    def test_default_findings_empty(self) -> None:
        job = ScanJob(
            job_id="test-123",
            repo_url="https://github.com/test/repo",
            status="queued",
        )
        assert job.findings == []
        assert job.error is None

    def test_status_values(self) -> None:
        for status in ["queued", "cloning", "planning", "scanning", "reviewing", "filing", "complete", "failed"]:
            job = ScanJob(
                job_id="test",
                repo_url="https://github.com/test/repo",
                status=status,
            )
            assert job.status == status
