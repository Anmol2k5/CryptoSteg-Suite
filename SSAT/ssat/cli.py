import argparse
import sys
import os
import json
from .sanitize import sanitize_image
from .analyze import generate_entropy_heatmap, chi_squared_test, sample_pair_analysis, rs_analysis
from .embed import embed_dwt, embed_watermark, verify_watermark, extract_traitor_tracing_id
from .visualize import create_bit_plane_grid, run_dashboard

def main():
    parser = argparse.ArgumentParser(description="SSAT: Secure Steganographic AI Toolkit")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Sanitize command
    sanitize_parser = subparsers.add_parser("sanitize", help="Purge LSB-based payloads")
    sanitize_parser.add_argument("--input", required=True, help="Input image path")
    sanitize_parser.add_argument("--output", required=True, help="Output image path")
    sanitize_parser.add_argument("--level", type=int, default=1, choices=[1, 2], help="Sanitization level (1 or 2)")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze image for steganography")
    analyze_parser.add_argument("--input", required=True, help="Input image path")
    analyze_parser.add_argument("--heatmap", help="Path to save entropy heatmap")
    analyze_parser.add_argument("--chi2", action="store_true", help="Run Chi-Squared test")
    analyze_parser.add_argument("--spa", action="store_true", help="Run Sample Pair Analysis")
    analyze_parser.add_argument("--rs", action="store_true", help="Run RS Analysis")
    analyze_parser.add_argument("--all", action="store_true", help="Run all tests")

    # Embed command
    embed_parser = subparsers.add_parser("embed", help="Embed payload into image")
    embed_parser.add_argument("--input", required=True, help="Input image path")
    embed_parser.add_argument("--output", required=True, help="Output image path")
    embed_parser.add_argument("--payload", required=True, help="Text payload to embed")
    embed_parser.add_argument("--password", help="Password for AES encryption")
    embed_parser.add_argument("--alpha", type=float, default=0.05, help="Embedding strength (alpha)")

    # Watermark command
    watermark_parser = subparsers.add_parser("watermark", help="Embed ownership watermark")
    watermark_parser.add_argument("--input", required=True, help="Input image path")
    watermark_parser.add_argument("--output", required=True, help="Output image path")
    watermark_parser.add_argument("--owner", required=True, help="Owner ID")
    watermark_parser.add_argument("--secret", required=True, help="Secret key")
    watermark_parser.add_argument("--strength", type=float, default=0.1, help="Watermark strength")
    watermark_parser.add_argument("--verify", action="store_true", help="Verify existing watermark")
    watermark_parser.add_argument("--metadata", help="Path to proof metadata JSON")

    # Traitor Tracing command
    trace_parser = subparsers.add_parser("trace", help="Identify watermark owner in stego image")
    trace_parser.add_argument("--input", required=True, help="Stego image path")
    trace_parser.add_argument("--database", required=True, help="JSON file with known watermarks")

    # Visualize command
    visualize_parser = subparsers.add_parser("visualize", help="Visualize bit-planes")
    visualize_parser.add_argument("--input", required=True, help="Input image path")
    visualize_parser.add_argument("--output", required=True, help="Output grid path")

    # Dashboard command
    dash_parser = subparsers.add_parser("dashboard", help="Launch web visualization dashboard")
    dash_parser.add_argument("--host", default="127.0.0.1", help="Host address")
    dash_parser.add_argument("--port", type=int, default=5000, help="Port number")

    args = parser.parse_args()

    if args.command == "sanitize":
        print(f"[*] Sanitizing {args.input} (Level {args.level})...")
        sanitize_image(args.input, args.output, args.level)
        print(f"[+] Saved sanitized image to {args.output}")

    elif args.command == "analyze":
        if args.heatmap:
            print(f"[*] Generating entropy heatmap for {args.input}...")
            generate_entropy_heatmap(args.input, args.heatmap)
            print(f"[+] Saved heatmap to {args.heatmap}\n")

        if args.chi2 or args.spa or args.rs or args.all:
            print("=" * 70)
            print("                 🔍 SSAT FORENSIC ANALYSIS REPORT 🔍")
            print("=" * 70)
            print(f"📁 Target Image : {args.input}\n")

            stego_flags = 0
            total_tests = 0

            if args.chi2 or args.all:
                total_tests += 1
                score = chi_squared_test(args.input)
                print("📊 [TEST 1] Chi-Squared Statistical Anomaly Test")
                print(f" ├─ Raw Score   : {score:.2f}")
                if score > 100:
                    stego_flags += 1
                    print(" ├─ Status      : ⚠️ HIGH ANOMALY DETECTED")
                    print(" └─ Layman Note : (Normal < 100). The colors in this image have unnatural mathematical patterns, which happens when data is hidden inside.\n")
                else:
                    print(" ├─ Status      : ✅ NATURAL")
                    print(" └─ Layman Note : Image colors look completely natural and unaltered.\n")

            if args.spa or args.all:
                total_tests += 1
                spa_result = sample_pair_analysis(args.input)
                corr = spa_result['lsb_correlation']
                print("📊 [TEST 2] Sample Pair Analysis (SPA)")
                print(f" ├─ LSB Match   : {corr * 100:.2f}%")
                if spa_result['indicator'] == "stego":
                    stego_flags += 1
                    print(" ├─ Status      : ⚠️ MODIFIED BITS DETECTED")
                    print(" └─ Layman Note : Adjacent pixels match too perfectly or too poorly. Someone likely altered the last bits (LSB) to hide text.\n")
                else:
                    print(" ├─ Status      : ✅ NATURAL")
                    print(" └─ Layman Note : Neighboring pixels have normal, natural variations.\n")

            if args.rs or args.all:
                total_tests += 1
                rs_result = rs_analysis(args.input)
                ratio = rs_result['rs_ratio']
                print("📊 [TEST 3] RS (Regular-Singular) Flipper Analysis")
                print(f" ├─ RS Ratio    : {ratio:.4f}")
                if rs_result['indicator'] == "stego":
                    stego_flags += 1
                    print(" ├─ Status      : ⚠️ STEGANOGRAPHY DETECTED")
                    print(" └─ Layman Note : (Normal near 0). Ratio is > 0.05! Clear evidence that pixel groups were flipped to embed secret data.\n")
                else:
                    print(" ├─ Status      : ✅ NATURAL")
                    print(" └─ Layman Note : Pixel flipping tests show no hidden modifications.\n")

            print("─" * 70)
            if stego_flags > 0:
                print(f"🚨 FINAL VERDICT : HIGH RISK ({stego_flags}/{total_tests} Tests found HIDDEN DATA / STEGO) 🚨")
            else:
                print(f"✅ FINAL VERDICT : CLEAN (All {total_tests} Tests passed. No hidden data detected) ✅")
            print("─" * 70)

    elif args.command == "embed":
        print(f"[*] Embedding payload into {args.input} using DWT...")
        embed_dwt(args.input, args.output, args.payload, args.password, args.alpha)
        print(f"[+] Saved stego-image to {args.output}")

    elif args.command == "watermark":
        if args.verify:
            if not args.metadata:
                print("[!] Error: --metadata required for verification")
                sys.exit(1)
            print(f"[*] Verifying watermark in {args.input}...")
            with open(args.metadata, 'r') as f:
                metadata = json.load(f)
            result = verify_watermark(args.input, args.owner, args.secret, metadata)
            print(f"[+] Hash Match: {result['hash_match']}")
            print(f"[+] Correlation: {result['correlation']:.4f}")
            print(f"[+] Verified: {result['verified']}")
        else:
            print(f"[*] Embedding watermark for owner: {args.owner}...")
            proof = embed_watermark(args.input, args.output, args.owner, args.secret, args.strength)
            print(f"[+] Watermark embedded. Metadata saved.")
            # Save metadata
            metadata_path = args.output.replace('.png', '_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(proof, f)
            print(f"[+] Proof metadata saved to {metadata_path}")

    elif args.command == "trace":
        print(f"[*] Running traitor tracing on {args.input}...")
        with open(args.database, 'r') as f:
            watermarks = json.load(f)
        result = extract_traitor_tracing_id(args.input, watermarks)
        print(f"[+] Identified Owner: {result['identified_owner']}")
        print(f"[+] All correlations: {result['all_correlations']}")

    elif args.command == "visualize":
        print(f"[*] Visualizing bit-planes for {args.input}...")
        create_bit_plane_grid(args.input, args.output)
        print(f"[+] Saved bit-plane grid to {args.output}")

    elif args.command == "dashboard":
        print(f"[*] Starting SSAT Dashboard at http://{args.host}:{args.port}")
        run_dashboard(args.host, args.port)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
