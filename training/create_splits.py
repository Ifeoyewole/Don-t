"""Leak-Free Grouped Dataset Splitting Tool.

Splits dataset strictly by Inspection_ID / Video_ID to guarantee that adjacent frames
from the same physical joint or inspection run never leak between splits:
- 75% Training
- 15% Validation
- 10% Testing
"""

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def create_grouped_splits(
    dataset_csv: Path,
    output_dir: Path,
    train_ratio: float = 0.75,
    val_ratio: float = 0.15,
    test_ratio: float = 0.10,
    seed: int = 42,
) -> Tuple[int, int, int]:
    """Partition dataset into leak-free train/val/test splits grouped by inspection."""
    if not dataset_csv.exists():
        raise FileNotFoundError(f"Dataset CSV not found at: {dataset_csv}")

    random.seed(seed)

    # Group all samples by inspection ID
    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    fieldnames: List[str] = []

    with open(dataset_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or ["filename", "defect_code", "category", "inspection_id", "video_id"]
        for row in reader:
            group_key = row.get("inspection_id") or row.get("video_id") or f"GRP_{row['filename']}"
            groups[group_key].append(row)

    unique_groups = list(groups.keys())
    random.shuffle(unique_groups)

    num_groups = len(unique_groups)
    train_cutoff = int(num_groups * train_ratio)
    val_cutoff = train_cutoff + int(num_groups * val_ratio)

    train_groups = set(unique_groups[:train_cutoff])
    val_groups = set(unique_groups[train_cutoff:val_cutoff])
    test_groups = set(unique_groups[val_cutoff:])

    train_rows, val_rows, test_rows = [], [], []

    for group_key, rows in groups.items():
        if group_key in train_groups:
            train_rows.extend(rows)
        elif group_key in val_groups:
            val_rows.extend(rows)
        else:
            test_rows.extend(rows)

    output_dir.mkdir(parents=True, exist_ok=True)

    for split_name, split_rows in [("train", train_rows), ("val", val_rows), ("test", test_rows)]:
        split_file = output_dir / f"{split_name}.csv"
        with open(split_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(split_rows)

    return len(train_rows), len(val_rows), len(test_rows)


def main():
    parser = argparse.ArgumentParser(description="Create grouped leak-free train/val/test splits")
    parser.add_argument("--input_csv", type=str, default="training/data/deduplicated_dataset.csv")
    parser.add_argument("--output_dir", type=str, default="training/data/splits")
    parser.add_argument("--train_ratio", type=float, default=0.75)
    parser.add_argument("--val_ratio", type=float, default=0.15)
    parser.add_argument("--test_ratio", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    input_p = Path(args.input_csv)
    if input_p.exists():
        n_train, n_val, n_test = create_grouped_splits(
            input_p,
            Path(args.output_dir),
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed,
        )
        print(f"Splits created successfully: {n_train} train, {n_val} val, {n_test} test.")
    else:
        print(f"Input dataset file '{input_p}' not found.")


if __name__ == "__main__":
    main()
