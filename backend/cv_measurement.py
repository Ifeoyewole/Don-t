import cv2
import numpy as np
import math
from typing import Optional, Dict, Any, Tuple
from image_enhancement import enhance_image

DEFAULT_PIPE_DIAMETER_MM = 225
MAX_PROCESS_DIMENSION = 1200
ANGLE_STEPS = 72
BASE_CLOSE_UP_MM_PER_PIXEL = 0.075

VERTICAL_BLACK_GAP_SCALE = [
    {"maxDiameterMm": 150, "mmPerPixel": 0.389},
    {"maxDiameterMm": 225, "mmPerPixel": 0.18},
    {"maxDiameterMm": 300, "mmPerPixel": 0.24},
    {"maxDiameterMm": 450, "mmPerPixel": 0.34},
    {"maxDiameterMm": 600, "mmPerPixel": 0.44},
    {"maxDiameterMm": float('inf'), "mmPerPixel": 0.55},
]

CLOSE_UP_PIPE_SCALE = [
    {"maxDiameterMm": 150, "scale": 5.18},
    {"maxDiameterMm": 225, "scale": 1},
    {"maxDiameterMm": 300, "scale": 1.08},
    {"maxDiameterMm": 450, "scale": 1.16},
    {"maxDiameterMm": 600, "scale": 1.24},
    {"maxDiameterMm": float('inf'), "scale": 1.34},
]

def classify_gap(gap_mm: float, pipe_diameter_mm: float) -> Dict[str, Any]:
    # Placeholder for the utils classification logic
    if gap_mm < 10:
        return {"status": "pass"}
    elif gap_mm < 25:
        return {"status": "review"}
    return {"status": "fail"}

def estimate_close_up_mm_per_pixel(pipe_diameter_mm: float) -> float:
    scale = 1.0
    for entry in CLOSE_UP_PIPE_SCALE:
        if pipe_diameter_mm <= entry["maxDiameterMm"]:
            scale = entry["scale"]
            break
    return round(BASE_CLOSE_UP_MM_PER_PIXEL * scale, 4)

def get_pixel(gray: np.ndarray, x: float, y: float) -> float:
    height, width = gray.shape
    cx = min(max(int(round(x)), 0), width - 1)
    cy = min(max(int(round(y)), 0), height - 1)
    return float(gray[cy, cx])

def smooth_profile(profile: list) -> list:
    n = len(profile)
    smoothed = []
    for i in range(n):
        start = max(0, i - 1)
        end = min(n - 1, i + 1)
        vals = profile[start:end+1]
        smoothed.append(sum(vals) / len(vals))
    return smoothed

def sample_ray_profile(gray: np.ndarray, center_x: float, center_y: float, angle: float, max_radius: int) -> list:
    profile = []
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    for r in range(max_radius + 1):
        profile.append(get_pixel(gray, center_x + cos_a * r, center_y + sin_a * r))
    return profile

def measure_gap_from_known_circle(gray: np.ndarray, pipe_diameter_mm: float, center_x: float, center_y: float, inner_radius_px: float, enhancement_used=False) -> Optional[Dict[str, Any]]:
    height, width = gray.shape
    gap_widths = []
    bright_threshold_samples = []
    covered_sectors = set()
    max_radius = int(min(width, height) * 0.45)
    
    for step in range(ANGLE_STEPS):
        angle = (math.pi * 2 * step) / ANGLE_STEPS
        profile = smooth_profile(sample_ray_profile(gray, center_x, center_y, angle, max_radius))
        sample_index = min(max(int(round(inner_radius_px * 0.75)), 0), len(profile) - 1)
        bright_threshold_samples.append(profile[sample_index])
        
    bright_threshold = min(max(np.mean(bright_threshold_samples) + 18, 86), 222)
    
    for step in range(ANGLE_STEPS):
        angle = (math.pi * 2 * step) / ANGLE_STEPS
        profile = smooth_profile(sample_ray_profile(gray, center_x, center_y, angle, max_radius))
        inner_r = min(max(int(round(inner_radius_px)), 4), len(profile) - 6)
        
        local_ref_slice = profile[max(0, inner_r - 3):min(len(profile), inner_r + 3)]
        local_reference = np.mean(local_ref_slice) if len(local_ref_slice) > 0 else 0
        ray_bright_threshold = min(max((bright_threshold + local_reference) / 2 + 10, 80), 228)
        
        outer_radius = -1
        best_score = 0
        
        limit_r = min(len(profile) - 2, inner_r + int(inner_radius_px * 0.6))
        for r in range(inner_r + 2, limit_r):
            gradient = profile[r + 1] - profile[r - 1]
            intensity_jump = profile[r] - profile[max(0, r - 2)]
            score = gradient + intensity_jump
            is_bright_enough = profile[r] >= ray_bright_threshold
            
            if score > best_score and gradient >= 5 and (is_bright_enough or intensity_jump >= 12):
                best_score = score
                outer_radius = r
                
        gap_pixels = outer_radius - inner_r
        if outer_radius > 0 and 2 <= gap_pixels <= inner_radius_px * 0.5:
            gap_widths.append(gap_pixels)
            covered_sectors.add(int(step / 6))
            
    if len(gap_widths) < 6 or len(covered_sectors) < 3:
        return None
        
    gap_pixels = np.median(gap_widths)
    gap_spread = np.std(gap_widths) if len(gap_widths) > 0 else 0
    mm_per_pixel = pipe_diameter_mm / (inner_radius_px * 2)
    gap_mm = round(gap_pixels * mm_per_pixel, 1)
    
    confidence = min(max(0.52 + len(gap_widths) / 90 + len(covered_sectors) / 24 - gap_spread / 24, 0.5), 0.93)
    
    if gap_mm <= 0.5 or gap_mm > 60:
        return None
        
    return {
        "gapMm": gap_mm,
        "confidence": round(confidence, 2),
        "note": "OpenCV confirmed the pipe opening, but the gap was estimated from partial visible joint slices." if confidence < 0.72 else None,
        "debug": {
            "pipeDetected": True,
            "gapPixels": round(float(gap_pixels), 1),
            "mmPerPixel": round(float(mm_per_pixel), 4),
            "enhancementUsed": enhancement_used
        }
    }

def try_measure_with_opencv(image: np.ndarray, pipe_diameter_mm: float) -> Optional[Dict[str, Any]]:
    # Scale image if needed
    height, width = image.shape[:2]
    scale = min(1.0, MAX_PROCESS_DIMENSION / max(width, height))
    if scale < 1.0:
        t_width = max(1, int(round(width * scale)))
        t_height = max(1, int(round(height * scale)))
        image = cv2.resize(image, (t_width, t_height), interpolation=cv2.INTER_AREA)
        
    # Enhance
    enhanced = enhance_image(image)
    gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    
    # Hough Circles
    height, width = gray.shape
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(24, int(height * 0.16)),
        param1=120,
        param2=28,
        minRadius=max(18, int(min(width, height) * 0.08)),
        maxRadius=max(24, int(min(width, height) * 0.34))
    )
    
    if circles is None or len(circles[0]) == 0:
        return None
        
    best_circle = None
    best_score = -1
    
    for circle in circles[0]:
        x, y, r = circle
        x_bias = abs(x / width - 0.5)
        y_bias = abs(y / height - 0.32)
        coverage = r / min(width, height)
        score = 1 - x_bias - y_bias + coverage
        
        if score > best_score:
            best_score = score
            best_circle = (x, y, r)
            
    if not best_circle:
        return None
        
    return measure_gap_from_known_circle(gray, pipe_diameter_mm, best_circle[0], best_circle[1], best_circle[2], True)

def run_cv_measurement(image: np.ndarray, pipe_diameter_mm: float = DEFAULT_PIPE_DIAMETER_MM) -> Dict[str, Any]:
    """
    Main entry point for processing the image and returning measurements.
    """
    measured = try_measure_with_opencv(image, pipe_diameter_mm)
    
    if measured:
        classification = classify_gap(measured["gapMm"], pipe_diameter_mm)
        return {
            "originalGapMm": measured["gapMm"],
            "status": classification["status"],
            "confidence": measured["confidence"],
            "measurementSource": "cv",
            "measurementNote": measured.get("note"),
            "cvDebug": measured.get("debug", {})
        }
        
    # Fallback if CV fails
    return {
        "originalGapMm": 0,
        "status": "review",
        "confidence": 0.0,
        "measurementSource": "fallback",
        "measurementNote": "CV failed to detect geometry.",
        "cvDebug": {"failureStage": "OpenCV HoughCircles"}
    }
