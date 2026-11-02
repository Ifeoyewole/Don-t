"""Build family-grouped research manifests from frozen external dataset scope."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath

from google.cloud import storage


UNIQUE_STATUS = "UNIQUE_TO_BASELINE"
JOINT_LABELS = {
    "OPEN_JOINT", "FAULTY_JOINT", "JOINT_DISPLACEMENT",
    "JOINT_MISALIGNMENT", "DEFORMATION", "RUPTURE", "BROKEN_PIPE",
}
SURFACE_LABELS = {"CORROSION", "SURFACE_DAMAGE"}


def load_gcs_json(client: storage.Client, uri: str) -> dict:
    bucket, name = uri.removeprefix("gs://").split("/", 1)
    return json.loads(client.bucket(bucket).blob(name).download_as_text())


def media_family(original_media_id: str) -> str:
    """Collapse Roboflow augmentation hashes while preserving source identity."""
    value = re.sub(r"\.rf\.[0-9a-f]+$", "", original_media_id, flags=re.IGNORECASE)
    return value.casefold()


def family_split(dataset_name: str, family_id: str) -> str:
    value = int.from_bytes(hashlib.sha256(f"{dataset_name}\0{family_id}".encode()).digest()[:8], "big") % 100
    return "train" if value < 80 else "val" if value < 90 else "test"


def join_gcs(root: str, relative: str) -> str:
    return root.rstrip("/") + "/" + str(PurePosixPath(relative))


def build(scope: dict, client: storage.Client) -> tuple[dict[str, list[dict]], dict]:
    stages = {"representation": [], "joint_detection": [], "surface_condition": []}
    seen_sha: set[str] = set()
    excluded = Counter()
    family_splits: dict[tuple[str, str], str] = {}
    for source in scope["external_sources"]:
        registry = load_gcs_json(client, source["gcs_registry"])
        for row in registry["records"]:
            if row.get("duplicate_status") != UNIQUE_STATUS:
                excluded["not_unique"] += 1
                continue
            digest = row.get("sha256")
            if not digest or digest in seen_sha:
                excluded["missing_or_repeated_sha256"] += 1
                continue
            seen_sha.add(digest)
            family = media_family(row["original_media_id"])
            key = (source["name"], family)
            split = family_splits.setdefault(key, family_split(*key))
            normalized = {
                "dataset_name": source["name"],
                "dataset_version": row["dataset_version"],
                "original_media_id": row["original_media_id"],
                "media_family_id": family,
                "original_split": row["split"],
                "split": split,
                "image_uri": join_gcs(source["gcs_media_root"], row["original_image_path"]),
                "annotation_uri": join_gcs(source["gcs_media_root"], row["original_annotation_path"]),
                "source_labels": row["source_labels"],
                "jointinspect_labels": row["jointinspect_labels"],
                "annotation_type": row["annotation_type"],
                "sha256": digest,
                "dhash": row.get("dhash"),
                "width": row["width"],
                "height": row["height"],
                "training_eligibility": "RESEARCH_CANDIDATE_PENDING_RECORD_REVIEW",
            }
            stages["representation"].append(normalized)
            labels = set(row["jointinspect_labels"])
            if labels & JOINT_LABELS:
                stages["joint_detection"].append(normalized)
            if labels & SURFACE_LABELS:
                stages["surface_condition"].append(normalized)
    for rows in stages.values():
        rows.sort(key=lambda row: (row["split"], row["dataset_name"], row["media_family_id"], row["sha256"]))
    summary = {
        "schema_version": 1,
        "scope_id": scope["scope_id"],
        "status": "RESEARCH_CANDIDATE_PENDING_RECORD_REVIEW",
        "base_dataset": scope["base_dataset"],
        "stage_counts": {name: len(rows) for name, rows in stages.items()},
        "stage_split_counts": {
            name: dict(Counter(row["split"] for row in rows)) for name, rows in stages.items()
        },
        "stage_family_counts": {
            name: len({(row["dataset_name"], row["media_family_id"]) for row in rows})
            for name, rows in stages.items()
        },
        "excluded_counts": dict(excluded),
        "selection_rule": "duplicate_status == UNIQUE_TO_BASELINE and globally unique SHA-256",
        "split_rule": "SHA-256(dataset_name + NUL + media_family_id), 80/10/10",
        "production_eligible": False,
    }
    return stages, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scope = json.loads(args.scope.read_text(encoding="utf-8"))
    stages, summary = build(scope, storage.Client(project=args.project))
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in stages.items():
        with (args.output / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    (args.output / "manifest_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
