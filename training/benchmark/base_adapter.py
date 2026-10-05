"""Base Dataset Adapter for Benchmark Evaluation.

Enforces strict isolation between benchmark datasets and production training pipelines:
1. Benchmark adapters are strictly read-only.
2. Production eligibility returns False by default for all external benchmarks.
3. Weights, gradients, and distillation pipelines can never access benchmark adapter data.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from pydantic import BaseModel


class BenchmarkSample(BaseModel):
    sample_id: str
    image_path: str
    condition_label: Optional[str] = None
    mask_path: Optional[str] = None
    bbox_xyxy: Optional[List[float]] = None
    ground_truth_gap_mm: Optional[float] = None
    metadata: Dict[str, Any] = {}


class BaseDatasetAdapter(ABC):
    """Abstract base class for benchmark dataset ingestion and iteration."""

    def __init__(self, dataset_root: Path, is_benchmark_only: bool = True):
        self.dataset_root = Path(dataset_root)
        self.is_benchmark_only = is_benchmark_only
        self.production_eligible = False  # Strictly False for external benchmarks

    @property
    @abstractmethod
    def dataset_name(self) -> str:
        """Name of the benchmark dataset."""
        pass

    @property
    @abstractmethod
    def license_name(self) -> str:
        """License governing the benchmark."""
        pass

    @abstractmethod
    def load(self) -> None:
        """Loads dataset index and validates integrity."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        pass

    @abstractmethod
    def __iter__(self) -> Iterator[BenchmarkSample]:
        pass
