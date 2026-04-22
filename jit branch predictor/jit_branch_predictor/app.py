# -*- coding: utf-8 -*-
"""
app.py  --  JIT Branch Predictor Dynamic UI
============================================
Paste Python/C/Java code -> generates RISC-V traces -> runs real Verilog simulation -> comparison.
Usage:  python app.py   then open http://localhost:5173
"""

import ast
import os
import re
import csv
import sys
import json
import subprocess
import io
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────
PROJ_DIR  = os.path.dirname(os.path.abspath(__file__))
TRACE_DIR = os.path.join(PROJ_DIR, "tb", "traces")
SIM_EXE   = os.path.join(PROJ_DIR, "dynamic_sim.exe")
NAIVE_MEM = os.path.join(TRACE_DIR, "user_naive.mem")
JIT_MEM   = os.path.join(TRACE_DIR, "user_jit.mem")

VERILOG_FILES = [
    "tb/tb_dynamic.v",
    "top.v",
    "pipeline/if_stage.v",
    "pipeline/if_id_reg.v",
    "pipeline/id_stage.v",
    "pipeline/id_ex_reg.v",
    "pipeline/ex_stage.v",
    "pipeline/ex_mem_reg.v",
    "pipeline/mem_wb_stage.v",
    "pipeline/register_file.v",
    "pipeline/alu.v",
    "pipeline/hazard_unit.v",
    "pipeline/forwarding_unit.v",
    "pipeline/flush_control.v",
    "predictors/predictor_if.v",
    "predictors/pred_static.v",
    "predictors/pred_1bit.v",
    "predictors/pred_2bit.v",
    "predictors/pred_ghr.v",
    "memory/instr_mem.v",
    "memory/data_mem.v",
]

TAKEN     = "00000463"   # BEQ x0,x0,+8  -> always TAKEN  (x0==x0 always true, BEQ)
NOT_TAKEN = "00001063"   # BNE x0,x0,+0  -> never TAKEN   (x0!=x0 always false, BNE)
NOP       = "00000013"   # ADDI x0,x0,0  -> no-op

# ─────────────────────────────────────────────────────────────
# Code Analysis
# ─────────────────────────────────────────────────────────────
def analyze_code(code):
    """
    Analyzes source code to extract branch-relevant patterns.
    Returns a dict with detected constructs and their complexity.
    Also classifies each for-loop as 'sorted' (predictable) or 'random' (unpredictable)
    based on whether sorted()/random.shuffle() calls appear near the loop.
    """
    result = {
        "for_loops": [], "while_loops": 0, "if_chains": [],
        "isinstance_calls": 0, "try_blocks": 0, "language": "unknown",
        "errors": [], "has_sorting": False, "has_shuffle": False,
        "nested_loops": 0,
    }
    try:
        tree = ast.parse(code)
        result["language"] = "Python"

        # Detect sorting / shuffle calls anywhere in the code
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = (func.id if isinstance(func, ast.Name)
                        else func.attr if isinstance(func, ast.Attribute) else "")
                if name in ("sorted", "sort"):
                    result["has_sorting"] = True
                if name in ("shuffle", "sample", "randint", "random", "choice"):
                    result["has_shuffle"] = True
                if name in ("isinstance", "type", "issubclass"):
                    result["isinstance_calls"] += 1
            elif isinstance(node, ast.Try):
                result["try_blocks"] += 1

        # Walk for loops and if-chains
        def _count_for_depth(node, depth=0):
            """Count max nesting depth of For loops."""
            if isinstance(node, ast.For):
                depth += 1
            best = depth
            for child in ast.iter_child_nodes(node):
                best = max(best, _count_for_depth(child, depth))
            return best

        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                iters = 10
                if isinstance(node.iter, ast.Call):
                    func = node.iter.func
                    fname = (func.id if isinstance(func, ast.Name)
                             else func.attr if isinstance(func, ast.Attribute) else "")
                    if fname == "range":
                        args = node.iter.args
                        try:
                            if len(args) == 1 and isinstance(args[0], ast.Constant):
                                iters = int(args[0].value)
                            elif len(args) >= 2:
                                a, b = args[0], args[1]
                                if isinstance(a, ast.Constant) and isinstance(b, ast.Constant):
                                    iters = int(b.value) - int(a.value)
                        except Exception:
                            pass
                result["for_loops"].append(min(max(iters, 2), 16))
            elif isinstance(node, ast.While):
                result["while_loops"] += 1
            elif isinstance(node, ast.If):
                chain = 1
                curr = node
                while (curr.orelse and len(curr.orelse) == 1
                       and isinstance(curr.orelse[0], ast.If)):
                    chain += 1
                    curr = curr.orelse[0]
                result["if_chains"].append(chain)

        # Detect nested loops (increases overhead)
        result["nested_loops"] = max(0, _count_for_depth(tree) - 1)
        return result
    except SyntaxError as e:
        py_err = f"Python Syntax Error: {e.msg} at line {e.lineno}"

    # ── C / Java fallback ──────────────────────────────────────
    # Check if it looks like C/Java. If not, return the Python error instead of silently falling back.
    if not re.search(r'#include|int\s+main|void\s+|public\s+class|\{', code):
        return {"error": py_err}

    result["language"] = "C/Java"
    for _ in re.findall(r'\bfor\b\s*\(', code):
        result["for_loops"].append(8)
    result["while_loops"] = len(re.findall(r'\bwhile\b\s*\(', code))
    lines = code.splitlines()
    chain = 0
    for line in lines:
        s = line.strip()
        if re.match(r'^(if)\s*[\(\s]', s):
            if chain > 0:
                result["if_chains"].append(chain)
            chain = 1
        elif re.match(r'^else\s+if\s*\(|^elif\s', s):
            chain += 1
        elif chain > 0 and not re.match(r'^else\b', s) and s:
            result["if_chains"].append(chain)
            chain = 0
    if chain > 0:
        result["if_chains"].append(chain)
    result["isinstance_calls"] = len(
        re.findall(r'\b(instanceof|isinstance|getClass|typeOf)\b', code))
    result["try_blocks"] = len(re.findall(r'\btry\b\s*\{?', code))
    if re.search(r'\b(sort|Arrays\.sort|Collections\.sort)\b', code):
        result["has_sorting"] = True
    if re.search(r'\b(shuffle|random|rand)\b', code):
        result["has_shuffle"] = True
    return result

# ─────────────────────────────────────────────────────────────
# Trace Generation
# ─────────────────────────────────────────────────────────────
def _pad(instructions):
    while len(instructions) < 256:
        instructions.append(NOP)
    return instructions[:256]


def _alt(i):
    """Alternating branch: even=TAKEN, odd=NOT_TAKEN."""
    return TAKEN if i % 2 == 0 else NOT_TAKEN


def generate_naive_trace(analysis):
    """
    COA NAIVE TRACE (Interpreter Model)
    Python interpreter executes a massive switch statement (dispatch loop).
    Every logical operation has 3-4 unpredictable overhead branches.
    """
    instr = []
    c = [0]
    def alt():
        v = TAKEN if c[0] % 2 == 0 else NOT_TAKEN
        c[0] += 1
        return v

    for iters in analysis["for_loops"]:
        for i in range(max(iters, 2)):
            # Interpreter overhead: Fetch, Decode, Type Check
            instr += [NOP, alt(), NOP, alt(), NOP, alt()]
            # Logical branch
            instr += [NOP, NOP, TAKEN if i < max(iters, 2) - 1 else NOT_TAKEN]

    for _ in range(analysis["while_loops"]):
        for i in range(8):
            instr += [NOP, alt(), NOP, alt()]
            instr += [NOP, TAKEN if i < 7 else NOT_TAKEN]

    for chain_len in analysis["if_chains"]:
        for _ in range(max(chain_len, 1)):
            instr += [NOP, alt(), NOP, alt()]
            instr += [NOP, alt()]

    for _ in range(analysis["isinstance_calls"]):
        instr += [NOP, alt(), NOP, alt(), NOP, alt(), NOP, alt()]

    for _ in range(analysis["try_blocks"]):
        instr += [NOP, alt(), NOP, alt()]

    if len(instr) < 10:
        for _ in range(16):
            instr += [NOP, NOP, alt()]

    return _pad(instr)

def generate_jit_trace(analysis):
    """
    COA JIT-OPTIMIZED TRACE
    Models JIT compiled code:
    1. Loop overhead is gone. Backward branches remain but are clean.
    2. Polymorphic Inline Caches (PICs) for type checks: correlated branches
       that alternate, defeating Static/2-bit but perfectly predicted by GHR.
    """
    instr = []
    c = [0]
    def alt():
        v = TAKEN if c[0] % 2 == 0 else NOT_TAKEN
        c[0] += 1
        return v

    for iters in analysis["for_loops"]:
        n = max(iters, 2)
        for i in range(n):
            instr += [NOP, NOP, NOP]
            # Clean backward branch
            instr.append(TAKEN if i < n - 1 else NOT_TAKEN)

    for _ in range(analysis["while_loops"]):
        for i in range(8):
            instr += [NOP, NOP]
            instr.append(TAKEN if i < 7 else NOT_TAKEN)

    for chain_len in analysis["if_chains"]:
        for _ in range(max(chain_len, 1)):
            # Complex data-dependent branch
            instr += [NOP, alt()]

    for _ in range(analysis["isinstance_calls"]):
        # Polymorphic Inline Cache (PIC) checks
        instr += [NOP] * 63 + [alt()]

    for _ in range(analysis["try_blocks"]):
        # Zero-cost exceptions (no branch on hot path)
        instr += [NOP, NOT_TAKEN]

    if len(instr) < 10:
        for _ in range(16):
            instr += [NOP, alt()]

    return _pad(instr)

def write_trace(path, instructions):
    with open(path, "w") as f:
        for word in instructions:
            f.write(word + "\n")

# ─────────────────────────────────────────────────────────────
# Simulation Runner
# ─────────────────────────────────────────────────────────────
_compile_lock = threading.Lock()
_compiled = False

def ensure_compiled():
    global _compiled
    with _compile_lock:
        if _compiled:
            return True
        files = [os.path.join(PROJ_DIR, f) for f in VERILOG_FILES]
        cmd = ["iverilog", "-o", SIM_EXE] + files
        r = subprocess.run(cmd, capture_output=True, cwd=PROJ_DIR)
        if r.returncode != 0:
            print("Compile FAILED:", r.stderr.decode("utf-8", errors="replace"))
            return False
        _compiled = True
        return True

def run_simulation():
    r = subprocess.run(["vvp", SIM_EXE], capture_output=True, cwd=PROJ_DIR)
    return r.stdout.decode("utf-8", errors="replace")

def parse_csv(sim_output):
    lines = sim_output.splitlines()
    in_csv, csv_lines = False, []
    for line in lines:
        line = line.strip()
        if "DYNAMIC_CSV_START" in line: in_csv = True; continue
        if "DYNAMIC_CSV_END"   in line: break
        if in_csv: csv_lines.append(line)
    if not csv_lines: return None
    reader = csv.DictReader(io.StringIO("\n".join(csv_lines)))
    return list(reader)

def count_branch_stats(instructions):
    taken = instructions.count(TAKEN)
    nt    = instructions.count(NOT_TAKEN)
    total = taken + nt
    return {
        "total_instructions": len(instructions),
        "total_branches": total,
        "taken": taken,
        "not_taken": nt,
        "branch_density": round(100 * total / len(instructions), 1) if instructions else 0,
        "taken_ratio": round(100 * taken / total, 1) if total else 0,
    }

def simulate(code):
    if not code.strip():
        return {"error": "Input code is empty. Please provide valid Python, C, or Java code."}

    analysis   = analyze_code(code)
    if "error" in analysis:
        return analysis

    naive_trace = generate_naive_trace(analysis)
    jit_trace   = generate_jit_trace(analysis)
    os.makedirs(TRACE_DIR, exist_ok=True)
    write_trace(NAIVE_MEM, naive_trace)
    write_trace(JIT_MEM,   jit_trace)
    if not ensure_compiled():
        return {"error": "Verilog compilation failed. Is iverilog installed and in PATH?"}
    sim_out = run_simulation()
    rows    = parse_csv(sim_out)
    if not rows:
        return {"error": "Simulation produced no CSV output. Check iverilog/vvp installation."}
    return {
        "analysis":     analysis,
        "naive_stats":  count_branch_stats(naive_trace),
        "jit_stats":    count_branch_stats(jit_trace),
        "rows":         rows,
        "naive_preview": "\n".join(naive_trace[:32]) + ("\n..." if len(naive_trace) > 32 else ""),
        "jit_preview":   "\n".join(jit_trace[:32])   + ("\n..." if len(jit_trace)   > 32 else ""),
    }

# ─────────────────────────────────────────────────────────────
# HTML UI
# ─────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JIT Branch Predictor &mdash; Dynamic Analyzer</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {
  --bg:     #0B0D1A;
  --surf:   #10132A;
  --card:   #161A2E;
  --card2:  #1C2038;
  --bdr:    #242840;
  --acc:    #7C6FFF;
  --green:  #00D4AA;
  --red:    #FF4466;
  --orange: #FF9944;
  --blue:   #44BBFF;
  --txt:    #DDE4F5;
  --muted:  #6B77A0;
  --r:      10px;
}
*  { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  height: 100%;
  overflow: hidden;
}
body {
  background: var(--bg);
  color: var(--txt);
  font-family: 'Inter', system-ui, sans-serif;
}

/* ── HEADER ──────────────────────────────── */
header {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--surf);
  border-bottom: 1px solid var(--bdr);
  z-index: 20;
}
.logo          { display: flex; align-items: center; gap: 10px; }
.logo-chip     { background: linear-gradient(135deg,#7C6FFF,#AA55FF); color: #fff; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; padding: 4px 9px; border-radius: 6px; }
.logo-title    { font-weight: 700; font-size: 14px; }
.header-hint   { font-size: 11px; color: var(--muted); }

/* ── MAIN ─────────────────────────────────── */
/* Fixed from below-header to bottom — gives both panels an exact known height */
.main {
  position: fixed;
  top: 52px; left: 0; right: 0; bottom: 0;
  display: flex;
  overflow: hidden;
}

/* ── EDITOR PANEL ────────────────────────── */
.ep {
  width: 360px;
  flex: 0 0 360px;           /* exact width, never shrink/grow */
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--surf);
  border-right: 1px solid var(--bdr);
}
.ep-hdr {
  flex-shrink: 0;
  padding: 9px 14px;
  border-bottom: 1px solid var(--bdr);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ep-label   { font-size: 10px; font-weight: 700; letter-spacing: 1px; color: var(--muted); text-transform: uppercase; }
.lang-tag   { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; background: rgba(124,111,255,.15); color: var(--acc); border: 1px solid rgba(124,111,255,.3); }
#code {
  flex: 1;
  min-height: 0;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  color: #C5D0E8;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12.5px;
  line-height: 1.75;
  padding: 14px;
  tab-size: 4;
  overflow-y: auto;
}
#code::placeholder { color: #252A45; }
.ep-badges {
  flex-shrink: 0;
  padding: 8px 12px;
  border-top: 1px solid var(--bdr);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 38px;
  align-items: center;
}
.badge { font-size: 10.5px; padding: 3px 9px; border-radius: 5px; font-weight: 500; }
.bl  { background: rgba(0,212,170,.1);  color: var(--green);  border: 1px solid rgba(0,212,170,.25); }
.bb  { background: rgba(255,153,68,.1); color: var(--orange); border: 1px solid rgba(255,153,68,.25); }
.bt  { background: rgba(255,68,102,.1); color: var(--red);    border: 1px solid rgba(255,68,102,.25); }
.run-btn {
  flex-shrink: 0;
  margin: 10px 14px;
  padding: 12px;
  border: none;
  border-radius: var(--r);
  background: linear-gradient(135deg, #7C6FFF, #AA44FF);
  color: #fff;
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: opacity .2s, transform .15s, box-shadow .2s;
}
.run-btn:hover   { opacity:.9; transform: translateY(-1px); box-shadow: 0 6px 24px rgba(124,111,255,.45); }
.run-btn:active  { transform: translateY(0); }
.run-btn:disabled { opacity: .4; cursor: not-allowed; transform: none; box-shadow: none; }

/* ── RESULTS PANEL ───────────────────────── */
/* flex:1 fills remaining width; height is inherited from fixed .main */
.rp {
  flex: 1;
  overflow-y: scroll;      /* always show scrollbar — forces scroll context */
  overflow-x: hidden;
  padding: 18px 20px 60px;
}
.rp::-webkit-scrollbar       { width: 6px; }
.rp::-webkit-scrollbar-track { background: rgba(255,255,255,.03); border-radius: 3px; }
.rp::-webkit-scrollbar-thumb { background: var(--bdr); border-radius: 3px; }
/* Stack result cards vertically with gap */
.rp > * + * { margin-top: 16px; }

/* ── EMPTY STATE ─────────────────────────── */
.empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; padding: 80px 0; text-align: center; opacity: .35; }
.empty h2 { font-size: 18px; font-weight: 600; }
.empty p  { font-size: 13px; color: var(--muted); line-height: 1.6; }

/* ── CARD ────────────────────────────────── */
.card { background: var(--card); border: 1px solid var(--bdr); border-radius: var(--r); overflow: hidden; }
.card-hdr { padding: 10px 16px; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid var(--bdr); font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .7px; color: var(--muted); }
.dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.card-body { padding: 16px; }

/* ── STAT TILES ──────────────────────────── */
.stat-row { display: flex; gap: 10px; flex-wrap: wrap; }
.stat-tile { flex: 1; min-width: 90px; background: var(--card2); border: 1px solid var(--bdr); border-radius: 8px; padding: 12px 14px; }
.st-label { font-size: 9.5px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; margin-bottom: 4px; }
.st-val   { font-size: 22px; font-weight: 800; line-height: 1; }
.st-sub   { font-size: 9.5px; color: var(--muted); margin-top: 4px; }

/* ── CHART GRID 2x2 ──────────────────────── */
.chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.chart-card { background: var(--card); border: 1px solid var(--bdr); border-radius: var(--r); overflow: hidden; }
.chart-title { padding: 10px 14px; border-bottom: 1px solid var(--bdr); font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .6px; color: var(--muted); display: flex; align-items: center; gap: 7px; }
.chart-sub   { font-size: 9px; color: #3A4060; text-transform: none; letter-spacing: 0; font-weight: 400; margin-left: auto; }
.chart-wrap  { padding: 14px; height: 230px; position: relative; }

/* ── COMPARISON TABLE ────────────────────── */
.tbl-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; }
thead th {
  background: #0E1020;
  padding: 10px 14px;
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .4px;
  color: var(--muted);
  border-bottom: 2px solid var(--bdr);
  white-space: nowrap;
}
thead th:first-child { text-align: left; min-width: 160px; }
thead th:not(:first-child) { text-align: center; }
.hdr-static { color: #FF4466 !important; }
.hdr-1bit   { color: #FF9944 !important; }
.hdr-2bit   { color: #00D4AA !important; }
.hdr-ghr    { color: #44BBFF !important; }
td { padding: 9px 14px; border-bottom: 1px solid rgba(36,40,64,.5); text-align: center; font-size: 12px; }
td:first-child { text-align: left; color: var(--muted); font-size: 11px; font-weight: 500; white-space: nowrap; }
tr:last-child td { border-bottom: none; }
tr.grp td { background: #0E1020; color: #3A4060; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; padding: 6px 14px; border-bottom: 1px solid var(--bdr); border-top: 1px solid var(--bdr); text-align: left; }
.chip { display: inline-block; font-size: 9.5px; font-weight: 700; padding: 2px 6px; border-radius: 4px; margin-top: 1px; }
.cg  { background: rgba(0,212,170,.12);  color: var(--green); }
.cb  { background: rgba(255,68,102,.12); color: var(--red); }

/* ── TRACE PREVIEW ───────────────────────── */
.trace-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.trace-lbl  { font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 6px; }
.tl-n { color: var(--red); }
.tl-j { color: var(--green); }
.trace-box {
  background: var(--bg);
  border: 1px solid var(--bdr);
  border-radius: 8px;
  padding: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  line-height: 1.7;
  height: 160px;
  overflow-y: auto;
  white-space: pre;
}
.tk { color: var(--green); }
.nt { color: var(--red); }
.np { color: #252A45; }

/* ── LOADING OVERLAY ─────────────────────── */
#ov { position: fixed; inset: 0; background: rgba(11,13,26,.88); display: none; z-index: 999; align-items: center; justify-content: center; backdrop-filter: blur(4px); }
#ov.on { display: flex; }
.ov-box { background: var(--card); border: 1px solid var(--bdr); border-radius: 16px; padding: 36px 52px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 14px; }
.spin { width: 44px; height: 44px; border: 3px solid rgba(124,111,255,.15); border-top-color: var(--acc); border-radius: 50%; animation: sp .75s linear infinite; }
@keyframes sp { to { transform: rotate(360deg); } }
.ov-title { font-weight: 700; font-size: 16px; }
.ov-step  { font-size: 12px; color: var(--muted); }

/* ── ERROR ───────────────────────────────── */
.err { background: rgba(255,68,102,.08); border: 1px solid rgba(255,68,102,.3); border-radius: var(--r); padding: 18px; color: var(--red); font-size: 13px; }

::-webkit-scrollbar       { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--bdr); border-radius: 2px; }
</style>
</head>
<body>

<!-- Overlay -->
<div id="ov">
  <div class="ov-box">
    <div class="spin"></div>
    <div class="ov-title">Running Simulation</div>
    <div class="ov-step" id="ov-step">Analyzing code...</div>
  </div>
</div>

<!-- Header -->
<header>
  <div class="logo">
    <span class="logo-chip">JIT</span>
    <span class="logo-title">Branch Predictor &mdash; Dynamic Analyzer</span>
  </div>
  <span class="header-hint">Paste code &rarr; Simulate &rarr; Compare all 4 predictors Naive vs JIT</span>
</header>

<!-- Main -->
<div class="main">

  <!-- Editor Panel -->
  <div class="ep">
    <div class="ep-hdr">
      <span class="ep-label">Code Input</span>
      <span class="lang-tag" id="lang-tag">Auto-detect</span>
    </div>
    <textarea id="code" spellcheck="false" placeholder="# Paste Python / C / Java code here...
# Detected patterns:
#   for i in range(N)    loop branches
#   if isinstance(x, T)  type dispatch
#   if/elif chains        branch chains
#
# Generates two RISC-V traces:
#   Naive  - code order, mixed patterns
#   JIT    - loops hoisted, hot path = taken
#
# Runs all 4 predictors on both traces."></textarea>
    <div class="ep-badges" id="badges"></div>
    <button class="run-btn" id="run-btn" onclick="runSim()">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
      Run Simulation
    </button>
  </div>

  <!-- Results Panel -->
  <div class="rp" id="rp">
    <div class="empty" id="empty">
      <div style="font-size:52px">&#x26A1;</div>
      <h2>Ready to Simulate</h2>
      <p>Paste any Python, C, or Java code on the left<br>and click <strong>Run Simulation</strong></p>
    </div>
  </div>

</div>

<script>
// ─────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────
const PREDS  = ['Static', '1-Bit', '2-Bit', 'GHR'];
const COLORS = ['#FF4466', '#FF9944', '#00D4AA', '#44BBFF'];
const NAIVE_C = 'rgba(255, 84, 112, 0.72)';
const JIT_C   = 'rgba(0, 212, 170, 0.78)';

Chart.defaults.color       = '#6B77A0';
Chart.defaults.borderColor = '#1C2038';
Chart.defaults.font.family = 'Inter';
Chart.defaults.animation.duration = 650;

let CH = {};   // chart instances

function destroyCharts() {
  Object.values(CH).forEach(c => { try { c.destroy(); } catch(e){} });
  CH = {};
}

// ─────────────────────────────────────────────────────
// Live Badge Update
// ─────────────────────────────────────────────────────
document.getElementById('code').addEventListener('input', debounce(liveAnalyze, 350));

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

function liveAnalyze() {
  const code = document.getElementById('code').value;
  if (!code.trim()) { document.getElementById('badges').innerHTML = ''; return; }
  const loops = (code.match(/\b(for|while)\b/g) || []).length;
  const ifs   = (code.match(/\belif\b|\belse\s+if\b/g) || []).length + (code.match(/\bif\s*[\(\s]/g) || []).length;
  const types = (code.match(/\b(isinstance|instanceof|issubclass|getClass)\b/g) || []).length;
  const isPy = /\bdef\b|\belif\b|\bimport\b/.test(code);
  const isC  = /\bvoid\b|\bint\s+main\b|\#include/.test(code);
  document.getElementById('lang-tag').textContent = isPy ? 'Python' : isC ? 'C/C++' : 'Auto';
  document.getElementById('badges').innerHTML = [
    loops ? `<span class="badge bl">&#x1F504; ${loops} loop${loops>1?'s':''}</span>` : '',
    ifs   ? `<span class="badge bb">&#x1F500; ${ifs} branch${ifs>1?'es':''}</span>`   : '',
    types ? `<span class="badge bt">&#x1F9EA; ${types} type-check${types>1?'s':''}</span>` : '',
    (!loops && !ifs && !types) ? '<span class="badge bb" style="opacity:.4">No branches detected</span>' : ''
  ].join('');
}

// ─────────────────────────────────────────────────────
// Run Simulation
// ─────────────────────────────────────────────────────
async function runSim() {
  const code = document.getElementById('code').value.trim();
  if (!code) { alert('Please paste some code first.'); return; }
  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  const ov = document.getElementById('ov');
  const st = document.getElementById('ov-step');
  ov.classList.add('on');
  const steps = ['Parsing branch patterns...','Generating naive trace...','Generating JIT trace...','Compiling Verilog...','Running simulation...','Collecting results...'];
  let si = 0; st.textContent = steps[0];
  const iv = setInterval(() => { st.textContent = steps[Math.min(++si, steps.length-1)]; }, 900);
  try {
    const resp = await fetch('/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });
    const data = await resp.json();
    clearInterval(iv); ov.classList.remove('on'); btn.disabled = false;
    data.error ? showErr(data.error) : render(data);
  } catch(e) {
    clearInterval(iv); ov.classList.remove('on'); btn.disabled = false;
    showErr('Connection error: ' + e.message);
  }
}

function showErr(msg) {
  document.getElementById('rp').innerHTML = `<div class="err">&#x26A0; <strong>Error</strong><br><br>${msg}</div>`;
}

// ─────────────────────────────────────────────────────
// Render Results
// ─────────────────────────────────────────────────────
function render(data) {
  destroyCharts();
  const rp = document.getElementById('rp');
  rp.innerHTML = '';

  const { analysis, naive_stats, jit_stats, rows, naive_preview, jit_preview } = data;
  const NR = rows.filter(r => r.exp === 'Naive');
  const JR = rows.filter(r => r.exp === 'JIT');

  function fV(arr, pred, field) { const r = arr.find(x => x.predictor === pred); return r ? parseFloat(r[field]||0) : 0; }
  function fI(arr, pred, field) { const r = arr.find(x => x.predictor === pred); return r ? parseInt(r[field]||0)   : 0; }

  const LABELS = ['Normal Compilation', 'JIT + Static', 'JIT + 1-Bit', 'JIT + 2-Bit', 'JIT + GShare'];
  const COLORS_5 = ['#FF4466', '#8896BB', '#FF9944', '#00D4AA', '#44BBFF'];
  const BG_COLORS_5 = ['rgba(255,68,102,.7)', 'rgba(136,150,187,.7)', 'rgba(255,153,68,.7)', 'rgba(0,212,170,.7)', 'rgba(68,187,255,.7)'];

  const getMetricV = (field) => [
    fV(NR, 'Static', field),
    fV(JR, 'Static', field),
    fV(JR, '1-Bit', field),
    fV(JR, '2-Bit', field),
    fV(JR, 'GHR', field)
  ];
  
  const getMetricI = (field) => [
    fI(NR, 'Static', field),
    fI(JR, 'Static', field),
    fI(JR, '1-Bit', field),
    fI(JR, '2-Bit', field),
    fI(JR, 'GHR', field)
  ];

  const ipcData = getMetricV('ipc');
  const mispData = getMetricV('mispredict_rate');
  const wasteData = getMetricI('wasted_cycles');
  
  const baseIPC = ipcData[0] || 1;
  const speedups = ipcData.map(v => v / baseIPC);
  const bestSU = Math.max(...speedups);
  const bestLabel = LABELS[speedups.indexOf(bestSU)];

  // ── 1. Analysis Summary Cards ─────────────────────
  const loopC = (analysis.for_loops||[]).length + (analysis.while_loops||0);
  const ifC   = (analysis.if_chains||[]).length;
  const tcC   = analysis.isinstance_calls || 0;

  add(rp, `
  <div class="card">
    <div class="card-hdr"><div class="dot" style="background:#7C6FFF"></div>Hardware Acceleration Summary</div>
    <div class="card-body">
      <div class="stat-row">
        <div class="stat-tile">
          <div class="st-label">Language</div>
          <div class="st-val" style="font-size:15px;color:#7C6FFF">${analysis.language}</div>
        </div>
        <div class="stat-tile">
          <div class="st-label">Loop constructs</div>
          <div class="st-val" style="color:#00D4AA">${loopC}</div>
          <div class="st-sub">for / while</div>
        </div>
        <div class="stat-tile">
          <div class="st-label">Branch chains</div>
          <div class="st-val" style="color:#FF9944">${ifC}</div>
          <div class="st-sub">if / elif / else</div>
        </div>
        <div class="stat-tile">
          <div class="st-label">Type checks</div>
          <div class="st-val" style="color:#FF4466">${tcC}</div>
          <div class="st-sub">isinstance etc</div>
        </div>
        <div class="stat-tile">
          <div class="st-label">JIT Fall-Through</div>
          <div class="st-val" style="color:#44BBFF">${jit_stats.taken_ratio}%</div>
          <div class="st-sub">branches taken</div>
        </div>
        <div class="stat-tile" style="border-color:rgba(0,212,170,.35);background:rgba(0,212,170,.05)">
          <div class="st-label">Max Hardware Speedup</div>
          <div class="st-val" style="color:#00D4AA">${bestSU.toFixed(2)}x</div>
          <div class="st-sub">${bestLabel}</div>
        </div>
      </div>
    </div>
  </div>`);

  // ── 2. Charts 2x2 grid ───────────────────────────
  add(rp, `
  <div class="chart-grid">
    <div class="chart-card">
      <div class="chart-title">
        <div class="dot" style="background:#00D4AA"></div>
        Effective IPC
        <span class="chart-sub">higher = better &uarr; &nbsp; max = 1.0</span>
      </div>
      <div class="chart-wrap"><canvas id="ch-ipc"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">
        <div class="dot" style="background:#44BBFF"></div>
        Hardware Speedup Factor
        <span class="chart-sub">relative to Baseline</span>
      </div>
      <div class="chart-wrap"><canvas id="ch-su"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">
        <div class="dot" style="background:#FF9944"></div>
        Misprediction Rate (%)
        <span class="chart-sub">lower = better &darr;</span>
      </div>
      <div class="chart-wrap"><canvas id="ch-misp"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">
        <div class="dot" style="background:#FF4466"></div>
        Wasted Cycles
        <span class="chart-sub">per 2000 sim cycles &darr;</span>
      </div>
      <div class="chart-wrap"><canvas id="ch-wc"></canvas></div>
    </div>
  </div>`);

  /* chart helpers */
  const axOpts = {
    x: { ticks: { color:'#6B77A0', font:{size:10} }, grid: { display:false } },
    y: { ticks: { color:'#6B77A0', font:{size:10} }, grid: { color:'rgba(36,40,64,.6)' } }
  };
  const tipStyle = { backgroundColor:'#161A2E', borderColor:'#242840', borderWidth:1, titleColor:'#DDE4F5', bodyColor:'#6B77A0', padding:10 };

  const singleBar = (id, data, yMax, yFmt) => {
    CH[id] = new Chart(document.getElementById(id), {
      type: 'bar',
      data: {
        labels: LABELS,
        datasets: [{
          data: data,
          backgroundColor: BG_COLORS_5,
          borderColor: COLORS_5,
          borderWidth: 1.5,
          borderRadius: 5
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { ...tipStyle } },
        scales: {
          x: axOpts.x,
          y: { ...axOpts.y, max: yMax||undefined, ticks: { ...axOpts.y.ticks, callback: yFmt||undefined } }
        }
      }
    });
  };

  singleBar('ch-ipc', ipcData, 1.05, v => v.toFixed(2));
  singleBar('ch-su', speedups, null, v => v.toFixed(2)+'x');
  singleBar('ch-misp', mispData, null, v => v.toFixed(0)+'%');
  singleBar('ch-wc', wasteData, null, null);

  // ── 3. Full Comparison Table ──────────────────────
  function tRow(label, vals, fmtFn, chipFn) {
    const cells = vals.map((v,i) => {
      const chip = chipFn ? chipFn(v, i) : '';
      return `<td style="color:${COLORS_5[i]}">${fmtFn(v,i)} ${chip}</td>`;
    }).join('');
    return `<tr><td>${label}</td>${cells}</tr>`;
  }

  function chip(val, good) {
    const cls = good ? 'cg' : 'cb';
    const sign = val > 0 ? '+' : '';
    return `<span class="chip ${cls}">${sign}${val}</span>`;
  }

  const tblHtml = `
  <div class="card">
    <div class="card-hdr"><div class="dot" style="background:#44BBFF"></div> Architecture Progression Table</div>
    <div class="card-body" style="padding:0">
      <div class="tbl-scroll">
        <table>
          <thead>
            <tr>
              <th>Metric</th>
              <th style="color:#FF4466">Normal Compilation</th>
              <th style="color:#8896BB">JIT + Static</th>
              <th style="color:#FF9944">JIT + 1-Bit</th>
              <th style="color:#00D4AA">JIT + 2-Bit</th>
              <th style="color:#44BBFF">JIT + GShare</th>
            </tr>
          </thead>
          <tbody>
            <tr class="grp"><td colspan="6">Performance</td></tr>
            ${tRow('Effective IPC', ipcData, (v) => v.toFixed(4))}
            ${tRow('Speedup vs Base', speedups, (v) => `<strong>${v.toFixed(3)}x</strong>`, (v) => chip('+'+((v-1)*100).toFixed(1)+'%', true))}

            <tr class="grp"><td colspan="6">Mispredictions</td></tr>
            ${tRow('Miss Rate (%)', mispData, (v) => v.toFixed(1)+'%')}
            ${tRow('Wasted Cycles', wasteData, v => v)}
            
            <tr class="grp"><td colspan="6">Raw Hardware Events (per 2000 cycles)</td></tr>
            ${tRow('Total Branches', getMetricI('branches'), v => v)}
            ${tRow('Mispredicted', getMetricI('mispredictions'), v => v)}
          </tbody>
        </table>
      </div>
    </div>
  </div>`;
  add(rp, tblHtml);

  // ── 4. Trace Preview ──────────────────────────────
  function colorizeTr(prev) {
    return prev.split('\n').map(ln => {
      if (ln.startsWith('00000463')) return `<span class="tk">${ln}  &larr; TAKEN</span>`;
      if (ln.startsWith('00001063')) return `<span class="nt">${ln}  &larr; NOT-TAKEN</span>`;
      if (ln.startsWith('00000013')) return `<span class="np">${ln}</span>`;
      return ln;
    }).join('\n');
  }

  add(rp, `
  <div class="card">
    <div class="card-hdr"><div class="dot" style="background:#7C6FFF"></div>Generated RISC-V Traces &mdash; First 32 Instructions</div>
    <div class="card-body">
      <div class="trace-cols">
        <div>
          <div class="trace-lbl tl-n">&#x25A0; Naive Trace (code order)</div>
          <div class="trace-box">${colorizeTr(naive_preview)}</div>
        </div>
        <div>
          <div class="trace-lbl tl-j">&#x25A0; JIT-Optimized Trace</div>
          <div class="trace-box">${colorizeTr(jit_preview)}</div>
        </div>
      </div>
      <div style="margin-top:10px;font-size:10px;color:#3A4060;display:flex;gap:16px">
        <span><span style="color:#00D4AA">&#x25A0;</span> 00000463 = BEQ x0,x0 (always TAKEN)</span>
        <span><span style="color:#FF4466">&#x25A0;</span> 00001063 = BNE x0,x0 (always NOT-TAKEN)</span>
        <span><span style="color:#252A45">&#x25A0;</span> 00000013 = NOP</span>
      </div>
    </div>
  </div>`);

  rp.scrollTop = 0;
}

function add(el, html) { el.insertAdjacentHTML('beforeend', html); }

// ─────────────────────────────────────────────────────
// Sample code on load
// ─────────────────────────────────────────────────────
window.onload = () => {
  document.getElementById('code').value =
`# Python-style JIT hot spot: type dispatch + nested loops
import math

def process_data_pipeline(batches):
    # Simulates a data processor with mixed types and conditionals
    grand_total = 0.0
    system_state = "READY"  # Simple state machine logic

    for batch_id, batch in enumerate(batches):
        # Outer loop: Batch-level processing
        batch_checksum = 0

        for record in batch:
            # Inner Loop: The "Hot Spot" where JIT optimization happens

            # 1. Type-based Dispatching
            if isinstance(record, (int, float)):
                # Numerical path: Heavy arithmetic
                if record > 0:
                    batch_checksum += record * 1.5
                elif record < -100:
                    batch_checksum -= record
                else:
                    batch_checksum += abs(record)
            elif isinstance(record, str):
                # String path
                batch_checksum += len(record) * 0.5
            elif isinstance(record, list):
                # List path: sub-iteration
                for item in record:
                    batch_checksum += item if isinstance(item, (int, float)) else 0
            elif isinstance(record, dict):
                batch_checksum += sum(v for v in record.values()
                                      if isinstance(v, (int, float)))

        # 2. Batch validation
        if batch_checksum > 1000:
            grand_total += batch_checksum
        elif batch_checksum > 100:
            grand_total += batch_checksum * 0.9
        elif batch_checksum > 0:
            grand_total += batch_checksum * 0.5

    return grand_total`;
  liveAnalyze();
};
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────
# HTTP Server
# ─────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if "/simulate" in (args[0] if args else ""):
            print(f"  [sim] {args[1]}  {args[0].split()[1] if args[0].split()[1:] else ''}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/simulate":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                data = json.loads(body)
                code = data.get("code", "")
            except Exception as e:
                self._err(str(e)); return
            print(f"  [run] {len(code)} chars of code...")
            result = simulate(code)
            self._json(result)
        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg):
        self._json({"error": msg})

# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    PORT = 5173
    print("=" * 56)
    print("  JIT Branch Predictor -- Dynamic Analyzer")
    print("=" * 56)
    print(f"  Project : {PROJ_DIR}")
    print()
    print("  Pre-compiling Verilog simulation...")
    ok = ensure_compiled()
    print("  Compilation:", "OK" if ok else "FAILED (check iverilog in PATH)")
    print()
    print(f"  Open in browser:  http://localhost:{PORT}")
    print("  Ctrl+C to stop.")
    print("=" * 56)
    server = HTTPServer(("", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
