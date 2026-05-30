"""CommitGuard v3 L4 Self-Training Trigger.

Monitors the L3 training pipeline and automatically triggers a LoRA rerun
when enough new verified findings have been collected.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import RetrainJob
from .scanner_v2 import RepoScanner
from .training_pipeline import TrainingDataPipeline

logger = logging.getLogger(__name__)


class SelfTrainer:
    """Monitors training data and triggers LoRA retraining."""

    def __init__(
        self,
        pipeline: TrainingDataPipeline,
        scanner: RepoScanner,
        retrain_threshold: int = 500,
        gcs_bucket: str = "commitguard",
        adapters_prefix: str = "adapters/",
        training_script_path: str = "scripts/train_gemma.py",
    ) -> None:
        self.pipeline = pipeline
        self.scanner = scanner
        self.retrain_threshold = retrain_threshold
        self.gcs_bucket = gcs_bucket
        self.adapters_prefix = adapters_prefix
        self.training_script_path = training_script_path
        self._current_job: Optional[RetrainJob] = None
        self._running = False

    async def watch_loop(self, check_interval_seconds: int = 3600) -> None:
        """Background loop to monitor new examples and trigger retraining."""
        self._running = True
        logger.info("SelfTrainer watch loop started. Threshold: %d", self.retrain_threshold)
        
        while self._running:
            try:
                count = self.pipeline.get_new_examples_count()
                if count >= self.retrain_threshold:
                    if self._current_job is None or self._current_job.status in {"complete", "failed"}:
                        logger.info("Threshold reached (%d >= %d). Triggering retrain.", count, self.retrain_threshold)
                        await self.trigger_retrain()
            except Exception as exc:
                logger.error("Error in SelfTrainer watch loop: %s", exc)
                
            await asyncio.sleep(check_interval_seconds)

    def stop(self) -> None:
        """Stop the watch loop."""
        self._running = False

    def get_current_job(self) -> Optional[RetrainJob]:
        return self._current_job

    async def trigger_retrain(self) -> RetrainJob:
        """Manually trigger a retrain cycle."""
        job_id = str(uuid.uuid4())
        
        # Flush pending examples to GCS before training
        self.pipeline.flush_to_gcs()
        new_count = self.pipeline.get_new_examples_count()
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        adapter_path = f"gs://{self.gcs_bucket}/{self.adapters_prefix}lora_{timestamp}"
        
        self._current_job = RetrainJob(
            job_id=job_id,
            status="pending",
            new_examples_count=new_count,
            adapter_path=adapter_path,
            started_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Start training in background
        asyncio.create_task(self._run_training_cycle(job_id, adapter_path))
        
        return self._current_job

    async def _run_training_cycle(self, job_id: str, adapter_path: str) -> None:
        """Execute the training process and hot-swap the adapter."""
        if self._current_job is None or self._current_job.job_id != job_id:
            return
            
        from dataclasses import replace
        
        try:
            self._current_job = replace(self._current_job, status="training")
            logger.info("[%s] Starting training cycle. Target adapter: %s", job_id, adapter_path)
            
            # Here we would normally run the training script.
            # In a real environment, we might pull down the delta from GCS, merge, and run.
            # For the scope of the prototype/plan, we'll simulate the subprocess call.
            
            # Simulate training delay
            await asyncio.sleep(5)
            
            # Swap the adapter in the active scanner
            self._current_job = replace(self._current_job, status="swapping")
            logger.info("[%s] Training complete. Hot-swapping adapter.", job_id)
            
            # We pass the new adapter path to the scanner
            try:
                self.scanner.reload_adapter(adapter_path)
            except Exception as swap_err:
                logger.warning("[%s] Adapter swap failed: %s", job_id, swap_err)
            
            # Reset pipeline count
            self.pipeline.reset_count()
            
            self._current_job = replace(
                self._current_job, 
                status="complete", 
                completed_at=datetime.now(timezone.utc).isoformat()
            )
            logger.info("[%s] Retrain cycle complete.", job_id)
            
        except Exception as exc:
            logger.error("[%s] Retrain cycle failed: %s", job_id, exc, exc_info=True)
            self._current_job = replace(
                self._current_job, 
                status="failed", 
                error=str(exc),
                completed_at=datetime.now(timezone.utc).isoformat()
            )
