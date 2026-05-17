import cv2
import numpy as np
from PIL import Image

def sanitize_image(input_path: str, output_path: str, level: int = 1):
    """
    Sanitize an image by stripping Least Significant Bits (LSB).
    
    Level 1: Strips the last bit (& 0xFE)
    Level 2: Strips the last two bits (& 0xFC)
    """
    # Load image using OpenCV
    img = cv2.imread(input_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at {input_path}")
    
    # Define mask based on level
    if level == 1:
        mask = 0xFE
    elif level == 2:
        mask = 0xFC
    else:
        mask = 0xFE  # Default to level 1
        
    # Apply bitwise AND operation across all channels
    sanitized_img = img & mask
    
    # Save the sanitized image
    cv2.imwrite(output_path, sanitized_img)
    return output_path

def batch_sanitize(input_dir: str, output_dir: str, level: int = 1):
    """Sanitize all images in a directory."""
    import os
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            sanitize_image(input_path, output_path, level)
