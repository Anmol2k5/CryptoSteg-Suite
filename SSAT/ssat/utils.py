import urllib.request
import urllib.parse
import os
from PIL import Image

def generate_ai_carrier(prompt: str, save_path: str = "carrier.png", width: int = 512, height: int = 512):
    """Generate an AI image from a prompt using Pollinations.ai."""
    print(f"[*] Generating AI image for prompt: '{prompt}'...")
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model=flux&nologo=true"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            image_data = response.read()
        
        with open(save_path, "wb") as f:
            f.write(image_data)
            
        # Ensure it's a valid RGB image
        img = Image.open(save_path).convert("RGB")
        img.save(save_path)
        return save_path
    except Exception as e:
        print(f"[!] AI Generation failed: {e}")
        return None
