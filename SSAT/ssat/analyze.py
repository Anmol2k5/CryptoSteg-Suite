import cv2
import numpy as np
import matplotlib.pyplot as plt

def calculate_entropy(block):
    """Calculate Shannon entropy of a pixel block."""
    if block.size == 0:
        return 0
    # Flatten and calculate histogram
    hist = cv2.calcHist([block], [0], None, [256], [0, 256])
    hist /= hist.sum()
    # Remove zeros for log calculation
    hist = hist[hist > 0]
    return -np.sum(hist * np.log2(hist))

def generate_entropy_heatmap(input_path: str, output_path: str, block_size: int = 8):
    """
    Generate an entropy heatmap of the image to detect high-entropy anomalies.
    """
    img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image not found at {input_path}")
    
    height, width = img.shape
    heatmap = np.zeros((height // block_size, width // block_size))
    
    for y in range(0, height - block_size + 1, block_size):
        for x in range(0, width - block_size + 1, block_size):
            block = img[y:y+block_size, x:x+block_size]
            heatmap[y // block_size, x // block_size] = calculate_entropy(block)
    
    # Normalize heatmap for visualization
    heatmap_norm = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)
    
    # Resize back to original image size for overlay
    heatmap_resized = cv2.resize(heatmap_color, (width, height), interpolation=cv2.INTER_NEAREST)
    
    cv2.imwrite(output_path, heatmap_resized)
    return output_path

def chi_squared_test(input_path: str):
    """
    Perform Chi-Squared test on Pairs of Values (PoV) to detect LSB steganography.
    """
    img = cv2.imread(input_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at {input_path}")
    
    # Flatten image and take a subset if too large
    pixels = img.flatten()
    if len(pixels) > 1000000:
        pixels = pixels[:1000000]
        
    # Count frequency of each pixel value
    counts = np.zeros(256)
    for p in pixels:
        counts[p] += 1
        
    # Calculate Chi-Squared statistic for PoVs (2i and 2i+1)
    chi_sq = 0
    for i in range(128):
        y1 = counts[2*i]
        y2 = counts[2*i+1]
        expected = (y1 + y2) / 2
        if expected > 0:
            chi_sq += ((y1 - expected)**2) / expected
            
    # p-value calculation (simplified)
    # A low p-value indicates that the distribution is NOT natural (likely stego)
    return chi_sq

def sample_pair_analysis(input_path: str) -> dict:
    """
    Sample Pair Analysis (SPA) - detects LSB steganography by analyzing
    correlations between pairs of pixels.
    """
    img = cv2.imread(input_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at {input_path}")

    # Use first channel for analysis
    if len(img.shape) == 3:
        gray = img[:, :, 0]
    else:
        gray = img

    height, width = gray.shape
    total_pairs = 0
    correlation_sum = 0

    # Sample pixel pairs (horizontal, vertical, diagonal)
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]

    for dy, dx in directions:
        for y in range(0, height - abs(dy)):
            for x in range(0, width - abs(dx)):
                p1 = gray[y, x]
                p2 = gray[y + dy, x + dx]

                # Check LSB correlation
                if (p1 & 1) == (p2 & 1):
                    correlation_sum += 1
                total_pairs += 1

    if total_pairs > 0:
        correlation_rate = correlation_sum / total_pairs
    else:
        correlation_rate = 0

    return {
        "total_pairs": total_pairs,
        "lsb_correlation": correlation_rate,
        "expected_natural": 0.5,
        "indicator": "stego" if abs(correlation_rate - 0.5) > 0.05 else "natural"
    }

def rs_analysis(input_path: str, sample_size: int = 10000) -> dict:
    """
    RS (Regular-Singular) Analysis - distinguishes stego images from cover
    by analyzing pixel group flip behavior.
    """
    import random

    img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image not found at {input_path}")

    height, width = img.shape

    # Random sampling for efficiency
    indices = random.sample(range(0, height * width), min(sample_size, height * width))

    def flip_group(pixels, mask):
        flipped = pixels.copy()
        for i in range(len(pixels)):
            if mask[i] == 1:
                flipped[i] = 255 - flipped[i]
        return flipped

    def compute_f(pixels):
        """Compute discrimination function"""
        return np.sum(np.abs(np.diff(pixels.astype(float))))

    # Initialize counters
    R = 0  # Regular groups
    S = 0  # Singular groups
    R_minus = 0
    S_minus = 0

    # Use 2x2 blocks
    block_size = 2
    mask_patterns = [
        np.array([[1, -1], [-1, 1]]),
        np.array([[-1, 1], [1, -1]]),
    ]

    for idx in indices:
        y = idx // width
        x = idx % width

        if y + block_size > height or x + block_size > width:
            continue

        block = img[y:y+block_size, x:x+block_size]
        pixels = block.flatten()

        # Test both mask patterns
        for mask in mask_patterns:
            mask_flat = mask.flatten()

            # Compute f before flip
            f_orig = compute_f(pixels)

            # Compute f after flip with mask
            flipped = flip_group(pixels, mask_flat)
            f_flipped = compute_f(flipped)

            # Compute f after flip with inverted mask
            flipped_inv = flip_group(pixels, -mask_flat)
            f_flipped_inv = compute_f(flipped_inv)

            # Classify as Regular or Singular
            if f_flipped > f_orig:
                if f_flipped_inv > f_orig:
                    R += 1
                else:
                    S_minus += 1
            else:
                if f_flipped_inv > f_orig:
                    S += 1
                else:
                    R_minus += 1

    # Calculate RS ratio
    total = R + S + R_minus + S_minus
    if total > 0:
        rs_ratio = (R - R_minus) / (R + S + R_minus + S_minus)
    else:
        rs_ratio = 0

    return {
        "R": R,
        "S": S,
        "R_minus": R_minus,
        "S_minus": S_minus,
        "rs_ratio": rs_ratio,
        "indicator": "stego" if abs(rs_ratio) > 0.05 else "natural"
    }
