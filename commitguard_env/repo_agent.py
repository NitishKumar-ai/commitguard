"""CommitGuard v2 Repo Agent — Jules-inspired async job runner.

Each scan job runs in an isolated context with no shared state between jobs.
Manages a job queue, spawns isolated scan workers, handles timeouts and retries.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import Finding, ScanJob

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_CONCURRENT_SCANS: int = 10
_JOB_TIMEOUT_SECONDS: int = 1800  # 30 minutes
_MAX_RETRIES: int = 1


# ---------------------------------------------------------------------------
# Scan Worker — isolated context per job
# ---------------------------------------------------------------------------


async def _run_scan_job(job: ScanJob, scanner: Any = None, verifier: Any = None, pipeline: Any = None) -> ScanJob:
    """Execute a single scan job in an isolated context.

    This function is designed to run in a background task.  It clones the repo,
    runs the 3-pass scanner, files GitHub issues, and returns the final job.
    """
    from .github_client import clone_repo, cleanup_clone, file_all_issues
    from .scanner_v2 import RepoScanner

    if scanner is None:
        scanner = RepoScanner()

    repo_path: Optional[Path] = None

    try:
        # Phase 1: Clone
        job = replace(job, status="cloning")
        logger.info("[%s] Cloning %s", job.job_id, job.repo_url)
        repo_path = await asyncio.to_thread(clone_repo, job.repo_url)

        # Phase 2: Plan + Execute + Review (3-pass scan)
        job = replace(job, status="scanning")
        logger.info("[%s] Starting 3-pass scan", job.job_id)

        findings: list[Finding] = await asyncio.to_thread(scanner.scan, repo_path)
        job = replace(job, findings=findings)
        logger.info("[%s] Scan complete: %d findings", job.job_id, len(findings))

        verified_findings = []
        if findings and verifier:
            # Phase 3: Verify (L2)
            job = replace(job, status="verifying")
            logger.info("[%s] Verifying %d findings in sandbox", job.job_id, len(findings))
            verified_findings = await asyncio.to_thread(verifier.verify_batch, findings, repo_path, "latest")
            
            # Filter for filing
            reportable = [vf.finding for vf in verified_findings if vf.verdict in {"CONFIRMED", "UNVERIFIABLE"}]
        else:
            reportable = findings

        # Phase 4: File GitHub issues
        if reportable:
            job = replace(job, status="filing")
            logger.info("[%s] Filing %d GitHub issues", job.job_id, len(reportable))
            try:
                await asyncio.to_thread(file_all_issues, job.repo_url, reportable)
            except Exception as exc:
                logger.warning("[%s] Issue filing failed (non-fatal): %s", job.job_id, exc)

        # Phase 5: Document (L3)
        if verified_findings and pipeline:
            job = replace(job, status="documenting")
            logger.info("[%s] Documenting %d verified findings", job.job_id, len(verified_findings))
            await asyncio.to_thread(pipeline.document_batch, verified_findings, job.repo_url, "latest")

        # Done
        job = replace(job, status="complete")
        logger.info("[%s] Job complete", job.job_id)

    except asyncio.CancelledError:
        job = replace(job, status="failed", error="Job cancelled (timeout)")
        logger.warning("[%s] Job cancelled", job.job_id)
    except Exception as exc:
        job = replace(job, status="failed", error=str(exc))
        logger.error("[%s] Job failed: %s", job.job_id, exc, exc_info=True)
    finally:
        # Cleanup clone
        if repo_path is not None:
            try:
                await asyncio.to_thread(cleanup_clone, repo_path)
            except Exception:
                pass

    return job


# ---------------------------------------------------------------------------
# AgentManager — queue + worker pool
# ---------------------------------------------------------------------------


class AgentManager:
    """Manages the scan job queue and worker pool.

    Jules-inspired: each job runs in complete isolation — no shared model state,
    no shared filesystem between concurrent scans.
    """

    def __init__(
        self,
        max_concurrent: int = _MAX_CONCURRENT_SCANS,
        job_timeout: int = _JOB_TIMEOUT_SECONDS,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._job_timeout = job_timeout
        self._jobs: dict[str, ScanJob] = {}
        self._tasks: dict[str, asyncio.Task[ScanJob]] = {}
        self._semaphore: asyncio.Semaphore | None = None
        self._started = False

        # v3 components
        from .scanner_v2 import RepoScanner
        from .verifier import ExploitVerifier
        from .training_pipeline import TrainingDataPipeline
        from .self_trainer import SelfTrainer
        
        self.scanner = RepoScanner()
        self.verifier = ExploitVerifier()
        self.pipeline = TrainingDataPipeline()
        self.trainer = SelfTrainer(pipeline=self.pipeline, scanner=self.scanner)
        
        self._trainer_task: Optional[asyncio.Task] = None

    def start_background_tasks(self) -> None:
        """Start self-trainer watch loop."""
        if self._trainer_task is None:
            self._trainer_task = asyncio.create_task(self.trainer.watch_loop())

    def _ensure_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return self._semaphore

    # -- Public API --

    def enqueue(self, repo_url: str) -> str:
        """Enqueue a new scan job.

        Parameters
        ----------
        repo_url : str
            GitHub repository URL to scan.

        Returns
        -------
        str
            The assigned job ID.
        """
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        job = ScanJob(
            job_id=job_id,
            repo_url=repo_url,
            status="queued",
            created_at=now,
        )
        self._jobs[job_id] = job

        # Launch as a background task
        task = asyncio.ensure_future(self._worker(job_id))
        self._tasks[job_id] = task

        logger.info("Enqueued job %s for %s", job_id, repo_url)
        return job_id

    def get_status(self, job_id: str) -> Optional[ScanJob]:
        """Return the current state of a job, or None if not found."""
        return self._jobs.get(job_id)

    def get_findings(self, job_id: str) -> list[Finding]:
        """Return findings for a completed job."""
        job = self._jobs.get(job_id)
        if job is None:
            return []
        return list(job.findings)

    def list_jobs(self) -> list[ScanJob]:
        """Return all tracked jobs."""
        return list(self._jobs.values())

    async def cancel(self, job_id: str) -> bool:
        """Cancel a running job. Returns True if cancelled."""
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            logger.info("Cancelled job %s", job_id)
            return True
        return False

    # -- Internal --

    async def _worker(self, job_id: str) -> None:
        """Execute a job with semaphore-based concurrency control and timeout."""
        sem = self._ensure_semaphore()

        async with sem:
            job = self._jobs[job_id]

            for attempt in range(_MAX_RETRIES + 1):
                try:
                    result = await asyncio.wait_for(
                        _run_scan_job(job, self.scanner, self.verifier, self.pipeline),
                        timeout=self._job_timeout,
                    )
                    self._jobs[job_id] = result

                    if result.status == "complete":
                        return
                    if attempt < _MAX_RETRIES:
                        logger.info("[%s] Retrying (attempt %d/%d)", job_id, attempt + 1, _MAX_RETRIES)
                        job = replace(job, status="queued", error=None)
                        continue
                except asyncio.TimeoutError:
                    self._jobs[job_id] = replace(
                        job, status="failed", error=f"Job timed out after {self._job_timeout}s"
                    )
                    logger.error("[%s] Job timed out", job_id)
                    return
                except asyncio.CancelledError:
                    self._jobs[job_id] = replace(job, status="failed", error="Job cancelled")
                    return
                except Exception as exc:
                    self._jobs[job_id] = replace(job, status="failed", error=str(exc))
                    logger.error("[%s] Worker error: %s", job_id, exc, exc_info=True)
                    return


# ---------------------------------------------------------------------------
# Module-level singleton (created on first import of server)
# ---------------------------------------------------------------------------

_manager: Optional[AgentManager] = None


def get_manager() -> AgentManager:
    """Return the global AgentManager singleton."""
    global _manager
    if _manager is None:
        _manager = AgentManager()
    return _manager
