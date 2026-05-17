import os
import sys
import subprocess

def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    else:
        print(result.stdout)

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    # Use local test_carrier.png
    carrier = "test_carrier.png"
    if not os.path.exists(carrier):
        print("Carrier image not found. Please ensure test_carrier.png exists in the parent directory.")
        return

    print("=== SSAT INTEGRATED TEST ===")
    
    # 1. Embed a secret message using DWT and AES
    print("\n[1] Embedding secret message...")
    run_command(["python", "main.py", "embed", "--input", carrier, "--output", "stego_dwt.png", "--payload", "SECRET_AGENT_007", "--password", "topsecret"])
    
    # 2. Analyze the stego image (Chi-Squared)
    print("\n[2] Analyzing stego image...")
    run_command(["python", "main.py", "analyze", "--input", "stego_dwt.png", "--all"])
    
    # 3. Generate entropy heatmap
    print("\n[3] Generating entropy heatmap...")
    run_command(["python", "main.py", "analyze", "--input", "stego_dwt.png", "--heatmap", "heatmap.png"])
    
    # 4. Visualize bit-planes
    print("\n[4] Visualizing bit-planes...")
    run_command(["python", "main.py", "visualize", "--input", "stego_dwt.png", "--output", "bitplanes.png"])
    
    # 5. Sanitize (Purge) the stego image
    print("\n[5] Sanitizing stego image...")
    run_command(["python", "main.py", "sanitize", "--input", "stego_dwt.png", "--output", "sanitized.png", "--level", "1"])
    
    # 6. Analyze sanitized image
    print("\n[6] Analyzing sanitized image...")
    run_command(["python", "main.py", "analyze", "--input", "sanitized.png", "--all"])

if __name__ == "__main__":
    main()
