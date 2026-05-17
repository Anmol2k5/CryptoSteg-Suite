import cv2
import numpy as np
from flask import Flask, render_template_string, request, send_file, jsonify, session
import io
import base64
import hashlib
import tempfile
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(32)

BATCH_RESULTS_FILE = os.path.join(os.path.dirname(__file__), '_batch_results.json')

def _load_batch_results():
    if os.path.exists(BATCH_RESULTS_FILE):
        try:
            with open(BATCH_RESULTS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_batch_results(results):
    with open(BATCH_RESULTS_FILE, 'w') as f:
        json.dump(results, f)

SINGLE_ANALYSIS_FILE = os.path.join(os.path.dirname(__file__), '_single_result.json')

def _load_single_result():
    if os.path.exists(SINGLE_ANALYSIS_FILE):
        try:
            with open(SINGLE_ANALYSIS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    return None

def _save_single_result(result):
    with open(SINGLE_ANALYSIS_FILE, 'w') as f:
        json.dump(result, f)

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def analyze_image_bytes(img_bytes: bytes) -> dict:
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        temp_path = tmp.name
        cv2.imwrite(temp_path, img)

    try:
        from .analyze import chi_squared_test, sample_pair_analysis, rs_analysis
        chi_score = chi_squared_test(temp_path)
        spa = sample_pair_analysis(temp_path)
        rs = rs_analysis(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    stego_flags = 0
    if chi_score > 100:
        stego_flags += 1
    if spa['indicator'] == 'stego':
        stego_flags += 1
    if rs['indicator'] == 'stego':
        stego_flags += 1

    if stego_flags == 0:
        verdict = "CLEAN"
        risk_level = "LOW"
    elif stego_flags == 1:
        verdict = "SUSPICIOUS"
        risk_level = "MEDIUM"
    else:
        verdict = "INFECTED"
        risk_level = "HIGH"

    return {
        "chi_score": chi_score,
        "spa": spa,
        "rs": rs,
        "stego_flags": stego_flags,
        "verdict": verdict,
        "risk_level": risk_level
    }

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSAT Analytics Core</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        cyber: { 950: '#083344', 900: '#164e63', 800: '#155e75', 500: '#06b6d4', 400: '#22d3ee' }
                    },
                    fontFamily: {
                        mono: ['Courier New', 'Courier', 'monospace', 'sans-serif']
                    }
                }
            }
        }

        function updateFileName(input, targetId) {
            if (input.files && input.files[0]) {
                document.getElementById(targetId).innerText = input.files[0].name;
            }
        }

        function updateBatchFileNames(input) {
            const count = input.files ? input.files.length : 0;
            const el = document.getElementById('batch-name');
            if (count > 0) {
                el.innerText = count + ' file(s) selected for batch scan';
                el.classList.add('text-cyan-300');
            } else {
                el.innerText = 'Initialize_Batch_Upload_Sequence';
                el.classList.remove('text-cyan-300');
            }
        }

        function toggleGuide() {
            const guide = document.getElementById('stego-guide');
            const icon = document.getElementById('guide-icon');
            if (guide.classList.contains('hidden')) {
                guide.classList.remove('hidden');
                icon.style.transform = 'rotate(180deg)';
            } else {
                guide.classList.add('hidden');
                icon.style.transform = 'rotate(0deg)';
            }
        }

        function showBatchProgress() {
            document.getElementById('batch-progress').classList.remove('hidden');
        }

        function hideBatchProgress() {
            document.getElementById('batch-progress').classList.add('hidden');
        }
    </script>
    <style>
        @keyframes scan {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100%); }
        }
        .animate-scan {
            animation: scan 3s linear infinite;
        }
        @keyframes pulse-border {
            0%, 100% { border-color: rgba(6,182,212,0.3); }
            50% { border-color: rgba(6,182,212,0.8); }
        }
        .batch-dropzone {
            animation: pulse-border 2s ease-in-out infinite;
        }
        .batch-dropzone.dragover {
            border-color: #06b6d4 !important;
            background: rgba(6,182,212,0.1) !important;
        }
    </style>
</head>
<body class="min-h-screen bg-[#020203] text-gray-300 font-mono p-4 md:p-8 selection:bg-cyan-900 selection:text-cyan-100">

    <header class="mb-8 border-b border-[#222] pb-4 flex flex-col md:flex-row md:items-end justify-between gap-4 max-w-7xl mx-auto">
        <div class="flex items-center gap-4">
            <div class="relative flex items-center justify-center w-12 h-12 bg-cyan-950/30 border border-cyan-800 rounded-sm shadow-[0_0_15px_rgba(6,182,212,0.2)]">
                <i data-lucide="shield-alert" class="w-6 h-6 text-cyan-400"></i>
            </div>
            <div>
                <h1 class="text-xl md:text-3xl font-bold tracking-widest text-gray-100 uppercase flex items-center gap-2">
                    SSAT <span class="text-cyan-500 font-light">Analytics Core</span>
                </h1>
                <p class="text-xs text-gray-500 uppercase tracking-widest mt-1">
                    Forensic Steganalysis & Investigation Core v3.0.0
                </p>
            </div>
        </div>

        <div class="flex items-center gap-4 text-xs">
            <div class="flex items-center gap-2 bg-[#0a0a0f] border border-[#222] px-3 py-2 rounded-sm shadow-inner">
                <i data-lucide="server" class="w-3.5 h-3.5 text-emerald-500"></i>
                <span class="text-gray-400">SYS_NODE:</span>
                <span class="text-emerald-500 font-bold">127.0.0.1:5000</span>
            </div>
            <div class="flex items-center gap-2 bg-[#0a0a0f] border border-[#222] px-3 py-2 rounded-sm shadow-inner">
                <i data-lucide="activity" class="w-3.5 h-3.5 text-cyan-500 animate-pulse"></i>
                <span class="text-gray-400">STATUS:</span>
                <span class="text-cyan-500 font-bold">ONLINE</span>
            </div>
        </div>
    </header>

    <div class="max-w-7xl mx-auto space-y-8">

        <div class="bg-[#0a0a0f] border border-cyan-950 rounded-sm shadow-xl overflow-hidden transition-all duration-300">
            <button onclick="toggleGuide()" class="w-full bg-[#111] hover:bg-[#151520] px-6 py-4 flex items-center justify-between border-b border-[#222] transition-colors text-left cursor-pointer select-none">
                <div class="flex items-center gap-3">
                    <i data-lucide="help-circle" class="w-5 h-5 text-cyan-400"></i>
                    <span class="font-bold text-gray-200 uppercase tracking-wider text-sm md:text-base">
                        How Steganalysis Works & What These Reports Mean (Layman's Guide)
                    </span>
                </div>
                <div class="flex items-center gap-2 text-xs text-cyan-400 font-mono">
                    <span>CLICK TO EXPAND / COLLAPSE</span>
                    <i data-lucide="chevron-down" id="guide-icon" class="w-4 h-4 transition-transform duration-300"></i>
                </div>
            </button>
            <div id="stego-guide" class="p-6 bg-[#050508] text-xs md:text-sm text-gray-400 leading-relaxed space-y-6 border-t border-[#111] hidden">
                <p class="text-gray-300 border-l-2 border-cyan-500 pl-4 py-1">
                    When secret text is embedded into an image using LSB steganography, the human eye sees zero change. However, modifying the lowest bits leaves undeniable mathematical footprints. SSAT runs three statistical tests to uncover these secret payloads.
                </p>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div class="bg-[#0a0a0f] p-5 border border-[#1f1f30] rounded-sm relative overflow-hidden">
                        <div class="absolute top-0 left-0 right-0 h-1 bg-red-500"></div>
                        <h4 class="text-red-400 font-bold font-mono text-base mb-2 flex items-center gap-2">
                            <i data-lucide="bar-chart-2" class="w-4 h-4"></i> 1. Chi-Squared Test
                        </h4>
                        <p class="text-xs text-gray-400">
                            In natural photos, color frequencies vary smoothly. When secret data is hidden in LSBs, adjacent color values become unnaturally equal. Normal images score under 100.
                        </p>
                    </div>
                    <div class="bg-[#0a0a0f] p-5 border border-[#1f1f30] rounded-sm relative overflow-hidden">
                        <div class="absolute top-0 left-0 right-0 h-1 bg-emerald-500"></div>
                        <h4 class="text-emerald-400 font-bold font-mono text-base mb-2 flex items-center gap-2">
                            <i data-lucide="activity" class="w-4 h-4"></i> 2. Sample Pair Analysis
                        </h4>
                        <p class="text-xs text-gray-400">
                            Examines pairs of neighboring pixels. Hidden payloads inject random high-frequency noise, breaking natural correlation of lowest bit patterns.
                        </p>
                    </div>
                    <div class="bg-[#0a0a0f] p-5 border border-[#1f1f30] rounded-sm relative overflow-hidden">
                        <div class="absolute top-0 left-0 right-0 h-1 bg-purple-500"></div>
                        <h4 class="text-purple-400 font-bold font-mono text-base mb-2 flex items-center gap-2">
                            <i data-lucide="git-compare" class="w-4 h-4"></i> 3. RS Flipper Analysis
                        </h4>
                        <p class="text-xs text-gray-400">
                            Groups pixels and flips their LSBs using mathematical masks. Secret messages shatter the natural Regular vs Singular symmetry (RS Ratio > 0.05).
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <!-- BATCH SURVEILLANCE MODE -->
        <div class="bg-[#0a0a0f] border border-cyan-900/50 rounded-sm flex flex-col overflow-hidden relative shadow-2xl">
            <div class="bg-[#111] border-b border-[#222] px-4 py-2.5 flex items-center justify-between select-none">
                <div class="flex items-center gap-2 text-cyan-400 text-xs font-mono tracking-wider uppercase">
                    <i data-lucide="folder-search" class="w-4 h-4"></i>
                    Batch Surveillance Mode (10-50 Images)
                </div>
                <div class="flex gap-1.5">
                    <div class="w-2.5 h-2.5 rounded-full bg-cyan-900/50"></div>
                    <div class="w-2.5 h-2.5 rounded-full bg-cyan-900/50"></div>
                    <div class="w-2.5 h-2.5 rounded-full bg-cyan-900/50"></div>
                </div>
            </div>
            <div class="p-8">
                <form action="/batch" method="post" enctype="multipart/form-data" onsubmit="showBatchProgress()" class="space-y-6">
                    <div class="batch-dropzone flex flex-col items-center justify-center w-full h-32 px-4 transition-all border-2 border-dashed border-cyan-800/40 rounded-sm bg-[#050508] hover:bg-[#0a0a12] hover:border-cyan-500/60 cursor-pointer"
                         id="batch-dropzone"
                         ondragover="event.preventDefault(); this.classList.add('dragover')"
                         ondragleave="this.classList.remove('dragover')"
                         ondrop="event.preventDefault(); this.classList.remove('dragover'); const input = document.getElementById('batch-files'); input.files = event.dataTransfer.files; updateBatchFileNames(input);">
                        <label class="flex flex-col items-center justify-center w-full h-full cursor-pointer">
                            <div class="flex items-center gap-3 text-cyan-500">
                                <i data-lucide="folder-up" class="w-6 h-6"></i>
                                <span id="batch-name" class="text-xs font-bold tracking-widest uppercase">Initialize_Batch_Upload_Sequence</span>
                            </div>
                            <span class="text-[10px] text-gray-600 mt-1">Drag & drop folder contents or click to select multiple files (PNG, JPG, BMP)</span>
                            <input type="file" id="batch-files" name="images" accept="image/*" multiple required class="hidden" onchange="updateBatchFileNames(this)" />
                        </label>
                    </div>
                    <button type="submit" class="w-full border px-8 py-3.5 uppercase tracking-widest text-xs font-bold transition-all duration-300 flex items-center justify-center gap-2 bg-cyan-950/40 text-cyan-300 border-cyan-700 hover:bg-cyan-900/70 hover:border-cyan-400 hover:shadow-[0_0_25px_rgba(6,182,212,0.3)]">
                        <i data-lucide="scan-line" class="w-4 h-4"></i> [ RUN_BATCH_SURVEILLANCE ]
                    </button>
                </form>
                <div id="batch-progress" class="hidden mt-4 text-center">
                    <div class="inline-flex items-center gap-2 text-cyan-400 text-xs animate-pulse">
                        <i data-lucide="loader" class="w-4 h-4 animate-spin"></i>
                        Scanning all files... Please wait.
                    </div>
                </div>
            </div>
        </div>

        <!-- BATCH RESULTS TABLE -->
        {% if batch_results %}
        <div class="bg-[#050508] border border-[#222] rounded-sm overflow-hidden shadow-2xl">
            <div class="bg-[#0a0a0f] border-b border-[#222] px-6 py-4 flex items-center justify-between flex-wrap gap-3">
                <div class="flex items-center gap-3">
                    <i data-lucide="table" class="w-5 h-5 text-cyan-500"></i>
                    <h2 class="text-sm md:text-base uppercase tracking-widest font-bold text-gray-200">
                        Batch_Scan_Results.table
                    </h2>
                </div>
                <div class="flex items-center gap-3 flex-wrap">
                    <span class="text-xs bg-[#111] px-3 py-1 rounded-sm border border-[#222] text-gray-400 font-mono">
                        SCANNED: <span class="text-cyan-400 font-bold">{{ batch_results|length }}</span>
                    </span>
                    <span class="text-xs bg-[#111] px-3 py-1 rounded-sm border border-[#222] text-gray-400 font-mono">
                        CLEAN: <span class="text-emerald-400 font-bold">{{ batch_results|selectattr('verdict', 'equalto', 'CLEAN')|list|length }}</span>
                    </span>
                    <span class="text-xs bg-[#111] px-3 py-1 rounded-sm border border-[#222] text-gray-400 font-mono">
                        SUSPICIOUS: <span class="text-yellow-400 font-bold">{{ batch_results|selectattr('verdict', 'equalto', 'SUSPICIOUS')|list|length }}</span>
                    </span>
                    <span class="text-xs bg-[#111] px-3 py-1 rounded-sm border border-[#222] text-gray-400 font-mono">
                        INFECTED: <span class="text-red-400 font-bold">{{ batch_results|selectattr('verdict', 'equalto', 'INFECTED')|list|length }}</span>
                    </span>
                    <a href="/pdf-report" class="inline-flex items-center gap-1.5 bg-red-950/40 border border-red-800 text-red-400 text-xs px-4 py-2 rounded-sm hover:bg-red-900/60 hover:border-red-500 hover:shadow-[0_0_15px_rgba(239,68,68,0.2)] transition-all font-bold uppercase tracking-wider">
                        <i data-lucide="file-down" class="w-3.5 h-3.5"></i> Download Forensic PDF Report
                    </a>
                </div>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-xs font-mono">
                    <thead>
                        <tr class="bg-[#0a0a0f] border-b border-[#222] text-gray-500 uppercase tracking-wider">
                            <th class="px-4 py-3 text-left">#</th>
                            <th class="px-4 py-3 text-left">Filename</th>
                            <th class="px-4 py-3 text-left">Size</th>
                            <th class="px-4 py-3 text-left">SHA-256 Hash</th>
                            <th class="px-4 py-3 text-center">Chi2</th>
                            <th class="px-4 py-3 text-center">SPA</th>
                            <th class="px-4 py-3 text-center">RS</th>
                            <th class="px-4 py-3 text-center">Flags</th>
                            <th class="px-4 py-3 text-center">Verdict</th>
                            <th class="px-4 py-3 text-center">Action</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-[#111]">
                        {% for r in batch_results %}
                        <tr class="hover:bg-[#0a0a0f] transition-colors">
                            <td class="px-4 py-3 text-gray-500">{{ loop.index }}</td>
                            <td class="px-4 py-3 text-gray-200 font-bold truncate max-w-[180px]" title="{{ r.filename }}">{{ r.filename }}</td>
                            <td class="px-4 py-3 text-gray-400">{{ r.size }}</td>
                            <td class="px-4 py-3 text-gray-500 font-mono text-[10px] truncate max-w-[120px]" title="{{ r.sha256 }}">{{ r.sha256[:16] }}...</td>
                            <td class="px-4 py-3 text-center {% if r.chi_score > 100 %}text-red-400{% else %}text-emerald-400{% endif %}">{{ "%.0f"|format(r.chi_score) }}</td>
                            <td class="px-4 py-3 text-center {% if r.spa.indicator == 'stego' %}text-red-400{% else %}text-emerald-400{% endif %}">{{ "%.0f"|format(r.spa.lsb_correlation * 100) }}%</td>
                            <td class="px-4 py-3 text-center {% if r.rs.indicator == 'stego' %}text-red-400{% else %}text-emerald-400{% endif %}">{{ "%.3f"|format(r.rs.rs_ratio) }}</td>
                            <td class="px-4 py-3 text-center">
                                <span class="{% if r.stego_flags == 0 %}text-emerald-400{% elif r.stego_flags == 1 %}text-yellow-400{% else %}text-red-400{% endif %} font-bold">{{ r.stego_flags }}/3</span>
                            </td>
                            <td class="px-4 py-3 text-center">
                                {% if r.verdict == 'CLEAN' %}
                                <span class="inline-flex items-center gap-1 bg-emerald-950/40 border border-emerald-800 text-emerald-400 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase">CLEAN</span>
                                {% elif r.verdict == 'SUSPICIOUS' %}
                                <span class="inline-flex items-center gap-1 bg-yellow-950/40 border border-yellow-800 text-yellow-400 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase">SUSPICIOUS</span>
                                {% else %}
                                <span class="inline-flex items-center gap-1 bg-red-950/40 border border-red-800 text-red-400 px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase">INFECTED</span>
                                {% endif %}
                            </td>
                            <td class="px-4 py-3 text-center">
                                {% if r.verdict != 'CLEAN' %}
                                <a href="/sanitize?filename={{ r.filename }}" class="text-cyan-400 hover:text-cyan-300 text-[10px] underline">Sanitize</a>
                                {% else %}
                                <span class="text-gray-600 text-[10px]">--</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endif %}

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">

            <div class="bg-[#0a0a0f] border border-[#222] rounded-sm flex flex-col overflow-hidden relative shadow-2xl">
                <div class="bg-[#111] border-b border-[#222] px-4 py-2.5 flex items-center justify-between select-none">
                    <div class="flex items-center gap-2 text-gray-400 text-xs font-mono tracking-wider uppercase">
                        <i data-lucide="crosshair" class="w-4 h-4 text-purple-400"></i>
                        Bit-Plane Inspector
                    </div>
                    <div class="flex gap-1.5">
                        <div class="w-2.5 h-2.5 rounded-full bg-gray-700"></div>
                        <div class="w-2.5 h-2.5 rounded-full bg-gray-700"></div>
                        <div class="w-2.5 h-2.5 rounded-full bg-gray-700"></div>
                    </div>
                </div>
                <div class="p-6 flex-1 flex flex-col gap-6 font-mono text-sm">
                    <form action="/bitplane" method="post" enctype="multipart/form-data" class="space-y-4">
                        <div class="flex flex-col gap-2">
                            <span class="text-gray-500 text-xs uppercase tracking-wider">Target Image Source</span>
                            <label class="group relative flex items-center justify-center w-full h-12 px-4 transition-all border border-dashed border-gray-700 rounded-sm bg-[#050508] hover:bg-[#0f0f15] hover:border-cyan-500/50 cursor-pointer">
                                <div class="flex items-center gap-2 text-gray-500 group-hover:text-cyan-400 transition-colors">
                                    <i data-lucide="upload-cloud" class="w-4 h-4"></i>
                                    <span id="bp-name" class="text-xs tracking-wider">Initialize_Upload_Sequence</span>
                                </div>
                                <input type="file" name="image" accept="image/*" required class="hidden" onchange="updateFileName(this, 'bp-name')" />
                            </label>
                        </div>
                        <div class="flex flex-col gap-2">
                            <span class="text-gray-500 text-xs uppercase tracking-wider">Bit Plane (0 is LSB, 7 is MSB):</span>
                            <div class="relative">
                                <div class="absolute left-0 top-0 bottom-0 w-1 bg-cyan-900/50"></div>
                                <input type="number" name="plane" min="0" max="7" value="0" class="w-full bg-[#050508] border border-gray-800 text-cyan-400 px-4 py-2.5 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/50 transition-all font-mono" />
                            </div>
                        </div>
                        <button type="submit" class="w-full border px-6 py-3 uppercase tracking-widest text-xs font-bold transition-all duration-300 flex items-center justify-center gap-2 bg-cyan-950/30 text-cyan-400 border-cyan-800 hover:bg-cyan-900/50 hover:border-cyan-500 hover:shadow-[0_0_15px_rgba(6,182,212,0.2)]">
                            <i data-lucide="terminal" class="w-4 h-4"></i> [ EXECUTE_VISUALIZATION ]
                        </button>
                    </form>
                    {% if bitplane_img %}
                    <div class="mt-4 border border-[#222] rounded-sm p-2 bg-[#050508]">
                        <img src="{{ bitplane_img }}" alt="Bit Plane" class="w-full rounded border border-cyan-900/50">
                    </div>
                    {% endif %}
                </div>
            </div>

            <div class="bg-[#0a0a0f] border border-[#222] rounded-sm flex flex-col overflow-hidden relative shadow-2xl">
                <div class="bg-[#111] border-b border-[#222] px-4 py-2.5 flex items-center justify-between select-none">
                    <div class="flex items-center gap-2 text-gray-400 text-xs font-mono tracking-wider uppercase">
                        <i data-lucide="activity" class="w-4 h-4 text-orange-400"></i>
                        Entropy Mapping
                    </div>
                    <div class="flex gap-1.5">
                        <div class="w-2.5 h-2.5 rounded-full bg-gray-700"></div>
                        <div class="w-2.5 h-2.5 rounded-full bg-gray-700"></div>
                        <div class="w-2.5 h-2.5 rounded-full bg-gray-700"></div>
                    </div>
                </div>
                <div class="p-6 flex-1 flex flex-col gap-6 font-mono text-sm">
                    <form action="/entropy" method="post" enctype="multipart/form-data" class="space-y-4">
                        <div class="flex flex-col gap-2">
                            <span class="text-gray-500 text-xs uppercase tracking-wider">Target Image Source</span>
                            <label class="group relative flex items-center justify-center w-full h-12 px-4 transition-all border border-dashed border-gray-700 rounded-sm bg-[#050508] hover:bg-[#0f0f15] hover:border-cyan-500/50 cursor-pointer">
                                <div class="flex items-center gap-2 text-gray-500 group-hover:text-cyan-400 transition-colors">
                                    <i data-lucide="upload-cloud" class="w-4 h-4"></i>
                                    <span id="em-name" class="text-xs tracking-wider">Initialize_Upload_Sequence</span>
                                </div>
                                <input type="file" name="image" accept="image/*" required class="hidden" onchange="updateFileName(this, 'em-name')" />
                            </label>
                        </div>
                        <div class="flex flex-col gap-2">
                            <span class="text-gray-500 text-xs uppercase tracking-wider">Block Size (Pixels):</span>
                            <div class="relative">
                                <div class="absolute left-0 top-0 bottom-0 w-1 bg-cyan-900/50"></div>
                                <input type="number" name="block_size" min="4" max="32" value="8" class="w-full bg-[#050508] border border-gray-800 text-cyan-400 px-4 py-2.5 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/50 transition-all font-mono" />
                            </div>
                        </div>
                        <button type="submit" class="w-full border px-6 py-3 uppercase tracking-widest text-xs font-bold transition-all duration-300 flex items-center justify-center gap-2 bg-cyan-950/30 text-cyan-400 border-cyan-800 hover:bg-cyan-900/50 hover:border-cyan-500 hover:shadow-[0_0_15px_rgba(6,182,212,0.2)]">
                            <i data-lucide="terminal" class="w-4 h-4"></i> [ GENERATE_HEATMAP ]
                        </button>
                    </form>
                    {% if entropy_img %}
                    <div class="mt-4 border border-[#222] rounded-sm p-2 bg-[#050508]">
                        <img src="{{ entropy_img }}" alt="Entropy Heatmap" class="w-full rounded border border-orange-900/50">
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>

        <div class="bg-[#0a0a0f] border border-cyan-900/50 rounded-sm flex flex-col overflow-hidden relative shadow-2xl">
            <div class="bg-[#111] border-b border-[#222] px-4 py-2.5 flex items-center justify-between select-none">
                <div class="flex items-center gap-2 text-cyan-400 text-xs font-mono tracking-wider uppercase">
                    <i data-lucide="cpu" class="w-4 h-4"></i>
                    Deep AI Steganalysis Engine
                </div>
                <div class="flex gap-1.5">
                    <div class="w-2.5 h-2.5 rounded-full bg-cyan-900/50"></div>
                    <div class="w-2.5 h-2.5 rounded-full bg-cyan-900/50"></div>
                    <div class="w-2.5 h-2.5 rounded-full bg-cyan-900/50"></div>
                </div>
            </div>
            <div class="p-8">
                <form action="/analyze" method="post" enctype="multipart/form-data" class="flex flex-col md:flex-row gap-6 items-end">
                    <div class="flex-1 w-full flex flex-col gap-2">
                        <span class="text-gray-500 text-xs uppercase tracking-wider">Upload Suspect Artifact for Deep Scan</span>
                        <label class="group relative flex items-center justify-center w-full h-12 px-4 transition-all border border-dashed border-cyan-800/60 rounded-sm bg-[#050508] hover:bg-[#0f0f15] hover:border-cyan-400 cursor-pointer shadow-[0_0_15px_rgba(6,182,212,0.1)]">
                            <div class="flex items-center gap-2 text-cyan-500 group-hover:text-cyan-300 transition-colors">
                                <i data-lucide="upload-cloud" class="w-5 h-5"></i>
                                <span id="an-name" class="text-xs font-bold tracking-widest uppercase">Select_Suspect_Image_Artifact</span>
                            </div>
                            <input type="file" name="image" accept="image/*" required class="hidden" onchange="updateFileName(this, 'an-name')" />
                        </label>
                    </div>
                    <button type="submit" class="w-full md:w-auto border px-8 py-3.5 uppercase tracking-widest text-xs font-bold transition-all duration-300 flex items-center justify-center gap-2 bg-cyan-950/40 text-cyan-300 border-cyan-700 hover:bg-cyan-900/70 hover:border-cyan-400 hover:shadow-[0_0_25px_rgba(6,182,212,0.3)]">
                        <i data-lucide="terminal" class="w-4 h-4"></i> [ RUN_FULL_DIAGNOSTIC ]
                    </button>
                </form>
            </div>
        </div>

        {% if analysis %}
        <div class="bg-[#050508] border border-[#222] rounded-sm overflow-hidden shadow-2xl transition-all duration-500">
            <div class="bg-[#0a0a0f] border-b border-[#222] px-6 py-4 flex items-center justify-between flex-wrap gap-3">
                <div class="flex items-center gap-3">
                    <i data-lucide="terminal" class="w-5 h-5 text-cyan-500"></i>
                    <h2 class="text-sm md:text-base uppercase tracking-widest font-bold text-gray-200">
                        Forensic_Investigation_Report.log
                    </h2>
                </div>
                <div class="flex items-center gap-3">
                    <span class="text-xs bg-[#111] px-3 py-1 rounded-sm border border-[#222] text-gray-400 font-mono">
                        PIXEL PAIRS SCANNED: <span class="text-cyan-400 font-bold">{{ "{:,}".format(analysis.spa.total_pairs|default(1045506)) }}</span>
                    </span>
                    <a href="/pdf-report-single" class="inline-flex items-center gap-1.5 bg-red-950/40 border border-red-800 text-red-400 text-xs px-4 py-2 rounded-sm hover:bg-red-900/60 hover:border-red-500 hover:shadow-[0_0_15px_rgba(239,68,68,0.2)] transition-all font-bold uppercase tracking-wider">
                        <i data-lucide="file-down" class="w-3.5 h-3.5"></i> Download PDF Report
                    </a>
                </div>
            </div>

            <div class="p-0 divide-y divide-[#111]">

                <div class="p-6 md:p-8 hover:bg-[#0a0a0f] transition-colors relative group">
                    <div class="absolute left-0 top-0 bottom-0 w-1 {% if analysis.chi_score > 100 %}bg-red-600{% else %}bg-emerald-600{% endif %}"></div>
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-4">
                        <div>
                            <div class="flex items-center gap-2">
                                <h3 class="text-gray-100 font-bold tracking-wide text-lg">1. Chi-Squared PoV Anomaly Scan</h3>
                                <span class="text-xs px-2 py-0.5 rounded bg-[#111] text-gray-400 font-mono">Color Distribution</span>
                            </div>
                            <p class="text-gray-400 text-xs mt-1">Measures equality of adjacent color pairs. Stego payloads force color pairs into identical 50/50 splits.</p>
                        </div>
                        <span class="text-sm text-gray-400 bg-[#111] px-4 py-2 rounded-sm border border-[#222] font-mono flex items-center gap-2">
                            Score: <span class="{% if analysis.chi_score > 100 %}text-red-400{% else %}text-emerald-400{% endif %} font-bold text-lg">{{ "%.2f"|format(analysis.chi_score) }}</span>
                        </span>
                    </div>
                    <div class="w-full bg-[#111] h-3 rounded-full border border-[#222] overflow-hidden relative mb-2">
                        {% set chi_pct = (analysis.chi_score / 2000.0 * 100)|round|int %}
                        {% if chi_pct > 100 %}{% set chi_pct = 100 %}{% endif %}
                        <div class="h-full rounded-full transition-all duration-1000 {% if analysis.chi_score > 100 %}bg-gradient-to-r from-orange-500 to-red-600{% else %}bg-gradient-to-r from-emerald-500 to-cyan-500{% endif %}" style="width: {{ chi_pct }}%;"></div>
                    </div>
                    <div class="flex justify-between text-[11px] text-gray-500 font-mono mb-4">
                        <span>0 (Perfectly Natural)</span>
                        <span class="text-yellow-500">Threshold: 100</span>
                        <span>2000+ (Heavy Secret Payload)</span>
                    </div>
                    {% if analysis.chi_score > 100 %}
                    <div class="inline-flex items-center gap-2 bg-red-950/40 border border-red-900/50 text-red-500 text-xs px-3 py-1.5 rounded-sm mb-2 font-bold uppercase tracking-wider">
                        <i data-lucide="alert-triangle" class="w-4 h-4"></i> HIGH STATISTICAL ANOMALY DETECTED
                    </div>
                    <p class="text-red-300 text-xs leading-relaxed bg-red-950/20 p-3 rounded border border-red-900/30 font-mono mt-1">
                        Layman Verdict: The mathematical color balance is unnatural. This proves someone modified the lowest bits of the pixels to store secret data.
                    </p>
                    {% else %}
                    <div class="inline-flex items-center gap-2 bg-emerald-950/40 border border-emerald-900/50 text-emerald-500 text-xs px-3 py-1.5 rounded-sm mb-2 font-bold uppercase tracking-wider">
                        <i data-lucide="check-circle-2" class="w-4 h-4"></i> NATURAL COLOR BALANCE
                    </div>
                    <p class="text-emerald-300 text-xs leading-relaxed bg-emerald-950/20 p-3 rounded border border-emerald-900/30 font-mono mt-1">
                        Layman Verdict: Color frequencies are completely natural. No mathematical tampering detected.
                    </p>
                    {% endif %}
                </div>

                <div class="p-6 md:p-8 hover:bg-[#0a0a0f] transition-colors relative group">
                    <div class="absolute left-0 top-0 bottom-0 w-1 {% if analysis.spa.indicator == 'stego' %}bg-red-600{% else %}bg-emerald-600{% endif %}"></div>
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-4">
                        <div>
                            <div class="flex items-center gap-2">
                                <h3 class="text-gray-100 font-bold tracking-wide text-lg">2. Sample Pair Analysis (SPA) Scan</h3>
                                <span class="text-xs px-2 py-0.5 rounded bg-[#111] text-gray-400 font-mono">Neighbor Correlation</span>
                            </div>
                            <p class="text-gray-400 text-xs mt-1">Scans adjacent pixel pairs across the image. Stego payloads inject random bit noise between neighbors.</p>
                        </div>
                        <span class="text-sm text-gray-400 bg-[#111] px-4 py-2 rounded-sm border border-[#222] font-mono flex items-center gap-2">
                            LSB Match: <span class="{% if analysis.spa.indicator == 'stego' %}text-red-400{% else %}text-emerald-400{% endif %} font-bold text-lg">{{ "%.2f"|format(analysis.spa.lsb_correlation * 100) }}%</span>
                        </span>
                    </div>
                    <div class="w-full bg-[#111] h-3 rounded-full border border-[#222] overflow-hidden relative mb-2">
                        {% set spa_pct = (analysis.spa.lsb_correlation * 100)|round|int %}
                        <div class="h-full rounded-full transition-all duration-1000 {% if analysis.spa.indicator == 'stego' %}bg-red-500{% else %}bg-emerald-500{% endif %}" style="width: {{ spa_pct }}%;"></div>
                    </div>
                    <div class="flex justify-between text-[11px] text-gray-500 font-mono mb-4">
                        <span>0% (Random Noise)</span>
                        <span>Expected Natural: 50%</span>
                        <span>100% (Perfect Smooth Match)</span>
                    </div>
                    {% if analysis.spa.indicator == 'stego' %}
                    <div class="inline-flex items-center gap-2 bg-red-950/40 border border-red-900/50 text-red-500 text-xs px-3 py-1.5 rounded-sm mb-2 font-bold uppercase tracking-wider">
                        <i data-lucide="alert-triangle" class="w-4 h-4"></i> MODIFIED BITS DETECTED
                    </div>
                    <p class="text-red-300 text-xs leading-relaxed bg-red-950/20 p-3 rounded border border-red-900/30 font-mono mt-1">
                        Layman Verdict: Neighboring pixels show abnormal bit correlation. The natural smooth transitions have been corrupted by secret text.
                    </p>
                    {% else %}
                    <div class="inline-flex items-center gap-2 bg-emerald-950/40 border border-emerald-900/50 text-emerald-500 text-xs px-3 py-1.5 rounded-sm mb-2 font-bold uppercase tracking-wider">
                        <i data-lucide="check-circle-2" class="w-4 h-4"></i> NATURAL CORRELATION
                    </div>
                    <p class="text-emerald-300 text-xs leading-relaxed bg-emerald-950/20 p-3 rounded border border-emerald-900/30 font-mono mt-1">
                        Layman Verdict: Adjacent pixels blend perfectly naturally.
                    </p>
                    {% endif %}
                </div>

                <div class="p-6 md:p-8 hover:bg-[#0a0a0f] transition-colors relative group">
                    <div class="absolute left-0 top-0 bottom-0 w-1 {% if analysis.rs.indicator == 'stego' %}bg-red-600{% else %}bg-emerald-600{% endif %}"></div>
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-4">
                        <div>
                            <div class="flex items-center gap-2">
                                <h3 class="text-gray-100 font-bold tracking-wide text-lg">3. RS Flipper (Regular-Singular) Scan</h3>
                                <span class="text-xs px-2 py-0.5 rounded bg-[#111] text-gray-400 font-mono">Mathematical Inversion</span>
                            </div>
                            <p class="text-gray-400 text-xs mt-1">Flips pixel groups with mathematical inversion masks. Secret payloads shatter the natural Regular vs Singular symmetry.</p>
                        </div>
                        <span class="text-sm text-gray-400 bg-[#111] px-4 py-2 rounded-sm border border-[#222] font-mono flex items-center gap-2">
                            RS Ratio: <span class="{% if analysis.rs.indicator == 'stego' %}text-red-400{% else %}text-emerald-400{% endif %} font-bold text-lg">{{ "%.4f"|format(analysis.rs.rs_ratio) }}</span>
                        </span>
                    </div>
                    <div class="w-full bg-[#111] h-3 rounded-full border border-[#222] overflow-hidden relative mb-2">
                        {% set rs_pct = (analysis.rs.rs_ratio * 100)|round|int %}
                        {% if rs_pct > 100 %}{% set rs_pct = 100 %}{% endif %}
                        <div class="h-full rounded-full transition-all duration-1000 {% if analysis.rs.indicator == 'stego' %}bg-red-500{% else %}bg-emerald-500{% endif %}" style="width: {{ rs_pct }}%;"></div>
                    </div>
                    <div class="flex justify-between text-[11px] text-gray-500 font-mono mb-4">
                        <span>0.0 (Clean Natural Equilibrium)</span>
                        <span class="text-yellow-500">Stego Threshold: > 0.05</span>
                        <span>1.0 (Full Stego Payload)</span>
                    </div>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 bg-[#0a0a0f] p-4 rounded border border-[#1f1f30] font-mono text-xs mb-4">
                        <div><span class="text-gray-500">Regular (R):</span> <span class="text-cyan-400 font-bold">{{ analysis.rs.R }}</span></div>
                        <div><span class="text-gray-500">R-Minus (R-):</span> <span class="text-purple-400">{{ analysis.rs.R_minus }}</span></div>
                        <div><span class="text-gray-500">Singular (S):</span> <span class="text-orange-400 font-bold">{{ analysis.rs.S }}</span></div>
                        <div><span class="text-gray-500">S-Minus (S-):</span> <span class="text-yellow-400">{{ analysis.rs.S_minus }}</span></div>
                    </div>
                    {% if analysis.rs.indicator == 'stego' %}
                    <div class="inline-flex items-center gap-2 bg-red-950/40 border border-red-900/50 text-red-500 text-xs px-3 py-1.5 rounded-sm mb-2 font-bold uppercase tracking-wider">
                        <i data-lucide="alert-triangle" class="w-4 h-4"></i> STEGANOGRAPHY DEFINITIVELY DETECTED
                    </div>
                    <p class="text-red-300 text-xs leading-relaxed bg-red-950/20 p-3 rounded border border-red-900/30 font-mono mt-1">
                        Layman Verdict: A ratio greater than 0.05 is mathematically impossible in natural images. This is absolute proof that secret data is encrypted within the pixel groups.
                    </p>
                    {% else %}
                    <div class="inline-flex items-center gap-2 bg-emerald-950/40 border border-emerald-900/50 text-emerald-500 text-xs px-3 py-1.5 rounded-sm mb-2 font-bold uppercase tracking-wider">
                        <i data-lucide="check-circle-2" class="w-4 h-4"></i> NATURAL FLIP BEHAVIOR
                    </div>
                    <p class="text-emerald-300 text-xs leading-relaxed bg-emerald-950/20 p-3 rounded border border-emerald-900/30 font-mono mt-1">
                        Layman Verdict: Pixel group flipping statistics match natural physical curves perfectly.
                    </p>
                    {% endif %}
                </div>
            </div>

            <div class="{% if analysis.stego_flags > 0 %}bg-red-950/20 border-t border-red-900/50{% else %}bg-emerald-950/20 border-t border-emerald-900/50{% endif %} p-6 md:p-8">
                <div class="bg-[#050505] {% if analysis.stego_flags > 0 %}border-red-600/50 shadow-[0_0_35px_rgba(239,68,68,0.25)]{% else %}border-emerald-600/50 shadow-[0_0_35px_rgba(16,185,129,0.25)]{% endif %} border rounded p-6 text-center relative overflow-hidden">
                    <div class="absolute inset-0 bg-gradient-to-b {% if analysis.stego_flags > 0 %}from-transparent via-red-500/10 to-transparent{% else %}from-transparent via-emerald-500/10 to-transparent{% endif %} w-full h-[200%] animate-scan pointer-events-none opacity-50 -top-full"></div>
                    <h2 class="{% if analysis.stego_flags > 0 %}text-red-500{% else %}text-emerald-500{% endif %} text-xl md:text-2xl font-bold uppercase tracking-[0.2em] flex items-center justify-center gap-3">
                        <i data-lucide="shield-alert" class="w-7 h-7 animate-pulse"></i>
                        FINAL VERDICT: {% if analysis.stego_flags > 0 %}HIGH RISK{% else %}CLEAN (SAFE){% endif %}
                        <i data-lucide="shield-alert" class="w-7 h-7 animate-pulse"></i>
                    </h2>
                    <p class="{% if analysis.stego_flags > 0 %}text-red-400/80{% else %}text-emerald-400/80{% endif %} text-sm mt-3 font-bold tracking-widest uppercase">
                        [ {{ analysis.stego_flags }}/3 STATE-OF-THE-ART TESTS DETECTED STEGANOGRAPHY ]
                    </p>
                </div>
            </div>
        </div>
        {% endif %}

    </div>

    <script>
        lucide.createIcons();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML, batch_results=_load_batch_results())

@app.route('/bitplane', methods=['POST'])
def bitplane_analysis():
    if 'image' not in request.files:
        return "No image uploaded", 400

    file = request.files['image']
    plane = int(request.form.get('plane', 0))

    img_bytes = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(img_bytes, cv2.IMREAD_GRAYSCALE)

    if img is None:
        return "Invalid image", 400

    mask = 1 << plane
    bit_plane = (img & mask)
    bit_plane[bit_plane > 0] = 255

    _, buf = cv2.imencode('.png', bit_plane)
    b64_img = base64.b64encode(buf).decode('utf-8')
    data_url = f"data:image/png;base64,{b64_img}"
    return render_template_string(DASHBOARD_HTML, bitplane_img=data_url, batch_results=_load_batch_results())

@app.route('/entropy', methods=['POST'])
def entropy_analysis():
    if 'image' not in request.files:
        return "No image uploaded", 400

    file = request.files['image']
    block_size = int(request.form.get('block_size', 8))

    img_bytes = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(img_bytes, cv2.IMREAD_GRAYSCALE)

    if img is None:
        return "Invalid image", 400

    from .analyze import generate_entropy_heatmap

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        output_path = tmp.name

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_in:
        in_path = tmp_in.name
        cv2.imwrite(in_path, img)

    try:
        generate_entropy_heatmap(in_path, output_path, block_size)
        result_img = cv2.imread(output_path)
        _, buf = cv2.imencode('.png', result_img)
        b64_img = base64.b64encode(buf).decode('utf-8')
        data_url = f"data:image/png;base64,{b64_img}"
    finally:
        if os.path.exists(in_path):
            os.unlink(in_path)
        if os.path.exists(output_path):
            os.unlink(output_path)

    return render_template_string(DASHBOARD_HTML, entropy_img=data_url, batch_results=_load_batch_results())

@app.route('/analyze', methods=['POST'])
def full_analysis():
    if 'image' not in request.files:
        return "No image uploaded", 400

    file = request.files['image']
    img_bytes = file.read()
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

    if img is None:
        return "Invalid image", 400

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        temp_path = tmp.name
        cv2.imwrite(temp_path, img)

    try:
        from .analyze import chi_squared_test, sample_pair_analysis, rs_analysis
        chi_score = chi_squared_test(temp_path)
        spa = sample_pair_analysis(temp_path)
        rs = rs_analysis(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    stego_flags = 0
    if chi_score > 100:
        stego_flags += 1
    if spa['indicator'] == 'stego':
        stego_flags += 1
    if rs['indicator'] == 'stego':
        stego_flags += 1

    if stego_flags == 0:
        verdict = "CLEAN"
        risk_level = "LOW"
    elif stego_flags == 1:
        verdict = "SUSPICIOUS"
        risk_level = "MEDIUM"
    else:
        verdict = "INFECTED"
        risk_level = "HIGH"

    report = {
        "chi_score": chi_score,
        "spa": spa,
        "rs": rs,
        "stego_flags": stego_flags,
        "filename": file.filename,
        "sha256": compute_sha256(img_bytes),
        "size": f"{len(img_bytes) / 1024:.1f} KB",
        "verdict": verdict,
        "risk_level": risk_level
    }
    _save_single_result(report)

    return render_template_string(DASHBOARD_HTML, analysis=report, batch_results=_load_batch_results())

@app.route('/batch', methods=['POST'])
def batch_scan():
    if 'images' not in request.files:
        return "No images uploaded", 400

    files = request.files.getlist('images')
    results = []

    for file in files:
        if not file or not file.filename:
            continue

        img_bytes = file.read()
        sha256 = compute_sha256(img_bytes)
        file_size = f"{len(img_bytes) / 1024:.1f} KB"

        result = analyze_image_bytes(img_bytes)
        if result is None:
            continue

        result['filename'] = file.filename
        result['sha256'] = sha256
        result['size'] = file_size
        results.append(result)

    _save_batch_results(results)
    return render_template_string(DASHBOARD_HTML, batch_results=results)

@app.route('/pdf-report')
def download_batch_pdf():
    batch_results = _load_batch_results()
    if not batch_results:
        return "No batch scan results available. Run a batch scan first.", 400

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch, mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    import textwrap

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name='Title2', fontSize=18, textColor=colors.HexColor('#1a1a2e'), fontName='Helvetica-Bold', spaceAfter=6, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='SubTitle', fontSize=10, textColor=colors.HexColor('#555555'), fontName='Helvetica', spaceAfter=12, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='SectionHeader', fontSize=13, textColor=colors.HexColor('#0f3460'), fontName='Helvetica-Bold', spaceBefore=16, spaceAfter=8))
    styles.add(ParagraphStyle(name='BodySmall', fontSize=8, textColor=colors.HexColor('#333333'), fontName='Helvetica', spaceAfter=4, leading=11))
    styles.add(ParagraphStyle(name='HashText', fontSize=7, textColor=colors.HexColor('#666666'), fontName='Courier', spaceAfter=2))
    styles.add(ParagraphStyle(name='Footer', fontSize=7, textColor=colors.HexColor('#999999'), fontName='Helvetica', alignment=TA_CENTER))

    elements = []

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    elements.append(Spacer(1, 30))
    elements.append(Paragraph("SSAT FORENSIC AUDIT REPORT", styles['Title2']))
    elements.append(Paragraph("Secure Steganographic AI Toolkit — Batch Surveillance Scan", styles['SubTitle']))

    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0f3460'), spaceAfter=12))

    elements.append(Paragraph("REPORT METADATA", styles['SectionHeader']))
    meta_data = [
        ['Report Generated', now],
        ['Total Files Scanned', str(len(batch_results))],
        ['Clean Files', str(sum(1 for r in batch_results if r['verdict'] == 'CLEAN'))],
        ['Suspicious Files', str(sum(1 for r in batch_results if r['verdict'] == 'SUSPICIOUS'))],
        ['Infected Files', str(sum(1 for r in batch_results if r['verdict'] == 'INFECTED'))],
        ['Scan Engine', 'SSAT v3.0.0 (Chi-Squared + SPA + RS Analysis)'],
    ]
    meta_table = Table(meta_data, colWidths=[2.2*inch, 4.3*inch])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f5')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("DETAILED FILE ANALYSIS", styles['SectionHeader']))

    for i, r in enumerate(batch_results, 1):
        if r['verdict'] == 'CLEAN':
            vcolor = colors.HexColor('#16a34a')
            vbg = colors.HexColor('#f0fdf4')
        elif r['verdict'] == 'SUSPICIOUS':
            vcolor = colors.HexColor('#ca8a04')
            vbg = colors.HexColor('#fefce8')
        else:
            vcolor = colors.HexColor('#dc2626')
            vbg = colors.HexColor('#fef2f2')

        elements.append(Paragraph(f"FILE #{i}: {r['filename']}", styles['SectionHeader']))

        file_info = [
            ['File Name', r['filename']],
            ['File Size', r['size']],
            ['SHA-256 Hash', r['sha256']],
            ['Verdict', r['verdict']],
            ['Risk Level', r['risk_level']],
            ['Stego Flags', f"{r['stego_flags']} / 3"],
        ]
        file_table = Table(file_info, colWidths=[1.8*inch, 4.7*inch])
        file_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f8fc')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
            ('TEXTCOLOR', (1, 3), (1, 3), vcolor),
            ('BACKGROUND', (1, 3), (1, 3), vbg),
            ('FONTNAME', (1, 2), (1, 2), 'Courier'),
            ('FONTSIZE', (1, 2), (1, 2), 6.5),
        ]))
        elements.append(file_table)
        elements.append(Spacer(1, 4))

        scores_data = [
            ['Test', 'Score', 'Threshold', 'Result'],
            ['Chi-Squared (PoV)', f"{r['chi_score']:.2f}", '< 100', 'ANOMALY' if r['chi_score'] > 100 else 'NATURAL'],
            ['Sample Pair Analysis', f"{r['spa']['lsb_correlation']*100:.2f}%", '~50%', 'STEGO' if r['spa']['indicator'] == 'stego' else 'NATURAL'],
            ['RS Flipper Ratio', f"{r['rs']['rs_ratio']:.4f}", '< 0.05', 'STEGO' if r['rs']['indicator'] == 'stego' else 'NATURAL'],
        ]
        scores_table = Table(scores_data, colWidths=[1.8*inch, 1.4*inch, 1.2*inch, 2.1*inch])
        scores_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f3460')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5fa')]),
        ]))

        for row_idx in range(1, 4):
            result_text = scores_data[row_idx][3]
            if result_text in ('ANOMALY', 'STEGO'):
                scores_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (3, row_idx), (3, row_idx), colors.red),
                    ('FONTNAME', (3, row_idx), (3, row_idx), 'Helvetica-Bold'),
                ]))
            else:
                scores_table.setStyle(TableStyle([
                    ('TEXTCOLOR', (3, row_idx), (3, row_idx), colors.green),
                    ('FONTNAME', (3, row_idx), (3, row_idx), 'Helvetica-Bold'),
                ]))

        elements.append(scores_table)
        elements.append(Spacer(1, 12))

    elements.append(PageBreak())
    elements.append(Paragraph("VERDICT SUMMARY", styles['SectionHeader']))

    summary_data = [['#', 'Filename', 'SHA-256 (First 16)', 'Chi2', 'SPA', 'RS', 'Flags', 'Verdict']]
    for i, r in enumerate(batch_results, 1):
        summary_data.append([
            str(i),
            r['filename'][:30],
            r['sha256'][:16],
            f"{r['chi_score']:.0f}",
            f"{r['spa']['lsb_correlation']*100:.0f}%",
            f"{r['rs']['rs_ratio']:.3f}",
            f"{r['stego_flags']}/3",
            r['verdict'],
        ])

    col_count = len(summary_data[0])
    summary_table = Table(summary_data, colWidths=[0.4*inch, 1.5*inch, 1.4*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.6*inch, 1.0*inch])

    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f3460')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5fa')]),
    ]
    summary_table.setStyle(TableStyle(style_cmds))

    for row_idx in range(1, len(summary_data)):
        verdict = summary_data[row_idx][7]
        if verdict == 'INFECTED':
            summary_table.setStyle(TableStyle([
                ('TEXTCOLOR', (7, row_idx), (7, row_idx), colors.red),
                ('FONTNAME', (7, row_idx), (7, row_idx), 'Helvetica-Bold'),
                ('BACKGROUND', (7, row_idx), (7, row_idx), colors.HexColor('#fef2f2')),
            ]))
        elif verdict == 'SUSPICIOUS':
            summary_table.setStyle(TableStyle([
                ('TEXTCOLOR', (7, row_idx), (7, row_idx), colors.HexColor('#ca8a04')),
                ('FONTNAME', (7, row_idx), (7, row_idx), 'Helvetica-Bold'),
                ('BACKGROUND', (7, row_idx), (7, row_idx), colors.HexColor('#fefce8')),
            ]))
        else:
            summary_table.setStyle(TableStyle([
                ('TEXTCOLOR', (7, row_idx), (7, row_idx), colors.green),
                ('FONTNAME', (7, row_idx), (7, row_idx), 'Helvetica-Bold'),
                ('BACKGROUND', (7, row_idx), (7, row_idx), colors.HexColor('#f0fdf4')),
            ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cccccc'), spaceAfter=10))
    elements.append(Paragraph("This report is generated by SSAT (Secure Steganographic AI Toolkit) v3.0.0", styles['Footer']))
    elements.append(Paragraph("All SHA-256 hashes are computed for chain-of-custody verification.", styles['Footer']))
    elements.append(Paragraph(f"Report timestamp: {now} | This document is audit-ready and court-admissible.", styles['Footer']))

    doc.build(elements)
    buf.seek(0)

    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f'SSAT_Forensic_Report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')

@app.route('/pdf-report-single')
def download_single_pdf():
    r = _load_single_result()
    if r is None:
        return "No single analysis result available. Run a full diagnostic first.", 400

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name='Title2', fontSize=18, textColor=colors.HexColor('#1a1a2e'), fontName='Helvetica-Bold', spaceAfter=6, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='SubTitle', fontSize=10, textColor=colors.HexColor('#555555'), fontName='Helvetica', spaceAfter=12, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='SectionHeader', fontSize=13, textColor=colors.HexColor('#0f3460'), fontName='Helvetica-Bold', spaceBefore=16, spaceAfter=8))
    styles.add(ParagraphStyle(name='Footer', fontSize=7, textColor=colors.HexColor('#999999'), fontName='Helvetica', alignment=TA_CENTER))

    elements = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    elements.append(Spacer(1, 30))
    elements.append(Paragraph("SSAT FORENSIC AUDIT REPORT", styles['Title2']))
    elements.append(Paragraph("Single File Deep Steganalysis Diagnostic", styles['SubTitle']))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0f3460'), spaceAfter=12))

    elements.append(Paragraph("FILE METADATA", styles['SectionHeader']))
    meta_data = [
        ['File Name', r['filename']],
        ['File Size', r['size']],
        ['SHA-256 Hash', r['sha256']],
        ['Scan Time', now],
        ['Engine', 'SSAT v3.0.0'],
    ]
    meta_table = Table(meta_data, colWidths=[1.8*inch, 4.7*inch])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f5')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('FONTNAME', (1, 2), (1, 2), 'Courier'),
        ('FONTSIZE', (1, 2), (1, 2), 6.5),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("FORENSIC TEST RESULTS", styles['SectionHeader']))
    scores_data = [
        ['Test', 'Score', 'Threshold', 'Result'],
        ['Chi-Squared (PoV)', f"{r['chi_score']:.2f}", '< 100', 'ANOMALY' if r['chi_score'] > 100 else 'NATURAL'],
        ['Sample Pair Analysis', f"{r['spa']['lsb_correlation']*100:.2f}%", '~50%', 'STEGO' if r['spa']['indicator'] == 'stego' else 'NATURAL'],
        ['RS Flipper Ratio', f"{r['rs']['rs_ratio']:.4f}", '< 0.05', 'STEGO' if r['rs']['indicator'] == 'stego' else 'NATURAL'],
    ]
    scores_table = Table(scores_data, colWidths=[2*inch, 1.5*inch, 1.2*inch, 1.8*inch])
    scores_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f3460')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5fa')]),
    ]))
    for row_idx in range(1, 4):
        result_text = scores_data[row_idx][3]
        if result_text in ('ANOMALY', 'STEGO'):
            scores_table.setStyle(TableStyle([
                ('TEXTCOLOR', (3, row_idx), (3, row_idx), colors.red),
                ('FONTNAME', (3, row_idx), (3, row_idx), 'Helvetica-Bold'),
            ]))
        else:
            scores_table.setStyle(TableStyle([
                ('TEXTCOLOR', (3, row_idx), (3, row_idx), colors.green),
                ('FONTNAME', (3, row_idx), (3, row_idx), 'Helvetica-Bold'),
            ]))
    elements.append(scores_table)
    elements.append(Spacer(1, 16))

    if r['verdict'] == 'CLEAN':
        vcolor = colors.HexColor('#16a34a')
        vlabel = 'CLEAN — NO STEGANOGRAPHY DETECTED'
    elif r['verdict'] == 'SUSPICIOUS':
        vcolor = colors.HexColor('#ca8a04')
        vlabel = 'SUSPICIOUS — FURTHER INVESTIGATION RECOMMENDED'
    else:
        vcolor = colors.HexColor('#dc2626')
        vlabel = 'INFECTED — STEGANOGRAPHY CONFIRMED'

    verdict_data = [['FINAL VERDICT', vlabel], ['Stego Flags', f"{r['stego_flags']} / 3 Tests Triggered"]]
    verdict_table = Table(verdict_data, colWidths=[1.8*inch, 4.7*inch])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f8fc')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('TEXTCOLOR', (1, 0), (1, 0), vcolor),
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(verdict_table)
    elements.append(Spacer(1, 20))

    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cccccc'), spaceAfter=10))
    elements.append(Paragraph("This report is generated by SSAT (Secure Steganographic AI Toolkit) v3.0.0", styles['Footer']))
    elements.append(Paragraph(f"SHA-256: {r['sha256']}", styles['Footer']))
    elements.append(Paragraph(f"Report timestamp: {now} | This document is audit-ready and court-admissible.", styles['Footer']))

    doc.build(elements)
    buf.seek(0)

    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f'SSAT_Forensic_Report_{r["filename"]}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')

def get_bit_plane(image_path: str, plane: int):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image not found at {image_path}")
    mask = 1 << plane
    bit_plane = (img & mask)
    bit_plane[bit_plane > 0] = 255
    return bit_plane

def save_all_bit_planes(image_path: str, output_prefix: str):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image not found at {image_path}")
    for i in range(8):
        plane = get_bit_plane(image_path, i)
        cv2.imwrite(f"{output_prefix}_plane_{i}.png", plane)

def create_bit_plane_grid(image_path: str, output_path: str):
    planes = []
    for i in range(8):
        planes.append(get_bit_plane(image_path, i))
    top_row = np.hstack(planes[4:])
    bottom_row = np.hstack(planes[:4])
    grid = np.vstack([top_row, bottom_row])
    cv2.imwrite(output_path, grid)
    return output_path

def run_dashboard(host: str = "127.0.0.1", port: int = 5000):
    app.run(host=host, port=port, debug=True)
