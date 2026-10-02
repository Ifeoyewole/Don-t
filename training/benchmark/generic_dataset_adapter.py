"""Generic Dataset Adapter for Frozen Evaluation.

Allows evaluating frozen production models on arbitrary standard format evaluation datasets
(COCO, Pascal VOC, or JointInspect JSON manifest).
"""

import json
import logging
from pathlib import Path
from typing import Iterator, List
from .base_adapter import BaseDatasetAdapter, BenchmarkSample

logger = logging.getLogger("generic_adapter")


class GenericDatasetAdapter(BaseDatasetAdapter):
    """Adapter for generic evaluation directories containing images and JSON metadata."""

    def __init__(self, dataset_root: Path, name: str = "GenericBenchmark", license_name: str = "EvaluationOnly"):
        super().__init__(dataset_root=dataset_root, is_benchmark_only=True)
        self._name = name
        self._license = license_name
        self._samples: List[BenchmarkSample] = []
        self.load()

    @property
    def dataset_name(self) -> str:
        return self._name

    @property
    def license_name(self) -> str:
        return self._license

    def load(self) -> None:
        self._samples.clear()
        if not self.dataset_root.exists():
            logger.warning("Dataset root does not exist: %s", self.dataset_root)
            return

        json_files = sorted(list(self.dataset_root.glob("*.json")))
        for jf in json_files:
            if jf.name.startswith("manifest") or jf.name.endswith("validation.json"):
                continue
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                sid = meta.get("sample_id", jf.stem)
                files = meta.get("files", {})
                img_p = str(self.dataset_root / files.get("rgb_image", f"{sid}.png"))
                mask_p = str(self.dataset_root / files.get("segmentation_mask", f"{sid}_mask.png"))

                sample = BenchmarkSample(
                    sample_id=sid,
                    image_path=img_p,
                    condition_label=meta.get("condition"),
                    mask_path=mask_p if Path(mask_p).exists() else None,
                    bbox_xyxy=meta.get("bbox_xyxy"),
                    ground_truth_gap_mm=meta.get("gap_mm"),
                    metadata=meta,
                )
                self._samples.append(sample)
            except Exception as e:
                logger.warning("Error parsing sample %s: %s", jf, e)

        logger.info("GenericDatasetAdapter '%s' loaded %d benchmark samples.", self._name, len(self._samples))

    def __len__(self) -> int:
        return len(self._samples)

    def __iter__(self) -> Iterator[BenchmarkSample]:
        return iter(self._samples)
