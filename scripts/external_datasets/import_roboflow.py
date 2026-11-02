"""Download a pinned Roboflow export and build a quarantined dataset registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml
from google.cloud import secretmanager, storage
from PIL import Image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
def dhash(path: Path, size: int = 8) -> str:
    with Image.open(path) as image:
        gray = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
        pixels = list(gray.getdata())
    value = 0
    for row in range(size):
        offset = row * (size + 1)
        for column in range(size):
            value = (value << 1) | int(pixels[offset + column + 1] > pixels[offset + column])
    return f"{value:016x}"


def nearest_hamming(value: str, candidates: set[str], maximum: int = 4) -> int | None:
    number, best = int(value, 16), None
    for candidate in candidates:
        distance = (number ^ int(candidate, 16)).bit_count()
        if distance <= maximum and (best is None or distance < best):
            best = distance
            if best == 0:
                break
    return best


class HammingIndex:
    """BK-tree index for bounded Hamming searches over 64-bit perceptual hashes."""

    def __init__(self, values: set[str] = frozenset()):
        self.root: list | None = None
        for value in values:
            self.add(value)

    def add(self, value: str) -> None:
        number = int(value, 16)
        if self.root is None:
            self.root = [number, {}]
            return
        node = self.root
        while True:
            distance = (number ^ node[0]).bit_count()
            if distance == 0:
                return
            child = node[1].get(distance)
            if child is None:
                node[1][distance] = [number, {}]
                return
            node = child

    def nearest(self, value: str, maximum: int = 4) -> int | None:
        if self.root is None:
            return None
        number, best, stack = int(value, 16), None, [self.root]
        while stack:
            node = stack.pop()
            distance = (number ^ node[0]).bit_count()
            if distance <= maximum and (best is None or distance < best):
                best = distance
                if best == 0:
                    return 0
            radius = maximum if best is None else min(maximum, best - 1)
            stack.extend(child for edge, child in node[1].items()
                         if distance - radius <= edge <= distance + radius)
        return best


def read_baselines(client: storage.Client, uris: list[str]) -> tuple[set[str], set[str]]:
    sha256, perceptual = set(), set()
    for uri in uris:
        bucket, name = uri.removeprefix("gs://").split("/", 1)
        manifest = json.loads(client.bucket(bucket).blob(name).download_as_text())
        for row in manifest["records"]:
            if row.get("sha256"):
                sha256.add(row["sha256"])
            if row.get("dhash"):
                perceptual.add(row["dhash"])
    return sha256, perceptual


def safe_extract(archive: Path, output: Path) -> None:
    output_resolved = output.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (output / member.filename).resolve()
            if output_resolved not in target.parents and target != output_resolved:
                raise RuntimeError(f"Unsafe ZIP member: {member.filename}")
        bundle.extractall(output)


def download_export(project: str, workspace: str, version: int, export_format: str,
                    api_key: str, archive: Path) -> dict:
    endpoint = f"https://api.roboflow.com/{workspace}/{project}/{version}/{export_format}"
    response = requests.get(endpoint, params={"api_key": api_key, "nocache": "true"}, timeout=120)
    response.raise_for_status()
    metadata = response.json()
    link = metadata["export"]["link"]
    with requests.get(link, stream=True, timeout=300) as export:
        export.raise_for_status()
        with archive.open("wb") as handle:
            for chunk in export.iter_content(1024 * 1024):
                handle.write(chunk)
    return {
        "format": metadata["export"].get("format", export_format),
        "size": metadata["export"].get("size"),
        "download_host": urllib.parse.urlsplit(link).hostname,
    }


def find_dataset_root(output: Path) -> Path:
    candidates = list(output.rglob("data.yaml"))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one data.yaml, found {len(candidates)}")
    return candidates[0].parent


def class_names(config: dict) -> list[str]:
    names = config["names"]
    if isinstance(names, dict):
        return [names[index] if index in names else names[str(index)] for index in range(len(names))]
    return names


def build_manifest(root: Path, dataset_name: str, workspace: str, project: str, version: int,
                   license_name: str, label_map: dict[str, str], baseline_sha: set[str],
                   baseline_dhash: set[str]) -> dict:
    config = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))
    classes = class_names(config)
    records, local_sha, local_dhash = [], set(), set()
    similarity_index = HammingIndex(baseline_dhash)
    for split in ("train", "valid", "test"):
        image_root = root / split / "images"
        label_root = root / split / "labels"
        for image_path in sorted(p for p in image_root.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES):
            label_path = label_root / f"{image_path.stem}.txt"
            if not label_path.is_file():
                raise RuntimeError(f"Missing annotation for {image_path.name}")
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            perceptual = dhash(image_path)
            if digest in local_sha:
                status, distance = "EXACT_SHA256_INTRA_SOURCE", 0
            elif digest in baseline_sha:
                status, distance = "EXACT_SHA256_BASELINE", 0
            elif perceptual in local_dhash:
                status, distance = "EXACT_DHASH_INTRA_SOURCE", 0
            elif perceptual in baseline_dhash:
                status, distance = "EXACT_DHASH_BASELINE", 0
            else:
                distance = similarity_index.nearest(perceptual)
                status = "NEAR_DHASH_EXISTING" if distance is not None else "UNIQUE_TO_BASELINE"
            local_sha.add(digest)
            local_dhash.add(perceptual)
            similarity_index.add(perceptual)
            source_labels = sorted({classes[int(line.split()[0])] for line in label_path.read_text().splitlines() if line.strip()})
            canonical = sorted({label_map.get(label, "GEOMETRY_UNCERTAIN") for label in source_labels})
            with Image.open(image_path) as image:
                width, height = image.size
            records.append({
                "dataset_name": dataset_name,
                "dataset_version": str(version),
                "source": f"https://universe.roboflow.com/{workspace}/{project}",
                "license": license_name,
                "original_media_id": image_path.stem,
                "original_image_path": str(image_path.relative_to(root)),
                "original_annotation_path": str(label_path.relative_to(root)),
                "source_labels": source_labels,
                "jointinspect_labels": canonical,
                "sha256": digest,
                "dhash": perceptual,
                "split": "val" if split == "valid" else split,
                "annotation_type": "YOLO_BOUNDING_BOX",
                "width": width,
                "height": height,
                "date_imported": datetime.now(timezone.utc).isoformat(),
                "duplicate_status": status,
                "near_duplicate_hamming_distance": distance,
                "training_eligibility": "QUARANTINED_PENDING_ANNOTATION_AUDIT",
                "model_experiments": [],
            })
    return {
        "schema_version": 1,
        "dataset_name": dataset_name,
        "dataset_version": str(version),
        "source": f"https://universe.roboflow.com/{workspace}/{project}",
        "license": license_name,
        "original_classes": classes,
        "record_count": len(records),
        "split_counts": {split: sum(row["split"] == split for row in records) for split in ("train", "val", "test")},
        "duplicate_counts": {status: sum(row["duplicate_status"] == status for row in records)
                             for status in sorted({row["duplicate_status"] for row in records})},
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gcp-project", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--roboflow-project", required=True)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--secret", default="roboflow-api-key")
    parser.add_argument("--license", default="CC BY 4.0")
    parser.add_argument("--baseline-manifest", action="append", required=True)
    parser.add_argument("--label-map-file", type=Path, required=True)
    parser.add_argument("--mapping-name", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    archive = args.output_root / "roboflow-yolov8-export.zip"
    secret_client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{args.gcp_project}/secrets/{args.secret}/versions/latest"
    api_key = secret_client.access_secret_version(request={"name": secret_name}).payload.data.decode().strip()
    try:
        export = download_export(args.roboflow_project, args.workspace, args.version, "yolov8", api_key, archive)
    finally:
        api_key = ""
    extracted = args.output_root / "extracted"
    safe_extract(archive, extracted)
    root = find_dataset_root(extracted)
    client = storage.Client(project=args.gcp_project)
    baseline_sha, baseline_dhash = read_baselines(client, args.baseline_manifest)
    mappings = json.loads(args.label_map_file.read_text(encoding="utf-8"))["dataset_mappings"]
    label_map = mappings[args.mapping_name]
    manifest = build_manifest(root, args.dataset_name, args.workspace, args.roboflow_project,
                              args.version, args.license, label_map, baseline_sha, baseline_dhash)
    manifest["export"] = export
    args.manifest_output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("record_count", "split_counts", "duplicate_counts")}, indent=2))


if __name__ == "__main__":
    main()
