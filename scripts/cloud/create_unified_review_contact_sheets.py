"""Cloud-only CCTV review contact sheets with verified, source-specific GCS paths.

Reads one existing local worklist stored in GCS plus the two publisher-
quarantined import registries. Never invents ROIs, verified source families,
adjudicated labels or commercial rights. No Gemini or GPU invocation.

Run through scripts/cloud/cloudbuild-unified-review-contact-sheets.yaml.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from csv import DictReader, DictWriter
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import PurePosixPath
import re
from typing import Any, Mapping

BUCKET = "joint-inspection-510310-data"
BASE = f"gs://{BUCKET}"
SOURCE_PREFIXES = {
    "Sewer Defects Public": (
        "datasets/quarantine/roboflow/sewage-defect-detection-s68df/"
        "sewer-defects-u8zwz/v1/"
    ),
    "Pipeline CCTV Defect Public": (
        "datasets/quarantine/roboflow/kyle-scally-4ixoi/"
        "pipeline-cctv-defect/v1/"
    ),
}
MAX_WORKLIST_BYTES = 2 * 1024 * 1024
MAX_REGISTRY_BYTES = 20 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_ROWS = 100
PAGE_SLOTS = 20
FAMILY_RE = re.compile(r"^([A-Za-z0-9_-]+)_f[0-9]+(?:_|$)")


def checked_uri(uri: str) -> str:
    if not isinstance(uri, str) or not uri.startswith(BASE + "/"):
        raise ValueError("Expected a project-bucket GCS URI")
    name = uri[len(BASE) + 1:]
    if (not name or len(name) > 1024 or "\\" in name or "?" in name or "#" in name
            or any(p in ("", ".", "..") for p in name.split("/"))
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError("Invalid GCS object path")
    return name


def checked_relative_path(raw: str) -> str:
    """Registry paths can include spaces but must never escape archive root."""
    if not isinstance(raw, str) or not raw or raw.startswith("/") or "\\" in raw:
        raise ValueError("Invalid relative media path")
    parts = raw.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Unsafe relative media path")
    if any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise ValueError("Unsafe media path control character")
    return "/".join(parts)


def expected_archive_suffix(registry: Mapping[str, Any], original_path: str) -> str:
    source_root = registry.get("source_root_within_extracted_archive", "")
    if source_root in ("", "."):
        suffix = "extracted/" + checked_relative_path(original_path)
    else:
        suffix = (
            "extracted/" + checked_relative_path(source_root)
            + "/" + checked_relative_path(original_path)
        )
    return suffix


def find_verified_object_name(
    registry: Mapping[str, Any],
    row: Mapping[str, str],
    *,
    prefix: str,
    available_names: list[str],
) -> str | None:
    """Metadata-only exact path match; ambiguous roots are NOT guessed."""
    if registry.get("commercial_training_eligible") is not False:
        raise ValueError("Review resolver accepts quarantined registries only")
    image_path = checked_relative_path(row["source_image_path"])
    sha = row["image_sha256"]
    record_match = any(
        item.get("original_image_path") == image_path
        and item.get("sha256") == sha
        for item in registry.get("records", [])
        if isinstance(item, dict)
    )
    if not record_match:
        return None
    suffix = expected_archive_suffix(registry, image_path)
    candidates = [
        name for name in available_names
        if name.startswith(prefix) and (
            name == prefix + suffix
            or name.endswith("/" + suffix)
        )
    ]
    return candidates[0] if len(candidates) == 1 else None


def tentative_family(source_media_id: str) -> str | None:
    """Hint only. Neither a verified video ID nor a split assignment."""
    if not isinstance(source_media_id, str):
        return None
    match = FAMILY_RE.match(source_media_id)
    return match.group(1) if match else None


def _download(client: Any, object_name: str, *, limit: int) -> bytes:
    blob = client.bucket(BUCKET).blob(object_name)
    blob.reload()
    if blob.size is None or blob.size > limit:
        raise ValueError("Cloud object exceeds bounded review input")
    return blob.download_as_bytes(if_generation_match=blob.generation)


def _write_new(client: Any, object_name: str, content: bytes, media_type: str) -> None:
    client.bucket(BUCKET).blob(object_name).upload_from_string(
        content, content_type=media_type, if_generation_match=0
    )


def _thumbnail(image_bytes: bytes):
    from PIL import Image, ImageOps
    with Image.open(BytesIO(image_bytes)) as opened:
        if (opened.width < 24 or opened.height < 24
                or opened.width * opened.height > MAX_IMAGE_PIXELS):
            raise ValueError("Unusable or oversized image dimensions")
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image.thumbnail((250, 172))
    return image


def make_pages(
    verified: list[dict[str, Any]],
    thumbnails: dict[str, Any],
) -> list[bytes]:
    """Render private, annotated review grids; annotations are NOT ground truth."""
    from PIL import Image, ImageDraw
    pages = []
    for start in range(0, len(verified), PAGE_SLOTS):
        batch = verified[start:start + PAGE_SLOTS]
        sheet = Image.new("RGB", (1100, 1190), "white")
        draw = ImageDraw.Draw(sheet)
        draw.text((18, 14), "JointInspect CCTV quarantine review | unverified labels",
                  fill="black")
        for index, item in enumerate(batch):
            col, line = index % 4, index // 4
            x, y = col * 275 + 12, line * 230 + 43
            thumb = thumbnails[item["image_sha256"]]
            px = x + (250 - thumb.width) // 2
            py = y + (172 - thumb.height) // 2
            sheet.paste(thumb, (px, py))
            draw.rectangle((x, y, x + 250, y + 172), outline="#909090", width=1)
            family = item.get("family_hint") or "UNKNOWN_SEQUENCE"
            bucket = item["candidate_bucket"].replace("_CANDIDATE_UNVERIFIED", "")
            draw.text((x, y + 178), f"{start + index + 1}. {bucket[:29]}", fill="black")
            draw.text((x, y + 194), f"Family hint: {family[:28]}", fill="#333333")
            draw.text((x, y + 210), item["image_sha256"][:20], fill="#555555")
        b = BytesIO()
        sheet.save(b, format="JPEG", quality=85, optimize=True)
        pages.append(b.getvalue())
    return pages


def generate(client: Any, *, worklist_uri: str, output_prefix_uri: str) -> dict[str, Any]:
    worklist_key = checked_uri(worklist_uri)
    output_key = checked_uri(output_prefix_uri + "/marker.json")[:-len("/marker.json")]
    worklist_bytes = _download(client, worklist_key, limit=MAX_WORKLIST_BYTES)
    worklist_text = worklist_bytes.decode("utf-8-sig")
    reader = DictReader(StringIO(worklist_text))
    if not reader.fieldnames or "image_sha256" not in reader.fieldnames:
        raise ValueError("Worklist CSV missing expected fields")
    worklist = list(reader)
    if not 1 <= len(worklist) <= MAX_ROWS:
        raise ValueError("Expected a bounded 1–100-row review worklist")
    registries: dict[str, dict[str, Any]] = {}
    available: dict[str, list[str]] = {}
    for name, prefix in SOURCE_PREFIXES.items():
        registry_bytes = _download(client, prefix + "dataset_registry.json",
                                   limit=MAX_REGISTRY_BYTES)
        registry = json.loads(registry_bytes)
        if registry.get("dataset_name") != name:
            raise ValueError("Registry dataset name did not match source prefix")
        registries[name] = registry
        available[name] = [
            item.name for item in client.list_blobs(BUCKET, prefix=prefix)
        ]

    verified = []
    thumbnails = {}
    errors = []
    seen_sha = set()
    for i, row in enumerate(worklist):
        digest = row.get("image_sha256", "")
        dataset = row.get("dataset_name", "")
        if (not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest)
                or digest in seen_sha or dataset not in registries):
            errors.append({"row": i + 1, "reason": "INVALID_OR_DUPLICATE_RECORD"})
            continue
        seen_sha.add(digest)
        try:
            path = find_verified_object_name(
                registries[dataset], row,
                prefix=SOURCE_PREFIXES[dataset], available_names=available[dataset],
            )
            if path is None:
                errors.append({"row": i + 1, "reason": "SOURCE_OBJECT_NOT_UNIQUELY_RESOLVED"})
                continue
            data = _download(client, path, limit=MAX_IMAGE_BYTES)
            if hashlib.sha256(data).hexdigest() != digest:
                errors.append({"row": i + 1, "reason": "SOURCE_OBJECT_HASH_MISMATCH"})
                continue
            image = _thumbnail(data)
            item = dict(row)
            item["image_uri_TO_VERIFY"] = BASE + "/" + path
            # This is a source-object SHA verification, not annotation or family review.
            item["review_status"] = "NEEDS_HUMAN_REVIEW"
            item["family_hint"] = tentative_family(row.get("source_media_id", ""))
            item["source_family_TO_VERIFY"] = ""
            item["roi_x0"] = item["roi_y0"] = ""
            item["roi_x1"] = item["roi_y1"] = ""
            item["geometry_TO_REVIEW"] = ""
            verified.append(item)
            thumbnails[digest] = image
        except (OSError, ValueError, KeyError) as exc:
            errors.append({"row": i + 1, "reason": type(exc).__name__})

    if not verified:
        raise ValueError("No source objects verified; not publishing empty review output")
    pages = make_pages(verified, thumbnails)
    columns = list(reader.fieldnames)
    out_csv = StringIO()
    writer = DictWriter(out_csv, fieldnames=columns)
    writer.writeheader()
    writer.writerows([{key: item.get(key, "") for key in columns} for item in verified])
    summary = {
        "schema_version": "1.0",
        "status": "REVIEW_PREVIEW_READY",
        "worklist_count": len(worklist),
        "sha256_verified_image_count": len(verified),
        "unresolved_count": len(errors),
        "unresolved": errors,
        "family_hints_not_ground_truth": dict(sorted(Counter(
            v["family_hint"] or "UNRESOLVED" for v in verified
        ).items())),
        "candidate_counts": dict(sorted(Counter(
            v["candidate_bucket"] for v in verified
        ).items())),
        "pages": [BASE + "/" + output_key + f"/contact-sheet-{i+1:02d}.jpg"
                  for i in range(len(pages))],
        "review_worklist_uri": BASE + "/" + output_key + "/review-worklist-verified.csv",
        "research_only": True,
        "annotation_audit_complete": False,
        "commercial_training_eligible": False,
        "note": (
            "Source GCS path and bytes hash verified for preview only. Family hints are "
            "unverified; source labels, ROIs, rights provenance and defect identities "
            "still require independent human review. No model inference or training."
        ),
    }
    # Create-only objects. A rerun must choose another output prefix.
    for i, binary in enumerate(pages, 1):
        _write_new(client, output_key + f"/contact-sheet-{i:02d}.jpg",
                   binary, "image/jpeg")
    _write_new(client, output_key + "/review-worklist-verified.csv",
               out_csv.getvalue().encode("utf-8-sig"), "text/csv")
    _write_new(client, output_key + "/summary.json",
               (json.dumps(summary, indent=2) + "\n").encode("utf-8"), "application/json")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="joint-inspection-510310")
    parser.add_argument("--worklist-uri", required=True)
    parser.add_argument("--output-prefix", required=True)
    args = parser.parse_args()
    from google.cloud import storage
    result = generate(storage.Client(project=args.project),
                      worklist_uri=args.worklist_uri,
                      output_prefix_uri=args.output_prefix)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("family_hints_not_ground_truth", "unresolved")},
                     indent=2))


if __name__ == "__main__":
    main()
