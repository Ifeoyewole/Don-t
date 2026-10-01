"""Automated Dataset Image Quality Screening Tool.

Excludes corrupt, blank, or unusable frames from training candidates prior to human review.
"""

from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np


def screen_dataset_images(
    image_paths: List[Path],
    min_resolution: Tuple[int, int] = (640, 480),
    min_variance: float = 20.0,
) -> Tuple[List[Path], List[Tuple[Path, str]]]:
    """Filter out corrupt or severely degraded image candidates.

    Returns:
        Tuple of (accepted_image_paths, rejected_with_reasons)
    """
    accepted = []
    rejected = []

    for path in image_paths:
        if not path.exists():
            rejected.append((path, "File does not exist"))
            continue

        img = cv2.imread(str(path))
        if img is None:
            rejected.append((path, "Failed to decode image"))
            continue

        h, w = img.shape[:2]
        if w < min_resolution[0] or h < min_resolution[1]:
            rejected.append((path, f"Resolution {w}x{h} below minimum {min_resolution[0]}x{min_resolution[1]}"))
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        var = float(np.var(gray))
        if var < min_variance:
            rejected.append((path, f"Image is solid or near-blank (variance {var:.1f} < {min_variance})"))
            continue

        accepted.append(path)

    return accepted, rejected
