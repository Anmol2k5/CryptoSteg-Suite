from PIL import Image
import os

DELIMITER = "#####"

def text_to_binary(text):
    return "".join(format(ord(char), '08b') for char in text)

def binary_to_text(binary):
    text = ""
    for i in range(0, len(binary), 8):
        byte = binary[i:i + 8]
        if len(byte) == 8:
            text += chr(int(byte, 2))
    return text

def encode_lsb(input_image_path, output_image_path, secret_message):
    if not os.path.exists(input_image_path):
        raise FileNotFoundError(f"Input image not found: {input_image_path}")

    image = Image.open(input_image_path).convert("RGB")
    width, height = image.size
    pixels = list(image.getdata())

    full_message = secret_message + DELIMITER
    binary_payload = text_to_binary(full_message)

    total_bits = len(binary_payload)
    max_bits = len(pixels) * 3

    if total_bits > max_bits:
        raise ValueError(f"Message too long! Capacity is {max_bits // 8} characters.")

    bit_index = 0
    new_pixels = []

    for pixel in pixels:
        r, g, b = pixel
        if bit_index < total_bits:
            r = (r & 0xFE) | int(binary_payload[bit_index])
            bit_index += 1
        if bit_index < total_bits:
            g = (g & 0xFE) | int(binary_payload[bit_index])
            bit_index += 1
        if bit_index < total_bits:
            b = (b & 0xFE) | int(binary_payload[bit_index])
            bit_index += 1

        new_pixels.append((r, g, b))
        if bit_index >= total_bits:
            new_pixels.extend(pixels[len(new_pixels):])
            break

    stego_image = Image.new("RGB", (width, height))
    stego_image.putdata(new_pixels)
    stego_image.save(output_image_path)
    return output_image_path

def decode_lsb(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Stego-image not found: {image_path}")

    image = Image.open(image_path).convert("RGB")
    pixels = list(image.getdata())

    binary_data = ""
    for r, g, b in pixels:
        binary_data += str(r & 1)
        binary_data += str(g & 1)
        binary_data += str(b & 1)
        # Optimization: check delimiter periodically if binary_data gets large
        if len(binary_data) % 8000 == 0:
            temp_text = binary_to_text(binary_data)
            if DELIMITER in temp_text:
                return temp_text[:temp_text.index(DELIMITER)]

    extracted_text = binary_to_text(binary_data)
    if DELIMITER in extracted_text:
        return extracted_text[:extracted_text.index(DELIMITER)]
    else:
        raise ValueError("No hidden message or valid delimiter found.")
