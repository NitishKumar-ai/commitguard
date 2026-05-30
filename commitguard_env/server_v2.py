"""CommitGuard v2 — FastAPI endpoint definitions for repo-level scanning.

This module adds v2 endpoints to the existing v1 FastAPI app.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ScanRequest(BaseModel):
    """POST /scan request body."""
    repo_url: str


class ScanResponse(BaseModel):
    """POST /scan response."""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """GET /status/{job_id} response."""
    job_id: str
    repo_url: str
    status: str
    finding_count: int
    error: str | None = None
    created_at: str | None = None


class FindingResponse(BaseModel):
    """Single finding in the findings list."""
    file: str
    line_start: int
    line_end: int
    cwe_id: str
    cwe_name: str
    severity: str
    confidence: float
    exploit_sketch: str
    suggested_fix: str
    code_snippet: str


class VerifiedFindingResponse(BaseModel):
    """Single verified finding in the response."""
    file: str
    line_start: int
    line_end: int
    cwe_id: str
    cwe_name: str
    severity: str
    confidence: float
    verdict: str
    exploit_code: str
    exploit_output: str
    suggested_fix: str


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_v2_app(v1_app: FastAPI) -> FastAPI:
    """Mount v2 scan endpoints onto the existing v1 app.

    Parameters
    ----------
    v1_app : FastAPI
        The existing v1 FastAPI application (with /reset, /step, /state, /health).

    Returns
    -------
    FastAPI
        The same app instance with v2 routes added.
    """
    # Update app metadata
    v1_app.title = "CommitGuard v2 Server"
    v1_app.version = "2.0.0"
    v1_app.description = (
        "Autonomous security scanning agent. "
        "Scans public GitHub repos, detects vulnerabilities, and files GitHub Issues."
    )

    @v1_app.on_event("startup")
    async def startup_event() -> None:
        from commitguard_env.repo_agent import get_manager
        manager = get_manager()
        manager.start_background_tasks()

    # -- v2 endpoints --

    @v1_app.post("/scan", response_model=ScanResponse, tags=["v2"])
    async def scan(req: ScanRequest) -> ScanResponse:
        """Enqueue a repository scan job.

        Accepts a public GitHub repo URL and returns a job ID for polling.
        """
        from commitguard_env.repo_agent import get_manager

        if not req.repo_url or "github.com" not in req.repo_url:
            raise HTTPException(status_code=400, detail="Invalid repo URL. Must be a public GitHub URL.")

        manager = get_manager()
        job_id = manager.enqueue(req.repo_url)

        return ScanResponse(
            job_id=job_id,
            status="queued",
            message=f"Scan job enqueued for {req.repo_url}",
        )

    @v1_app.get("/status/{job_id}", response_model=JobStatusResponse, tags=["v2"])
    async def status(job_id: str) -> JobStatusResponse:
        """Poll the status of a scan job."""
        from commitguard_env.repo_agent import get_manager

        manager = get_manager()
        job = manager.get_status(job_id)

        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JobStatusResponse(
            job_id=job.job_id,
            repo_url=job.repo_url,
            status=job.status,
            finding_count=len(job.findings),
            error=job.error,
            created_at=job.created_at,
        )

    @v1_app.get("/findings/{job_id}", tags=["v2"])
    async def findings(job_id: str) -> dict[str, Any]:
        """Return full findings for a completed scan job."""
        from commitguard_env.repo_agent import get_manager

        manager = get_manager()
        job = manager.get_status(job_id)

        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        if job.status not in {"complete", "failed"}:
            return {
                "job_id": job_id,
                "status": job.status,
                "message": "Scan still in progress",
                "findings": [],
            }

        return {
            "job_id": job_id,
            "status": job.status,
            "finding_count": len(job.findings),
            "findings": [asdict(f) for f in job.findings],
        }

    @v1_app.get("/jobs", tags=["v2"])
    async def list_jobs() -> dict[str, Any]:
        """List all tracked scan jobs."""
        from commitguard_env.repo_agent import get_manager

        manager = get_manager()
        jobs = manager.list_jobs()

        return {
            "total": len(jobs),
            "jobs": [
                {
                    "job_id": j.job_id,
                    "repo_url": j.repo_url,
                    "status": j.status,
                    "finding_count": len(j.findings),
                    "created_at": j.created_at,
                }
                for j in jobs
            ],
        }

    @v1_app.post("/cancel/{job_id}", tags=["v2"])
    async def cancel(job_id: str) -> dict[str, Any]:
        """Cancel a running scan job."""
        from commitguard_env.repo_agent import get_manager

        manager = get_manager()
        cancelled = await manager.cancel(job_id)

        if not cancelled:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or already completed")

        return {"job_id": job_id, "status": "cancelled"}

    # -- v3 endpoints --

    @v1_app.get("/training/status", tags=["v3"])
    async def training_status() -> dict[str, Any]:
        """Return training pipeline status."""
        from commitguard_env.repo_agent import get_manager
        manager = get_manager()
        
        return {
            "new_examples_count": manager.pipeline.get_new_examples_count(),
            "retrain_threshold": manager.trainer.retrain_threshold,
        }

    @v1_app.post("/retrain/trigger", tags=["v3"])
    async def trigger_retrain() -> dict[str, Any]:
        """Manually trigger a retrain cycle."""
        from commitguard_env.repo_agent import get_manager
        manager = get_manager()
        
        job = await manager.trainer.trigger_retrain()
        return {
            "job_id": job.job_id,
            "status": job.status,
            "message": "Retrain cycle triggered.",
        }

    @v1_app.get("/retrain/status", tags=["v3"])
    async def retrain_status() -> dict[str, Any]:
        """Return current retrain job status."""
        from commitguard_env.repo_agent import get_manager
        manager = get_manager()
        
        job = manager.trainer.get_current_job()
        if job is None:
            return {"status": "No active retrain job."}
            
        from dataclasses import asdict
        return asdict(job)

    @v1_app.get("/adapter/current", tags=["v3"])
    async def current_adapter() -> dict[str, Any]:
        """Return info about the currently loaded adapter."""
        from commitguard_env.repo_agent import get_manager
        manager = get_manager()
        
        return {
            "adapter_path": manager.scanner._model_path,
            "base_model": manager.scanner._base_model,
        }

    logger.info("v2 endpoints mounted: /scan, /status, /findings, /jobs, /cancel")
    return v1_app
