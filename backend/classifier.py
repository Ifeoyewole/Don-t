import cv2
import numpy as np

def is_pipe(image: np.ndarray) -> bool:
    """
    Analyzes an image to determine if it contains a pipe opening using OpenCV Hough Circle Transform.
    
    Args:
        image: A numpy array representing the image (BGR format from cv2).
        
    Returns:
        bool: True if a pipe (circle) is detected, False otherwise.
    """
    # Convert image to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise and improve circle detection
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    
    # Use HoughCircles to detect circles
    # Adjust the parameters depending on typical pipe sizes in your images
    circles = cv2.HoughCircles(
        blurred, 
        cv2.HOUGH_GRADIENT, 
        dp=1.2, 
        minDist=100,
        param1=100, 
        param2=50, 
        minRadius=20, 
        maxRadius=0
    )
    
    # If at least one circle is detected, we assume it's a pipe opening
    if circles is not None:
        return True
    
    return False
