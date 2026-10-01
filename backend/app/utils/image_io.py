"""Image encoding, decoding, and I/O utility functions."""

import base64
from typing import Optional
import cv2
import numpy as np


def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """Decode raw image bytes (JPEG, PNG, WebP, TIFF) to an OpenCV BGR numpy array.

    Args:
        image_bytes: Raw binary bytes of the uploaded image file.

    Returns:
        np.ndarray: Decoded image in BGR format (H, W, 3) or (H, W).

    Raises:
        ValueError: If image decoding fails or byte payload is empty/corrupt.
    """
    if not image_bytes:
        raise ValueError("Image bytes payload is empty.")

    np_arr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is None or image.size == 0:
        raise ValueError("Failed to decode image from provided bytes. Unsupported or corrupted format.")

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
