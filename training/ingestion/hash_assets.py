"""Asset Hashing and Perceptual Fingerprinting.

Computes:
1. Exact cryptographic SHA-256 hash.
2. Perceptual Difference Hash (dHash 64-bit hex) for near-duplicate and re-scaled image detection.
"""

import hashlib
from pathlib import Path
from typing import Tuple, Union
import cv2
import numpy as np


def compute_sha256(file_path: Union[str, Path]) -> str:
    """Computes exact SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_sha256_bytes(data: bytes) -> str:
    """Computes exact SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_dhash(image: np.ndarray, hash_size: int = 8) -> str:
    """Computes 64-bit difference perceptual hash (dHash) from an image array."""
    if image is None or image.size == 0:
        return "0" * 16

    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Resize to (hash_size + 1, hash_size)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)

    # Compute difference between adjacent pixels: col[i] > col[i+1]
    diff = resized[:, 1:] > resized[:, :-1]

    # Convert binary array to hex string
    decimal_val = 0
    for bit in diff.flatten():
        decimal_val = (decimal_val << 1) | int(bit)

    return f"{decimal_val:016x}"


def compute_asset_hashes(file_path: Union[str, Path]) -> Tuple[str, str]:
    """Returns (sha256, perceptual_hash) for a given image file."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Asset file not found: {path}")

    sha256_val = compute_sha256(path)

    # Load image for dHash
    img = cv2.imread(str(path))
    if img is not None:
        dhash_val = compute_dhash(img)
    else:
        dhash_val = "0" * 16

    return sha256_val, dhash_val
