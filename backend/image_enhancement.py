import cv2
import numpy as np

def enhance_image(image: np.ndarray) -> np.ndarray:
    """
    Measurement-focused image enhancement pipeline.
    Improves edge visibility for gap measurement WITHOUT distorting
    or moving pixel geometry. Works for both iPhone and GoPro MAX images.
    
    Steps:
    1. Edge-preserving denoise (bilateral filter)
    2. CLAHE local contrast
    3. Unsharp mask
    
    Args:
        image: A numpy array representing the image in BGR format.
        
    Returns:
        The enhanced numpy array image.
    """
    # Create a copy so we don't modify the original in-place unexpectedly
    enhanced = image.copy()
    
    # 1. Edge-preserving denoise (Bilateral Filter)
    # This replaces the custom applyEdgePreservingDenoise loop.
    # d=5 (diameter), sigmaColor=25, sigmaSpace=25 matches roughly the radius=2, intensityRange=25
    enhanced = cv2.bilateralFilter(enhanced, d=5, sigmaColor=25, sigmaSpace=25)
    
    # 2. Local contrast enhancement (CLAHE)
    # Convert to LAB color space to apply CLAHE to the L (Lightness) channel only
    lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_clahe = clahe.apply(l_channel)
    
    # Merge back and convert to BGR
    lab_clahe = cv2.merge((l_clahe, a_channel, b_channel))
    enhanced = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
    
    # 3. Unsharp mask
    # formula: original + amount * (original - blurred)
    # We use GaussianBlur instead of simple box blur for better results, but keep radius tight.
    # radius=2 in TS -> roughly ksize=(5, 5) or (3, 3) in OpenCV. Let's use (5, 5).
    amount = 0.4
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
    
    # We need to calculate this in float to avoid clipping issues during subtraction
    enhanced_float = enhanced.astype(float)
    blurred_float = blurred.astype(float)
    
    unsharped = enhanced_float + amount * (enhanced_float - blurred_float)
    unsharped = np.clip(unsharped, 0, 255).astype(np.uint8)
    
    return unsharped

def create_enhanced_variants(image: np.ndarray) -> dict:
    """
    Creates the different cropped variants of the enhanced image.
    Returns a dictionary of labels to image arrays.
    """
    enhanced_img = enhance_image(image)
    height, width = enhanced_img.shape[:2]
    
    variants = {}
    
    # 'full-enhanced'
    variants['full-enhanced'] = enhanced_img
    
    # 'center-zoom'
    cz_sx, cz_sy = int(width * 0.18), int(height * 0.18)
    cz_w, cz_h = int(width * 0.64), int(height * 0.64)
    variants['center-zoom'] = enhanced_img[cz_sy:cz_sy+cz_h, cz_sx:cz_sx+cz_w]
    
    # 'upper-strip'
    us_h = int(height * 0.42)
    variants['upper-strip'] = enhanced_img[0:us_h, 0:width]
    
    # 'middle-strip'
    ms_sy = int(height * 0.29)
    ms_h = int(height * 0.42)
    variants['middle-strip'] = enhanced_img[ms_sy:ms_sy+ms_h, 0:width]
    
    # 'lower-strip'
    ls_sy = int(height * 0.58)
    ls_h = int(height * 0.42)
    variants['lower-strip'] = enhanced_img[ls_sy:ls_sy+ls_h, 0:width]
    
    # 'left-band'
    lb_w = int(width * 0.5)
    variants['left-band'] = enhanced_img[0:height, 0:lb_w]
    
    # 'right-band'
    rb_sx = int(width * 0.5)
    rb_w = int(width * 0.5)
    variants['right-band'] = enhanced_img[0:height, rb_sx:rb_sx+rb_w]
    
    return variants
