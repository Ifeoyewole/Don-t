import csv
import json
import os
import subprocess
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from google.cloud import storage

def extract_and_organize():
    bucket_name = "joint-inspection-510310-data"
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    print("=== Loading Curated Wanted Filenames from GCS ===")
    wanted_blob = bucket.blob("datasets/sewer-ml/manifests/curated_wanted_images.txt")
    wanted_lines = wanted_blob.download_as_text().splitlines()
    wanted_set = set(line.strip() for line in wanted_lines if line.strip())
    print(f"Total wanted curated images across splits: {len(wanted_set)}")

    # Load curated annotations to categorize
    train_blob = bucket.blob("datasets/sewer-ml/splits/train/curated_train.csv")
    train_blob.download_to_filename("/tmp/curated_train.csv")
    val_blob = bucket.blob("datasets/sewer-ml/splits/validation/curated_val.csv")
    val_blob.download_to_filename("/tmp/curated_val.csv")

    meta_by_filename = {}
    for csv_file in ["/tmp/curated_train.csv", "/tmp/curated_val.csv"]:
        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                meta_by_filename[row["Filename"]] = row

    password = os.environ.get("SEWER_PASSWORD", "").strip()
    base_url = "https://sciencedata.dk/public/Large%20AAU%20files/Sewer_ML"

    os.makedirs("/tmp/extracted", exist_ok=True)
    os.makedirs("/tmp/curated_subsets", exist_ok=True)

    total_extracted = 0

    # We process valid00.zip and train00.zip
    archives_to_process = ["valid00.zip", "train00.zip"]

    for arch in archives_to_process:
        zip_path = f"/tmp/{arch}"
        print(f"--- Downloading {arch} via curl from Sewer-ML ---")
        curl_cmd = [
            "curl", "--location-trusted",
            "-u", f"operator:{password}",
            "-f", "-s", "-S",
            "-o", zip_path,
            f"{base_url}/{arch}"
        ]
        ret = subprocess.run(curl_cmd, check=True)
        size_gb = os.path.getsize(zip_path) / (1024 ** 3)
        print(f"Successfully downloaded {arch} ({size_gb:.2f} GB)")

        print(f"Extracting wanted files from {arch}...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            arch_namelist = set(zf.namelist())
            matching = [f for f in wanted_set if f in arch_namelist]
            print(f"Found {len(matching)} wanted files in {arch}.")
            for f in matching:
                zf.extract(f, path="/tmp/extracted")
                total_extracted += 1

        print(f"Removing {arch} to reclaim temporary disk space...")
        os.remove(zip_path)

    print(f"Total files extracted locally: {total_extracted}")

    extracted_files = [f for f in os.listdir("/tmp/extracted") if f.endswith(".png")]
    print(f"Found {len(extracted_files)} images to upload to GCS.")

    def upload_image(fname):
        local_p = os.path.join("/tmp/extracted", fname)
        blob = bucket.blob(f"datasets/sewer-ml/curated/images/{fname}")
        blob.upload_from_filename(local_p, content_type="image/png")
        return fname

    print("Uploading images in parallel with 32 workers...")
    uploaded_count = 0
    with ThreadPoolExecutor(max_workers=32) as executor:
        for _ in executor.map(upload_image, extracted_files):
            uploaded_count += 1
            if uploaded_count % 500 == 0:
                print(f"Uploaded {uploaded_count}/{len(extracted_files)} images...")

    print(f"Uploaded all {uploaded_count} images successfully to GCS.")

    # Build category manifests for curated/ subdirectories
    category_buckets = {
        "displacement": [],
        "joint-related": [],
        "cracks-and-fractures": [],
        "deformation": [],
        "roots-and-deposits": [],
        "normal": [],
        "difficult-scenes": [],
        "negatives": [],
    }

    fieldnames = ["Filename", "GCS_URI", "WaterLevel", "VA", "RB", "OB", "PF", "DE", "FS", "IS", "RO", "IN", "AF", "BE", "FO", "GR", "PH", "PB", "OS", "OP", "OK", "ND", "Defect", "Split"]

    for fname in extracted_files:
        row = meta_by_filename.get(fname)
        if not row:
            continue
        row_with_uri = dict(row)
        row_with_uri["GCS_URI"] = f"gs://{bucket_name}/datasets/sewer-ml/curated/images/{fname}"

        # Categorize
        if row.get("FS") in ("1", "1.0"):
            category_buckets["displacement"].append(row_with_uri)
            category_buckets["joint-related"].append(row_with_uri)
        if row.get("IS") in ("1", "1.0"):
            category_buckets["joint-related"].append(row_with_uri)
        if row.get("RB") in ("1", "1.0"):
            category_buckets["cracks-and-fractures"].append(row_with_uri)
        if row.get("DE") in ("1", "1.0"):
            category_buckets["deformation"].append(row_with_uri)
        if any(row.get(d) in ("1", "1.0") for d in ("RO", "AF", "BE", "FO")):
            category_buckets["roots-and-deposits"].append(row_with_uri)
            category_buckets["negatives"].append(row_with_uri)
        if row.get("ND") in ("1", "1.0"):
            category_buckets["normal"].append(row_with_uri)

        active_cnt = sum(1 for k in ["VA", "RB", "OB", "PF", "DE", "FS", "IS", "RO", "IN", "AF", "BE", "FO", "GR"] if row.get(k) in ("1", "1.0"))
        if active_cnt >= 2:
            category_buckets["difficult-scenes"].append(row_with_uri)

    # Write manifests to GCS
    for cat, rows in category_buckets.items():
        cat_csv_path = f"/tmp/curated_subsets/{cat}_manifest.csv"
        with open(cat_csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        blob = bucket.blob(f"datasets/sewer-ml/curated/{cat}/manifest.csv")
        blob.upload_from_filename(cat_csv_path)
        print(f"Uploaded {len(rows)} records for category '{cat}' to datasets/sewer-ml/curated/{cat}/manifest.csv")

    # Generate curation quality report
    curation_report = {
        "status": "CURATION_COMPLETE",
        "total_extracted_images": len(extracted_files),
        "source_archives_processed": archives_to_process,
        "gcs_image_root": f"gs://{bucket_name}/datasets/sewer-ml/curated/images/",
        "category_counts": {k: len(v) for k, v in category_buckets.items()},
        "zero_pc_downloads": True,
        "ephemeral_disk_reclaimed": True
    }
    bucket.blob("datasets/sewer-ml/quality-reports/curation_report.json").upload_from_string(
        json.dumps(curation_report, indent=2), content_type="application/json"
    )
    print("Curation quality report uploaded to quality-reports/curation_report.json")
    print("=== Phase 4 High-Value Curation Complete ===")

if __name__ == "__main__":
    extract_and_organize()
