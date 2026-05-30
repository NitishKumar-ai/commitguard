"""Tests for commitguard_env.self_trainer — L4 self-training trigger."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from commitguard_env.self_trainer import SelfTrainer


@pytest.mark.asyncio
async def test_trigger_retrain_creates_job() -> None:
    mock_pipeline = MagicMock()
    mock_pipeline.get_new_examples_count.return_value = 550
    mock_scanner = MagicMock()
    
    trainer = SelfTrainer(pipeline=mock_pipeline, scanner=mock_scanner)
    
    job = await trainer.trigger_retrain()
    
    assert job is not None
    assert job.status in {"pending", "training", "swapping", "complete"}
    assert job.new_examples_count == 550
    mock_pipeline.flush_to_gcs.assert_called_once()
