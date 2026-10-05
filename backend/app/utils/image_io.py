"""Image encoding, decoding, and I/O utility functions."""

import base64
from typing import Optional
import cv2
import numpy as np


ALLOWED_MAGIC_SIGNATURES = [
    b"\xff\xd8\xff",  # JPEG
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"RIFF",  # WebP container prefix
]


def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """Decode raw image bytes (JPEG, PNG, WebP) to an OpenCV BGR numpy array with strict security checks.

    Args:
        image_bytes: Raw binary bytes of the uploaded image file.

    Returns:
        np.ndarray: Decoded image in BGR format (H, W, 3).

    Raises:
        ValueError: If image decoding fails, format is unsupported, dimensions exceed bounds, or byte payload is corrupt.
    """
    if not image_bytes:
        raise ValueError("Image bytes payload is empty.")

    # 1. Enforce payload size limit (15 MB default)
    max_bytes = 15 * 1024 * 1024
    if len(image_bytes) > max_bytes:
        raise ValueError(f"Image payload size ({len(image_bytes)} bytes) exceeds maximum limit ({max_bytes} bytes).")

    # 2. Magic byte header verification (reject executables, scripts, or foreign formats)
    header = image_bytes[:16]
    is_valid_magic = any(header.startswith(sig) for sig in ALLOWED_MAGIC_SIGNATURES)
    if not is_valid_magic:
        raise ValueError("Invalid image file format. Only JPEG, PNG, and WebP images are permitted.")

    # Additional check for WebP format ('RIFF'....'WEBP')
    if header.startswith(b"RIFF") and b"WEBP" not in image_bytes[:16]:
        raise ValueError("Invalid RIFF container: WEBP signature missing.")

    # 3. Safe OpenCV decoding
    np_arr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is None or image.size == 0:
        raise ValueError("Corrupted or malformed image payload. OpenCV failed to decode pixels.")

    # 4. Dimension & Decompression Bomb Safeguards
    height, width = image.shape[:2]
    max_dimension = 8192
    max_total_pixels = 50_000_000  # 50 Megapixels

    if height > max_dimension or width > max_dimension:
        raise ValueError(
            f"Image dimensions ({width}x{height}) exceed maximum allowed dimension ({max_dimension}x{max_dimension})."
        )

    if (height * width) > max_total_pixels:
        raise ValueError(
            f"Image resolution ({width * height} pixels) exceeds decompression bomb limit ({max_total_pixels} pixels)."
        )

    return image


def encode_image_to_base64(
    image: np.ndarray,
    format: str = ".jpg",
    jpeg_quality: int = 85,
    include_prefix: bool = True,
) -> str:
    """Encode an OpenCV image (numpy array) to a Base64 string.

    Args:
        image: Numpy image array (BGR or Grayscale).
        format: Target image extension, e.g. '.jpg', '.png'.
        jpeg_quality: JPEG compression quality (1-100).
        include_prefix: If True, prefixes with data:image/jpeg;base64,

    Returns:
        str: Base64-encoded representation of the image.

    Raises:
        ValueError: If image array is invalid or encoding fails.
    """
    if image is None or image.size == 0:
        raise ValueError("Cannot encode empty or None image array.")

    encode_params = []
    if format.lower() in [".jpg", ".jpeg"]:
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
    elif format.lower() == ".png":
        encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 4]

    success, buffer = cv2.imencode(format, image, encode_params)
    if not success:
        raise ValueError(f"Failed to encode image to format {format}")

    b64_str = base64.b64encode(buffer).decode("utf-8")
    if include_prefix:
        mime_type = "image/png" if format.lower() == ".png" else "image/jpeg"
        return f"data:{mime_type};base64,{b64_str}"

    return b64_str
