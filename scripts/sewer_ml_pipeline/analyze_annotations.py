import csv
import json
import os
import sys
from collections import Counter
from google.cloud import storage

def analyze_and_curate():
    client = storage.Client()
    bucket_name = "joint-inspection-510310-data"
    bucket = client.bucket(bucket_name)

    print("=== Downloading SewerML_Val.csv and SewerML_Train.csv header from GCS ===")
    val_blob = bucket.blob("datasets/sewer-ml/original-annotations/SewerML_Val.csv")
    val_blob.download_to_filename("/tmp/SewerML_Val.csv")
    print(f"Downloaded SewerML_Val.csv ({os.path.getsize('/tmp/SewerML_Val.csv')} bytes)")

    train_blob = bucket.blob("datasets/sewer-ml/original-annotations/SewerML_Train.csv")
    # Stream or download train csv
    print("Downloading SewerML_Train.csv from GCS...")
    train_blob.download_to_filename("/tmp/SewerML_Train.csv")
    print(f"Downloaded SewerML_Train.csv ({os.path.getsize('/tmp/SewerML_Train.csv')} bytes)")

    defect_columns = ["VA", "RB", "OB", "PF", "DE", "FS", "IS", "RO", "IN", "AF", "BE", "FO", "GR", "PH", "PB", "OS", "OP", "OK", "ND", "Defect"]

    def process_file(csv_path, split_name):
        class_counts = Counter()
        total_rows = 0
        multi_label_count = 0
        records = []

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_rows += 1
                active_labels = [c for c in defect_columns if c not in ("Defect", "ND") and row.get(c) in ("1", "1.0")]
                is_nd = row.get("ND") in ("1", "1.0")
                if len(active_labels) > 1:
                    multi_label_count += 1
                for c in defect_columns:
                    if row.get(c) in ("1", "1.0"):
                        class_counts[c] += 1

                records.append({
                    "Filename": row["Filename"],
                    "WaterLevel": row.get("WaterLevel", "0"),
                    "active_labels": active_labels,
                    "is_nd": is_nd,
                    "split": split_name,
                    "raw_row": row
                })

        return total_rows, class_counts, multi_label_count, records

    print("--- Processing Validation Set ---")
    val_total, val_counts, val_multi, val_records = process_file("/tmp/SewerML_Val.csv", "val")
    print(f"Val Total Rows: {val_total}, Multi-label: {val_multi}")
    print("Val Class Counts:", dict(val_counts))

    print("--- Processing Training Set ---")
    train_total, train_counts, train_multi, train_records = process_file("/tmp/SewerML_Train.csv", "train")
    print(f"Train Total Rows: {train_total}, Multi-label: {train_multi}")
    print("Train Class Counts:", dict(train_counts))

    # Produce complete inventory
    inventory = {
        "dataset_name": "Sewer-ML",
        "description": "Multi-label sewer defect classification dataset",
        "total_train_images": train_total,
        "total_val_images": val_total,
        "train_class_distribution": dict(train_counts),
        "val_class_distribution": dict(val_counts),
        "train_multi_defect_images": train_multi,
        "val_multi_defect_images": val_multi,
        "defect_classes": defect_columns,
        "key_joint_classes": {
            "FS": "Displaced joint (Forskudt samling)",
            "IS": "Intruding seal (Indtrængende samlingsmateriale)",
            "RB": "Broken pipe / fracture (Rørbrud)",
            "DE": "Deformed pipe (Deformation)",
            "ND": "Normal non-defective pipe (Normaltilstand)"
        }
    }

    # Write inventory report to GCS
    inv_blob = bucket.blob("datasets/sewer-ml/quality-reports/sewer_ml_inventory.json")
    inv_blob.upload_from_string(json.dumps(inventory, indent=2), content_type="application/json")
    print("Uploaded inventory to gs://joint-inspection-510310-data/datasets/sewer-ml/quality-reports/sewer_ml_inventory.json")

    # Now select the curated high-value dataset for JointInspect
    # Target: ~5,000 to ~10,000 images covering:
    # 1. Joint defects: FS (all available high-confidence)
    # 2. Intruding seals: IS (all available)
    # 3. Structural damage: RB, DE
    # 4. Obstacles & roots: RO, AF, BE, FO
    # 5. Normal pipe: ND
    # 6. Multi-defect difficult scenes

    # We select from train_records (for training split) and val_records (for validation split)
    def curate_split(records, split_name, targets):
        selected = []
        cur_counts = Counter()

        # Prioritize FS
        for r in records:
            if "FS" in r["active_labels"] and cur_counts["FS"] < targets.get("FS", 1500):
                selected.append(r)
                cur_counts["FS"] += 1

        # Prioritize IS
        for r in records:
            if "IS" in r["active_labels"] and r not in selected and cur_counts["IS"] < targets.get("IS", 500):
                selected.append(r)
                cur_counts["IS"] += 1

        # Prioritize RB & DE
        for r in records:
            if any(l in ("RB", "DE") for l in r["active_labels"]) and r not in selected and cur_counts["RB_DE"] < targets.get("RB_DE", 800):
                selected.append(r)
                cur_counts["RB_DE"] += 1

        # Prioritize Distractors / Obstacles (RO, AF, BE, FO)
        for r in records:
            if any(l in ("RO", "AF", "BE", "FO") for l in r["active_labels"]) and r not in selected and cur_counts["DISTRACTOR"] < targets.get("DISTRACTOR", 600):
                selected.append(r)
                cur_counts["DISTRACTOR"] += 1

        # Prioritize Multi-defect difficult
        for r in records:
            if len(r["active_labels"]) >= 2 and r not in selected and cur_counts["MULTI"] < targets.get("MULTI", 600):
                selected.append(r)
                cur_counts["MULTI"] += 1

        # Prioritize Normal (ND)
        for r in records:
            if r["is_nd"] and r not in selected and cur_counts["ND"] < targets.get("ND", 1000):
                selected.append(r)
                cur_counts["ND"] += 1

        return selected, cur_counts

    train_targets = {"FS": 2000, "IS": 600, "RB_DE": 1000, "DISTRACTOR": 800, "MULTI": 800, "ND": 1500}
    val_targets = {"FS": 500, "IS": 150, "RB_DE": 250, "DISTRACTOR": 200, "MULTI": 200, "ND": 400}

    curated_train, cur_train_counts = curate_split(train_records, "train", train_targets)
    curated_val, cur_val_counts = curate_split(val_records, "val", val_targets)

    print(f"Curated Train set: {len(curated_train)} images. Distribution: {dict(cur_train_counts)}")
    print(f"Curated Val set: {len(curated_val)} images. Distribution: {dict(cur_val_counts)}")

    # Write curated split CSVs to GCS
    def export_curated_csv(records, gcs_path):
        out_path = f"/tmp/{os.path.basename(gcs_path)}"
        with open(out_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Filename", "WaterLevel"] + defect_columns + ["Split"])
            writer.writeheader()
            for r in records:
                row_dict = dict(r["raw_row"])
                row_dict["Split"] = r["split"]
                writer.writerow(row_dict)
        blob = bucket.blob(gcs_path)
        blob.upload_from_filename(out_path)
        print(f"Uploaded {len(records)} records to gs://{bucket_name}/{gcs_path}")

    export_curated_csv(curated_train, "datasets/sewer-ml/splits/train/curated_train.csv")
    export_curated_csv(curated_val, "datasets/sewer-ml/splits/validation/curated_val.csv")

    # Also generate wanted images list
    wanted_filenames = [r["Filename"] for r in curated_train] + [r["Filename"] for r in curated_val]
    wanted_txt = "\n".join(wanted_filenames)
    bucket.blob("datasets/sewer-ml/manifests/curated_wanted_images.txt").upload_from_string(wanted_txt)
    print(f"Uploaded {len(wanted_filenames)} wanted image filenames to manifests/curated_wanted_images.txt")

    print("=== Curation and Manifest Generation Complete ===")

if __name__ == "__main__":
    analyze_and_curate()
