import cv2
import numpy as np
import pywt
from PIL import Image
from .crypto import encrypt_payload, decrypt_payload

def embed_dwt(image_path: str, output_path: str, payload: str, password: str = None, alpha: float = 0.05):
    """
    Embed a payload into the image using Discrete Wavelet Transform (DWT).
    Targeting the LH/HL sub-bands for robustness.
    """
    # Encrypt payload if password is provided
    if password:
        final_payload = encrypt_payload(payload, password)
    else:
        final_payload = payload
        
    # Convert payload to binary string
    binary_payload = ''.join(format(ord(c), '08b') for c in final_payload)
    binary_payload += '1111111111111110'  # Delimiter
    
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at {image_path}")
    
    # Process each channel independently
    channels = cv2.split(img)
    new_channels = []
    
    payload_idx = 0
    payload_len = len(binary_payload)
    
    for channel in channels:
        # Perform 2D DWT
        coeffs2 = pywt.dwt2(channel.astype(float), 'haar')
        LL, (LH, HL, HH) = coeffs2
        
        # Embed bits into LH coefficients
        if payload_idx < payload_len:
            # We can only embed as many bits as the sub-band size
            flat_LH = LH.flatten()
            for i in range(len(flat_LH)):
                if payload_idx < payload_len:
                    bit = int(binary_payload[payload_idx])
                    # Simple additive embedding or replacement
                    # For better robustness, use a more complex scheme.
                    # Here we modify the coefficient slightly based on the bit.
                    if bit == 1:
                        flat_LH[i] += alpha * np.abs(flat_LH[i]) if flat_LH[i] != 0 else alpha
                    else:
                        flat_LH[i] -= alpha * np.abs(flat_LH[i]) if flat_LH[i] != 0 else -alpha
                    payload_idx += 1
                else:
                    break
            LH = flat_LH.reshape(LH.shape)
            
        # Reconstruct channel
        new_channel = pywt.idwt2((LL, (LH, HL, HH)), 'haar')
        new_channels.append(np.clip(new_channel, 0, 255).astype(np.uint8))
        
    # Merge channels and save
    stego_img = cv2.merge(new_channels)
    cv2.imwrite(output_path, stego_img)
    return output_path

def extract_dwt(image_path: str, password: str = None):
    """
    Extract payload from a DWT-encoded image.
    Note: Robust extraction without the original image is difficult with simple additive embedding.
    This is a simplified demonstration.
    """
    # In a real-world scenario, we'd need a more sophisticated reference-free extraction
    # or the original image. For this toolkit, we'll implement a basic reference-free heuristic
    # or simply note the complexity.
    return "Extraction requires original image or more advanced blind extraction logic (Work in Progress)"

# ===== Traitor Tracing & Proof of Authorship =====

import hashlib
import json

def generate_watermark_key(user_id: str, secret: str) -> str:
    """Generate a unique watermark key for a user/content owner."""
    combined = f"{user_id}:{secret}"
    return hashlib.sha256(combined.encode()).hexdigest()

def embed_watermark(image_path: str, output_path: str, owner_id: str, secret: str,
                     strength: float = 0.1) -> dict:
    """
    Embed a unique ownership watermark using spread-spectrum technique.
    Returns metadata for later verification.
    """
    import os

    # Generate owner's unique watermark key
    watermark_key = generate_watermark_key(owner_id, secret)

    # Load image
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at {image_path}")

    # Create pseudo-random sequence from watermark key
    np.random.seed(int(watermark_key[:8], 16))
    watermark_sequence = np.random.choice([0, 1], size=img.shape[:2])

    # Embed using spread spectrum (add to LSB with strength factor)
    channels = cv2.split(img)
    new_channels = []

    for i, channel in enumerate(channels):
        # Use different slice for each channel
        channel_wm = watermark_sequence.copy()
        if i == 1:  # Shift for second channel
            channel_wm = np.roll(channel_wm, 50, axis=1)

        # Embed: add to LSB with strength factor
        embedded = channel.astype(float) + (channel_wm * strength * 255)
        new_channels.append(np.clip(embedded, 0, 255).astype(np.uint8))

    # Merge and save
    stego_img = cv2.merge(new_channels)
    cv2.imwrite(output_path, stego_img)

    # Generate proof metadata
    proof_metadata = {
        "owner_id": owner_id,
        "watermark_hash": watermark_key[:16],
        "algorithm": "SSAT-SpreadSpectrum",
        "strength": strength,
        "timestamp": str(os.path.getmtime(image_path))
    }

    return proof_metadata

def verify_watermark(image_path: str, owner_id: str, secret: str,
                     proof_metadata: dict, threshold: float = 0.6) -> dict:
    """
    Verify watermark ownership using correlation detection.
    """
    # Regenerate expected watermark
    watermark_key = generate_watermark_key(owner_id, secret)
    np.random.seed(int(watermark_key[:8], 16))
    expected_wm = np.random.choice([0, 1], size=(100, 100))  # Sample size

    # Load image and extract LSB pattern
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at {image_path}")

    # Sample from center region
    h, w = img.shape[:2]
    center = img[h//2-50:h//2+50, w//2-50:w//2+50, 0]
    extracted_wm = (center & 1)

    # Compute correlation
    if extracted_wm.shape == expected_wm.shape:
        correlation = np.corrcoef(expected_wm.flatten(), extracted_wm.flatten())[0, 1]
    else:
        correlation = 0

    # Verify against stored hash and correlation
    hash_match = watermark_key[:16] == proof_metadata.get("watermark_hash", "")

    return {
        "hash_match": hash_match,
        "correlation": correlation,
        "verified": hash_match and correlation > threshold,
        "owner": owner_id
    }

def extract_traitor_tracing_id(stego_image_path: str, known_watermarks: dict) -> dict:
    """
    Given a stego image, identify which watermark (from known owners) is present.
    Used for traitor tracing - finding which authorized user leaked content.
    """
    img = cv2.read(stego_image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at {stego_image_path}")

    results = []

    for owner_id, watermark_data in known_watermarks.items():
        # Check correlation with each known watermark
        watermark_key = generate_watermark_key(owner_id, watermark_data["secret"])
        np.random.seed(int(watermark_key[:8], 16))
        expected_wm = np.random.choice([0, 1], size=(50, 50))

        # Sample center region
        h, w = img.shape[:2]
        center = img[h//2-25:h//2+25, w//2-25:w//2+25, 0]
        extracted = (center & 1)

        if extracted.shape == expected_wm.shape:
            correlation = np.corrcoef(expected_wm.flatten(), extracted.flatten())[0, 1]
            results.append({
                "owner_id": owner_id,
                "correlation": correlation
            })

    # Sort by correlation
    results.sort(key=lambda x: x["correlation"], reverse=True)

    return {
        "identified_owner": results[0]["owner_id"] if results else None,
        "all_correlations": results
    }
