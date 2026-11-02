"""Versioned, traceable canonical-label resolution for external datasets."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data_sources" / "canonical_labels.json"


def normalize_source_label(label: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", label.strip().lower())).strip("_")


@dataclass(frozen=True)
class LabelResolution:
    dataset_name: str
    source_label: str
    normalized_source_label: str
    jointinspect_label: str
    mapping_version: str
    mapping_scope: str

    def to_dict(self) -> dict:
        return asdict(self)


class CanonicalLabelRegistry:
    def __init__(self, path: Path = REGISTRY_PATH):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.labels = frozenset(self.data["canonical_labels"])
        self._validate()

    def _validate(self) -> None:
        if self.data.get("fallback") not in self.labels:
            raise ValueError("Canonical-label fallback is not registered")
        mapped = list(self.data.get("aliases", {}).values())
        for mappings in self.data.get("dataset_mappings", {}).values():
            mapped.extend(mappings.values())
        unknown = set(mapped) - self.labels
        if unknown:
            raise ValueError(f"Mappings reference unknown canonical labels: {sorted(unknown)}")

    def resolve(self, dataset_name: str, source_label: str) -> LabelResolution:
        dataset_mapping = self.data.get("dataset_mappings", {}).get(dataset_name, {})
        if source_label in dataset_mapping:
            canonical = dataset_mapping[source_label]
            scope = "dataset"
        else:
            normalized = normalize_source_label(source_label)
            canonical = self.data.get("aliases", {}).get(normalized, self.data["fallback"])
            scope = "alias" if normalized in self.data.get("aliases", {}) else "fallback"
        return LabelResolution(
            dataset_name=dataset_name,
            source_label=source_label,
            normalized_source_label=normalize_source_label(source_label),
            jointinspect_label=canonical,
            mapping_version=self.data["schema_version"],
            mapping_scope=scope,
        )


registry = CanonicalLabelRegistry()
