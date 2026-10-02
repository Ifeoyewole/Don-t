"""Sewer-ML Benchmark Adapter with Strict Legal Permission Gate.

STATUS: BENCHMARK_PERMISSION_PENDING

STRICT PROHIBITION:
Sewer-ML MUST NOT be used for:
- production training
- fine-tuning
- pretraining
- distillation
- production RAG
- production embeddings
- production model weights
- synthetic-data derivation
until explicit permission/appropriate rights are confirmed.

The adapter refuses execution unless:
    SEWERML_BENCHMARK_PERMISSION=true
is explicitly present in environment variables.
"""

import os
import logging
from pathlib import Path
from typing import Iterator, List
from .base_adapter import BaseDatasetAdapter, BenchmarkSample

logger = logging.getLogger("sewerml_adapter")

SEWERML_STATUS = "BENCHMARK_PERMISSION_PENDING"


class SewerMLAdapter(BaseDatasetAdapter):
    """Adapter for the Sewer-ML multi-defect benchmark dataset."""

    def __init__(self, dataset_root: Path = Path("benchmarks/sewerml")):
        super().__init__(dataset_root=dataset_root, is_benchmark_only=True)
        self.production_eligible = False
        self.commercial_training_allowed = False
        self._samples: List[BenchmarkSample] = []
        self._check_permission()

    def _check_permission(self):
        permission_flag = os.environ.get("SEWERML_BENCHMARK_PERMISSION", "false").strip().lower()
        if permission_flag != "true":
            logger.error(
                "Execution blocked: Sewer-ML benchmark permission is pending. "
                "Set SEWERML_BENCHMARK_PERMISSION=true only after formal legal permission has been confirmed."
            )
            raise PermissionError(
                "Sewer-ML permission is pending (STATUS: BENCHMARK_PERMISSION_PENDING). "
                "Cannot access or iterate Sewer-ML images."
            )

    @property
    def dataset_name(self) -> str:
        return "Sewer-ML-Benchmark"

    @property
    def license_name(self) -> str:
        return "Sewer-ML-Research-Only (Permission Pending)"

    def load(self) -> None:
        self._check_permission()
        # Placeholder for read-only benchmark iteration when permission is granted
        self._samples.clear()
        logger.info("Sewer-ML benchmark initialized under permission-cleared mode.")

    def __len__(self) -> int:
        return len(self._samples)

    def __iter__(self) -> Iterator[BenchmarkSample]:
        self._check_permission()
        return iter(self._samples)
