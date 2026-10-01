import cv2
import numpy as np
import math

MAX_VALIDATION_DIMENSION = 640

def detect_opening_center(gray: np.ndarray):
    height, width = gray.shape
    start_x, end_x = int(width * 0.15), int(width * 0.85)
    start_y, end_y = int(height * 0.08), int(height * 0.72)
    
    roi = gray[start_y:end_y, start_x:end_x]
    count = roi.size
    
    if count == 0:
        return None
        
    min_val = np.min(roi)
    mean_val = np.mean(roi)
    
    dark_threshold = max(min_val + 18, min(118, mean_val * 0.64))
    bright_threshold = min(max(mean_val * 0.93, dark_threshold + 10), 220)
    
    # Create mask of dark pixels
    dark_mask = roi <= dark_threshold
    dark_pixels = roi[dark_mask]
    
    if len(dark_pixels) == 0:
        return None
        
    weights = dark_threshold - dark_pixels + 1
    
    # Get coordinates of dark pixels relative to full image
    y_indices, x_indices = np.nonzero(dark_mask)
    y_indices = y_indices + start_y
    x_indices = x_indices + start_x
    
    weight_sum = np.sum(weights)
    if weight_sum == 0:
        return None
        
    weighted_x = np.sum(x_indices * weights)
    weighted_y = np.sum(y_indices * weights)
    
    return {
        'x': weighted_x / weight_sum,
        'y': weighted_y / weight_sum,
        'brightThreshold': bright_threshold
    }

def get_pixel_clamped(gray: np.ndarray, x: float, y: float):
    height, width = gray.shape
    cx = min(max(int(round(x)), 0), width - 1)
    cy = min(max(int(round(y)), 0), height - 1)
    return gray[cy, cx]

def sample_ray_radii(gray: np.ndarray, center_x: float, center_y: float, bright_threshold: float):
    height, width = gray.shape
    radii = []
    max_radius = int(min(width, height) * 0.45)
    
    for step in range(36):
        angle = (math.pi * 2 * step) / 36
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        radius_found = -1
        
        for radius in range(4, max_radius + 1):
            sample = get_pixel_clamped(gray, center_x + cos_a * radius, center_y + sin_a * radius)
            if sample >= bright_threshold:
                radius_found = radius
                break
                
        if radius_found > 0:
            radii.append(radius_found)
            
    return radii

def detect_horizontal_linear_joint(gray: np.ndarray):
    height, width = gray.shape
    start_x, end_x = int(width * 0.08), int(math.ceil(width * 0.92))
    start_y, end_y = int(height * 0.12), int(math.ceil(height * 0.88))
    
    roi = gray[start_y:end_y, start_x:end_x]
    # Calculate row darkness: sum of (255 - pixel) / width
    # Which is (255 - mean of row)
    row_darkness = 255.0 - np.mean(roi, axis=1)
    
    baseline = np.mean(row_darkness)
    best_score = 0
    best_y = -1
    
    n_rows = len(row_darkness)
    for index in range(2, n_rows - 2):
        local = np.mean(row_darkness[index-2:index+3])
        upper = np.mean(row_darkness[max(0, index-20):max(1, index-8)])
        lower = np.mean(row_darkness[min(n_rows-1, index+8):min(n_rows, index+20)])
        
        contrast = local - max(upper, lower, baseline * 0.82)
        if contrast > best_score:
            best_score = contrast
            best_y = start_y + index
            
    if best_score < 18 or best_y < 0:
        return None
        
    score = max(0.38, min(0.92, best_score / 70.0))
    return {'score': float(round(score, 2))}

def detect_vertical_linear_joint(gray: np.ndarray):
    height, width = gray.shape
    start_x, end_x = int(width * 0.08), int(math.ceil(width * 0.92))
    start_y, end_y = int(height * 0.12), int(math.ceil(height * 0.88))
    
    roi = gray[start_y:end_y, start_x:end_x]
    # Calculate column darkness
    col_darkness = 255.0 - np.mean(roi, axis=0)
    
    baseline = np.mean(col_darkness)
    best_score = 0
    
    n_cols = len(col_darkness)
    for index in range(2, n_cols - 2):
        local = np.mean(col_darkness[index-2:index+3])
        left = np.mean(col_darkness[max(0, index-20):max(1, index-8)])
        right = np.mean(col_darkness[min(n_cols-1, index+8):min(n_cols, index+20)])
        
        contrast = local - max(left, right, baseline * 0.82)
        if contrast > best_score:
            best_score = contrast
            
    if best_score < 18:
        dark_threshold = baseline * 1.18
        best_run_score = 0
        run_start = -1
        
        for index in range(n_cols + 1):
            in_dark_run = index < n_cols and col_darkness[index] >= dark_threshold
            if in_dark_run and run_start < 0:
                run_start = index
                
            if (index == n_cols or not in_dark_run) and run_start >= 0:
                run_end = index - 1
                run_width = run_end - run_start + 1
                run_mean = np.mean(col_darkness[run_start:run_end+1])
                left_mean = np.mean(col_darkness[max(0, run_start-28):max(1, run_start-6)])
                right_mean = np.mean(col_darkness[min(n_cols-1, run_end+6):min(n_cols, run_end+28)])
                
                contrast = run_mean - max(left_mean, right_mean, baseline * 0.82)
                width_ok = (run_width >= width * 0.02) and (run_width <= width * 0.36)
                if width_ok and contrast > best_run_score:
                    best_run_score = contrast
                run_start = -1
                
        best_score = best_run_score
        
    if best_score < 12:
        return None
        
    score = max(0.38, min(0.92, best_score / 70.0))
    return {'score': float(round(score, 2))}

def detect_linear_joint(gray: np.ndarray):
    horizontal = detect_horizontal_linear_joint(gray)
    vertical = detect_vertical_linear_joint(gray)
    
    if not horizontal:
        return vertical
    if not vertical:
        return horizontal
        
    return horizontal if horizontal['score'] >= vertical['score'] else vertical

def validate_guided_photo(image: np.ndarray):
    """
    Validates a photo to ensure it meets requirements for gap measurement.
    Args:
        image: A numpy array representing the image (BGR).
    Returns:
        dict: Validation result with status, message, and score.
    """
    height, width = image.shape[:2]
    
    # Scale down for validation if necessary, similar to TS MAX_VALIDATION_DIMENSION
    scale = min(1.0, MAX_VALIDATION_DIMENSION / max(width, height))
    if scale < 1.0:
        val_width = max(1, int(round(width * scale)))
        val_height = max(1, int(round(height * scale)))
        scaled_img = cv2.resize(image, (val_width, val_height), interpolation=cv2.INTER_AREA)
    else:
        scaled_img = image
        
    gray = cv2.cvtColor(scaled_img, cv2.COLOR_BGR2GRAY)
    
    center = detect_opening_center(gray)
    if not center:
        linear_joint = detect_linear_joint(gray)
        if linear_joint:
            return {
                'status': 'ready',
                'message': 'Linear joint seam detected. Enhanced CV and AI review will confirm the measurement.',
                'score': linear_joint['score']
            }
        return {
            'status': 'retake',
            'message': 'Retake photo: keep the pipe opening visible and centered so the gap can be scaled correctly.',
            'score': 0.08
        }
        
    radii = sample_ray_radii(gray, center['x'], center['y'], center['brightThreshold'])
    if len(radii) < 16:
        linear_joint = detect_linear_joint(gray)
        if linear_joint:
            return {
                'status': 'ready',
                'message': 'Linear joint seam detected. Enhanced CV and AI review will confirm the measurement.',
                'score': linear_joint['score']
            }
        return {
            'status': 'retake',
            'message': 'Retake photo: the pipe opening is not clear enough for reliable gap measurement.',
            'score': 0.18
        }
        
    radius = np.median(radii)
    center_x_ratio = center['x'] / gray.shape[1]
    center_y_ratio = center['y'] / gray.shape[0]
    radius_ratio = radius / min(gray.shape[1], gray.shape[0])
    radius_variance = np.mean([abs(r - radius) for r in radii])
    
    centered_enough = 0.28 < center_x_ratio < 0.72 and 0.12 < center_y_ratio < 0.58
    opening_large_enough = radius_ratio > 0.13
    circle_stable_enough = radius_variance < radius * 0.22
    
    score = min(max(
        0.34 +
        (0.22 if centered_enough else 0) +
        (0.22 if opening_large_enough else 0) +
        (0.18 if circle_stable_enough else 0) +
        min(0.12, len(radii) / 300.0),
        0.0
    ), 1.0)
    
    if not centered_enough or not opening_large_enough or not circle_stable_enough:
        linear_joint = detect_linear_joint(gray)
        if linear_joint:
            return {
                'status': 'ready',
                'message': 'Linear joint seam detected. Enhanced CV and AI review will confirm the measurement.',
                'score': linear_joint['score']
            }
        return {
            'status': 'retake',
            'message': 'Retake photo: use the guided capture angle and keep the full pipe opening steady in frame.',
            'score': float(round(score, 2))
        }
        
    return {
        'status': 'ready',
        'message': 'Guided photo check passed.',
        'score': float(round(score, 2))
    }
