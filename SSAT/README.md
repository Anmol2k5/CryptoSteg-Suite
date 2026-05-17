# Secure Steganographic AI Toolkit (SSAT)

SSAT is an advanced framework designed for the generative AI era. It provides a unified suite for executing and defending against multimodal Indirect Prompt Injection (IPI), applying cryptographic forensic watermarks, and analyzing digital media through frequency-domain steganography.

## Core Features

🛡️ **1. AI Agent Firewall Layer (Defense)**
- **Gateway Sanitizer**: Purges LSB-based adversarial prompts before VLM ingestion using deterministic bitwise masking.
- **Steganalysis Engine**: Flags structural anomalies using Entropy Heatmaps and statistical tests (Chi-Squared, SPA).

🏷️ **2. Provenance & Traitor Tracing (Watermarking)**
- **DWT Embedding**: Hides payloads in robust LH/HL sub-bands, surviving compression and resizing.
- **Cryptographic Authorship**: Couples watermarks with AES-256-GCM encryption for non-repudiation.

🧪 **3. Adversarial Resistance (Red Teaming)**
- **IPI Payload Generator**: Create test cases for Vision-Language Models.
- **Scrubber-Resistant Embedding**: Bypasses simple blurring and filtering attacks.

🎨 **4. Visual Analytics & Cryptography**
- **Bit-Plane Dashboard**: Isolate image bit-planes to visually detect hidden data patterns.
- **AES-256 Vault**: Military-grade security for all hidden payloads.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### 🛡️ Sanitize an image (Strip LSBs)
```bash
python main.py sanitize --input untrusted.png --output safe.png --level 1
```

### 🏷️ Embed an encrypted watermark
```bash
python main.py embed --input original.jpg --payload "OwnerID: 9948" --password "secure_key" --output stego.png
```

### 🔍 Analyze for anomalies
```bash
python main.py analyze --input suspicious.png --heatmap heatmap.png --test
```

### 🎨 Visualize bit-planes
```bash
python main.py visualize --input target.jpg --output grid.png
```

## Project Architecture
- `ssat/sanitize.py`: Deterministic decontamination.
- `ssat/analyze.py`: Probabilistic anomaly detection.
- `ssat/embed.py`: Frequency-domain DWT embedding.
- `ssat/crypto.py`: AES-256-GCM encryption vault.
- `ssat/visualize.py`: Bit-plane and entropy visualization.
