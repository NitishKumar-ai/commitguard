"""CommitGuard v3 L3 Auto-Documentation Pipeline.

Converts VerifiedFinding objects into structured TrainingPair objects
and persists them to GCS for continuous self-training.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .models import TrainingPair, VerifiedFinding

logger = logging.getLogger(__name__)


class TrainingDataPipeline:
    """Manages creation and storage of training data from verified findings."""

    def __init__(
        self,
        gcs_bucket: str = "commitguard",
        gcs_prefix: str = "verified_findings/",
        local_buffer_dir: str | Path = "data/buffer",
    ) -> None:
        self.gcs_bucket = gcs_bucket
        self.gcs_prefix = gcs_prefix
        self.local_buffer_dir = Path(local_buffer_dir)
        self.local_buffer_dir.mkdir(parents=True, exist_ok=True)
        self.buffer_file = self.local_buffer_dir / "current_buffer.jsonl"
        self._new_examples_count = 0

    def document(self, verified: VerifiedFinding, repo_url: str, commit_sha: str) -> TrainingPair:
        """Convert a VerifiedFinding into a TrainingPair and append to local buffer."""
        pair = TrainingPair(
            code=verified.finding.code_snippet,
            cwe_id=verified.finding.cwe_id,
            cwe_name=verified.finding.cwe_name,
            verdict=verified.verdict,
            exploit_code=verified.exploit_code,
            exploit_output=verified.exploit_output,
            suggested_fix=verified.finding.suggested_fix,
            repo_url=repo_url,
            commit_sha=commit_sha,
            file_path=verified.finding.file,
            line_start=verified.finding.line_start,
            line_end=verified.finding.line_end,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Append to local buffer
        with self.buffer_file.open("a", encoding="utf-8") as f:
            from dataclasses import asdict
            f.write(json.dumps(asdict(pair)) + "\n")
            
        self._new_examples_count += 1
        logger.info("Documented training pair for %s (total new: %d)", pair.cwe_id, self._new_examples_count)
        return pair

    def document_batch(self, verified_findings: list[VerifiedFinding], repo_url: str, commit_sha: str) -> list[TrainingPair]:
        """Document a batch of verified findings."""
        pairs = []
        for verified in verified_findings:
            pairs.append(self.document(verified, repo_url, commit_sha))
        return pairs

    def get_new_examples_count(self) -> int:
        """Return the number of new examples documented since the last retrain."""
        return self._new_examples_count

    def reset_count(self) -> None:
        """Reset the new examples count (called by L4 after a retrain)."""
        self._new_examples_count = 0

    def flush_to_gcs(self) -> int:
        """Upload the current buffer to GCS and clear it. Returns the number of items flushed."""
        if not self.buffer_file.exists() or self.buffer_file.stat().st_size == 0:
            return 0

        # Count lines for logging
        with self.buffer_file.open("r", encoding="utf-8") as f:
            count = sum(1 for _ in f)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        gcs_path = f"{self.gcs_prefix}batch_{timestamp}.jsonl"
        
        try:
            self._upload_jsonl(self.buffer_file, gcs_path)
            logger.info("Flushed %d examples to gs://%s/%s", count, self.gcs_bucket, gcs_path)
            # Clear buffer after successful upload
            self.buffer_file.unlink()
            return count
        except Exception as exc:
            logger.error("Failed to flush training data to GCS: %s", exc)
            return 0

    def _upload_jsonl(self, local_path: Path, gcs_path: str) -> None:
        """Upload a local file to GCS."""
        try:
            from google.cloud import storage
        except ImportError:
            logger.warning("google-cloud-storage not installed. Skipping GCS upload (local mode).")
            return
            
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set. Skipping GCS upload (local mode).")
            return

        client = storage.Client()
        bucket = client.bucket(self.gcs_bucket)
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(str(local_path))
