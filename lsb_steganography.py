"""
=============================================================================
  IMAGE STEGANOGRAPHY USING LEAST SIGNIFICANT BIT (LSB)
=============================================================================

  HOW LSB STEGANOGRAPHY WORKS:
  ─────────────────────────────
  Every pixel in an RGB image is made of 3 colour channels: Red, Green, Blue.
  Each channel is stored as an 8-bit integer (0–255).

  Example pixel value:  200  →  binary: 11001000
                                                ↑
                                         LSB (bit 0)

  The Least Significant Bit (LSB) contributes only ±1 to the colour value.
  Changing it causes virtually NO visible difference to the human eye.

  ENCODING IDEA:
  ──────────────
  1. Convert secret message → binary string.
  2. Append a known delimiter so decoder knows where message ends.
  3. Replace the LSB of each colour channel value with one message bit.
  4. Save the modified image — it looks identical to the original.

  DECODING IDEA:
  ──────────────
  1. Read the LSB of every colour channel in the same order.
  2. Concatenate those bits into a binary string.
  3. Convert each 8-bit chunk back to a character.
  4. Stop when the delimiter is found.

  Dependencies: Pillow  (pip install pillow)
  Author      : Cryptography Project
  Language    : Python 3.x

  AI IMAGE GENERATION (Pollinations.ai):
  ──────────────────────────────────────
  Pollinations.ai is a FREE public API that generates images from text prompts.
  No API key or sign-up required — just an internet connection.
  We request an image URL, download it, and use it as the carrier image.
  Since the response is PNG (lossless), LSB data is perfectly preserved.
=============================================================================
"""

from PIL import Image
import os
import sys
import urllib.request
import urllib.parse

# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────

# Delimiter that marks the END of the hidden message.
# Must be a unique string unlikely to appear in normal messages.
DELIMITER = "#####"

# ─────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────

def text_to_binary(text):
    """
    Convert a plain-text string into a binary string.

    Each character is converted to its ASCII code, then to an
    8-bit binary representation.

    Example:
        'A' → 65 → '01000001'
        'Hi' → '0100100001101001'
    """
    binary = ""
    for char in text:
        # ord() gives the ASCII/Unicode integer value of the character.
        # format(n, '08b') converts it to an 8-bit binary string.
        binary += format(ord(char), '08b')
    return binary


def binary_to_text(binary):
    """
    Convert a binary string back into readable plain text.

    Reads the binary string in 8-bit chunks and converts each chunk
    to its corresponding ASCII character.

    Example:
        '01000001' → 65 → 'A'
    """
    text = ""
    # Process 8 bits at a time (one character per byte)
    for i in range(0, len(binary), 8):
        byte = binary[i:i + 8]
        if len(byte) == 8:  # Guard against incomplete bytes at the end
            text += chr(int(byte, 2))  # int(str, 2) converts binary string to int
    return text


# ─────────────────────────────────────────────
#  CORE FUNCTION 1 — ENCODE
# ─────────────────────────────────────────────

def encode_image(input_image_path, output_image_path, secret_message):
    """
    Hide a secret message inside an image using LSB steganography.

    Parameters:
        input_image_path  (str) : Path to the original carrier image.
        output_image_path (str) : Path where the stego-image will be saved.
        secret_message    (str) : The text message to hide.

    Returns:
        True on success, raises an exception on failure.

    How it works:
        1. Open the image and get pixel data.
        2. Convert message + delimiter to binary.
        3. Embed each bit into the LSB of each R, G, B channel value.
        4. Save the modified image.
    """

    # ── Step 1: Load the image ──────────────────────────────────────────
    if not os.path.exists(input_image_path):
        raise FileNotFoundError(f"Input image not found: {input_image_path}")

    image = Image.open(input_image_path)

    # Convert to RGB mode to ensure consistent 3-channel pixels.
    # This handles grayscale, RGBA, palette images, etc.
    image = image.convert("RGB")

    width, height = image.size
    pixels = list(image.getdata())  # Flat list of (R, G, B) tuples

    # ── Step 2: Prepare binary payload ─────────────────────────────────
    # Append delimiter so the decoder knows where the message ends
    full_message = secret_message + DELIMITER
    binary_payload = text_to_binary(full_message)

    total_bits = len(binary_payload)
    # Each pixel holds 3 bits (one per RGB channel)
    max_bits = len(pixels) * 3

    # ── Step 3: Capacity check ──────────────────────────────────────────
    if total_bits > max_bits:
        raise ValueError(
            f"Message too long! "
            f"Need {total_bits} bits but image can only hold {max_bits} bits "
            f"({max_bits // 8} characters max, including delimiter)."
        )

    # ── Step 4: Embed bits into pixel LSBs ─────────────────────────────
    bit_index = 0          # Current position in the binary payload
    new_pixels = []        # Modified pixel list

    for pixel in pixels:
        r, g, b = pixel    # Unpack the three colour channels

        # Modify the LSB of Red channel
        if bit_index < total_bits:
            # Clear the LSB with '& 0xFE'  (e.g., ...X → ...0)
            # Set  the LSB with '| int(bit)' (embed the message bit)
            r = (r & 0xFE) | int(binary_payload[bit_index])
            bit_index += 1

        # Modify the LSB of Green channel
        if bit_index < total_bits:
            g = (g & 0xFE) | int(binary_payload[bit_index])
            bit_index += 1

        # Modify the LSB of Blue channel
        if bit_index < total_bits:
            b = (b & 0xFE) | int(binary_payload[bit_index])
            bit_index += 1

        new_pixels.append((r, g, b))

        # Once all bits are embedded, copy remaining pixels unchanged
        if bit_index >= total_bits:
            new_pixels.extend(pixels[len(new_pixels):])
            break

    # ── Step 5: Save the stego-image ────────────────────────────────────
    stego_image = Image.new("RGB", (width, height))
    stego_image.putdata(new_pixels)
    stego_image.save(output_image_path)

    print(f"\n[OK] Message successfully encoded!")
    print(f"     Bits used   : {total_bits} / {max_bits}")
    print(f"     Saved image : {output_image_path}\n")
    return True


# ─────────────────────────────────────────────
#  CORE FUNCTION 2 — DECODE
# ─────────────────────────────────────────────

def decode_image(image_path):
    """
    Extract a hidden message from a stego-image using LSB steganography.

    Parameters:
        image_path (str) : Path to the stego-image (must be the encoded output).

    Returns:
        secret_message (str) : The extracted hidden message.

    How it works:
        1. Open the stego-image.
        2. Read the LSB of every R, G, B channel in pixel order.
        3. Group bits into 8-bit bytes and convert to characters.
        4. Stop when the delimiter is found and return the message.
    """

    # ── Step 1: Load the image ──────────────────────────────────────────
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Stego-image not found: {image_path}")

    image = Image.open(image_path).convert("RGB")
    pixels = list(image.getdata())

    # ── Step 2: Extract LSBs from each channel ──────────────────────────
    binary_data = ""

    for pixel in pixels:
        r, g, b = pixel
        # Extract the LSB from each channel using '& 1' (bitwise AND with 1)
        binary_data += str(r & 1)   # LSB of Red
        binary_data += str(g & 1)   # LSB of Green
        binary_data += str(b & 1)   # LSB of Blue

    # ── Step 3: Convert binary to text and find delimiter ───────────────
    extracted_text = binary_to_text(binary_data)

    # Search for the delimiter that marks end of message
    if DELIMITER in extracted_text:
        # Return only the part before the delimiter
        secret_message = extracted_text[:extracted_text.index(DELIMITER)]
        return secret_message
    else:
        raise ValueError(
            "No hidden message found. "
            "The image may not be encoded, or was saved in a lossy format (e.g. JPEG)."
        )


# ─────────────────────────────────────────────
#  AI IMAGE GENERATION
# ─────────────────────────────────────────────

def generate_ai_image(prompt, save_path="ai_carrier.png", width=512, height=512):
    """
    Generate an AI image from a text prompt using the Pollinations.ai free API.

    Parameters:
        prompt    (str) : Text description of the image to generate.
        save_path (str) : Where to save the downloaded PNG image.
        width     (int) : Image width  in pixels (default 512).
        height    (int) : Image height in pixels (default 512).

    Returns:
        save_path (str) : Path to the saved AI-generated image.

    How it works:
        - Pollinations.ai exposes a simple HTTP endpoint:
          https://image.pollinations.ai/prompt/{encoded_prompt}
        - We URL-encode the prompt, make an HTTP GET request, and save
          the returned PNG directly to disk.
        - No API key or account needed — completely free.
        - The image is PNG (lossless), so LSB bits will not be corrupted.
    """
    print(f"\n  [AI] Generating image for prompt: '{prompt}'")
    print("  [AI] Contacting Pollinations.ai ... (this may take 10-20 seconds)")

    # URL-encode the prompt so spaces/special chars are safe in a URL
    encoded_prompt = urllib.parse.quote(prompt)

    # Build the API URL — model=flux gives high quality results
    url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width={width}&height={height}&model=flux&nologo=true"
    )

    try:
        # Add User-Agent header so servers/Cloudflare don't block default Python bot requests
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            image_data = response.read()

        # Save the raw PNG bytes to disk
        with open(save_path, "wb") as f:
            f.write(image_data)

        # Verify it opened correctly with Pillow
        img = Image.open(save_path).convert("RGB")
        img.save(save_path)  # Re-save to ensure proper RGB PNG format

        print(f"  [AI] Image generated and saved as: {save_path}")
        print(f"  [AI] Size: {img.size[0]}x{img.size[1]} pixels\n")
        return save_path

    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Could not reach Pollinations.ai. Check your internet connection.\n  Details: {e}"
        )
    except Exception as e:
        raise RuntimeError(f"AI image generation failed: {e}")


# ─────────────────────────────────────────────
#  COMMAND-LINE INTERFACE (CLI)
# ─────────────────────────────────────────────

def print_banner():
    """Print a styled welcome banner."""
    print("=" * 55)
    print("   LSB IMAGE STEGANOGRAPHY TOOL")
    print("   Hide secret messages inside images")
    print("=" * 55)


def cli_menu():
    """
    Interactive command-line menu for encoding and decoding messages.
    Loops until the user chooses to exit.
    """
    print_banner()

    while True:
        print("\n  MENU")
        print("  ─────────────────────────────")
        print("  1. Encode a message into an image")
        print("  2. Decode a message from an image")
        print("  3. Quick Test (no paths needed!)")
        print("  4. AI Image + Encode (Generate & Hide!)")
        print("  5. Exit")
        print("  ─────────────────────────────")

        choice = input("  Enter your choice (1/2/3/4/5): ").strip()

        # ── OPTION 1: ENCODE ──────────────────────────────────────────
        if choice == "1":
            print("\n[ENCODE MODE]")
            input_path  = input("  Path to input (carrier) image : ").strip()
            output_path = input("  Path to save output image     : ").strip()

            # Warn the user to save as PNG, not JPEG
            if output_path.lower().endswith(('.jpg', '.jpeg')):
                print("\n  [!] WARNING: JPEG uses lossy compression and will")
                print("      DESTROY the hidden data. Please use .png extension.")
                confirm = input("  Save anyway? (y/n): ").strip().lower()
                if confirm != 'y':
                    continue

            print("  Enter the secret message (press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            secret_message = "\n".join(lines)

            if not secret_message:
                print("  [!] No message entered. Returning to menu.")
                continue

            try:
                encode_image(input_path, output_path, secret_message)
            except (FileNotFoundError, ValueError) as e:
                print(f"\n  [ERROR] {e}\n")

        # ── OPTION 2: DECODE ──────────────────────────────────────────
        elif choice == "2":
            print("\n[DECODE MODE]")
            image_path = input("  Path to stego-image : ").strip()

            try:
                message = decode_image(image_path)
                print("\n[OK] Hidden message found:")
                print("─" * 40)
                print(message)
                print("─" * 40)
            except (FileNotFoundError, ValueError) as e:
                print(f"\n  [ERROR] {e}\n")

        # ── OPTION 3: QUICK TEST (no file paths needed) ───────────────
        elif choice == "3":
            print("\n[QUICK TEST MODE]")
            print("  Uses 'test_carrier.png' as input and saves to 'quick_test_out.png'")
            print("  Type your secret message below (press Enter twice to finish):")

            # Check the test image exists
            if not os.path.exists("test_carrier.png"):
                print("\n  [ERROR] 'test_carrier.png' not found in current folder.")
                print("  Run: python lsb_steganography.py example  to generate it first.\n")
                continue

            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            secret_message = "\n".join(lines)

            if not secret_message:
                print("  [!] No message entered.")
                continue

            try:
                encode_image("test_carrier.png", "quick_test_out.png", secret_message)
                recovered = decode_image("quick_test_out.png")
                print("[DECODED BACK] Hidden message:")
                print("-" * 40)
                print(recovered)
                print("-" * 40)
                if recovered == secret_message:
                    print("[OK] Encode -> Decode verified successfully!\n")
            except (FileNotFoundError, ValueError) as e:
                print(f"\n  [ERROR] {e}\n")

        # ── OPTION 4: AI IMAGE + ENCODE ───────────────────────────────
        elif choice == "4":
            print("\n[AI IMAGE + ENCODE MODE]")
            print("  An AI image will be generated from your prompt and used as the carrier.")
            print("  No image file needed — AI creates it for you!\n")

            prompt = input("  Enter image prompt (e.g. 'a futuristic city at night'): ").strip()
            if not prompt:
                print("  [!] No prompt entered. Returning to menu.")
                continue

            output_path = input("  Save stego image as (e.g. ai_stego.png)          : ").strip()
            if not output_path:
                output_path = "ai_stego.png"
            if not output_path.lower().endswith(".png"):
                output_path += ".png"

            print("\n  Enter the secret message (press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            secret_message = "\n".join(lines)

            if not secret_message:
                print("  [!] No message entered. Returning to menu.")
                continue

            try:
                ai_image_path = generate_ai_image(prompt)
                encode_image(ai_image_path, output_path, secret_message)
                print(f"  AI carrier saved as : {ai_image_path}")
                print(f"  Stego image saved as: {output_path}")
                print("\n  To decode later, run option 2 and enter:", output_path, "\n")
            except Exception as e:
                print(f"\n  [ERROR] {e}\n")

        # ── OPTION 5: EXIT ─────────────────────────────────────────────
        elif choice == "5":
            print("\n  Goodbye!\n")
            sys.exit(0)

        else:
            print("\n  [!] Invalid choice. Please enter 1, 2, 3, 4, or 5.")


# ─────────────────────────────────────────────
#  DIRECT USAGE EXAMPLE (for testing/demo)
# ─────────────────────────────────────────────

def run_example():
    """
    Quick demonstration of encoding and decoding without the CLI.

    To run this demo:
        1. Place any PNG image named 'original.png' in the same folder.
        2. Run:  python lsb_steganography.py example
    """
    print("\n[DEMO] Running encode → decode example...\n")

    input_img   = "test_carrier.png" if os.path.exists("test_carrier.png") else "original.png"
    encoded_img = "stego_output.png"
    message     = "Hello, Professor! This is a secret message hidden with LSB steganography."

    # --- Encode ---
    print(f"Secret message : '{message}'")
    encode_image(input_img, encoded_img, message)

    # --- Decode ---
    recovered = decode_image(encoded_img)
    print(f"Recovered msg  : '{recovered}'")

    # --- Verify ---
    if message == recovered:
        print("[OK] SUCCESS: Message matches perfectly!")
    else:
        print("[FAIL] MISMATCH: Something went wrong.")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run modes:
        python lsb_steganography.py           → Interactive CLI menu
        python lsb_steganography.py example   → Run the quick demo
    """
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) > 1 and sys.argv[1] == "example":
        run_example()
    else:
        cli_menu()
