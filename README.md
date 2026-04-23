# JIT Branch Predictor: Simulation and Analysis

This repository contains a COA course project that studies how **JIT-style code generation** interacts with **hardware branch predictors** implemented in a 5‑stage RISC‑V pipeline.

The core idea is simple: we generate two types of branch traces from the same Python code (naive interpreter-style and JIT‑like), feed them into different predictors (Static, 1‑bit, 2‑bit, GShare), and measure misprediction rate, wasted cycles and IPC.

---

## 1. Features

- 5‑stage **RISC‑V pipeline** in Verilog (IF, ID, EX, MEM, WB).
- Four branch predictors:
  - Static (always not-taken)
  - 1‑bit history
  - 2‑bit saturating counter
  - GShare with Global History Register (GHR) and BTB hooks
- Python backend:
  - Parses user Python code using the `ast` module.
  - Generates **naive** (interpreter-like) and **JIT** (optimized) branch traces.
  - Orchestrates Icarus Verilog simulations and collects metrics.
- Simple web frontend:
  - Paste Python code in a text area.
  - See bar charts comparing predictors on naive vs JIT traces.
  - Export results as CSV.

---

## 2. Repository Layout

```text
Jit-branch-predictor/
├── README.md
├── presentation.tex                  # Beamer slides (project summary)
└── jit branch predictor/
    ├── app.py                        # Flask/FastAPI web backend
    ├── ast_analyzer.py               # Python AST parsing
    ├── trace_generator.py            # Naive + JIT RISC-V trace generation
    ├── simulator.py                  # iverilog / vvp orchestration
    ├── pipeline.v                    # 5-stage RISC-V pipeline (top module)
    ├── branch_predictor.v            # Static, 1-bit, 2-bit, GShare
    ├── hazard_unit.v                 # Load-use hazard detection
    ├── forwarding_unit.v             # EX/MEM forwarding logic
    ├── alu.v                         # Arithmetic Logic Unit
    ├── register_file.v               # 32 x 32-bit register file
    ├── memory.v                      # Instruction and data memories
    ├── testbench.v                   # Top-level Verilog testbench
    └── static/                       # HTML, CSS, JS for frontend
```

---

## 3. Getting Started

### 3.1. Prerequisites

- Python 3.8+
- `pip` for installing Python packages
- [Icarus Verilog](http://iverilog.icarus.com/) (`iverilog`, `vvp`)
- A modern browser (Chrome/Firefox)

On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y iverilog python3 python3-pip
pip3 install flask
```

### 3.2. Running the Web App

```bash
cd "Jit-branch-predictor/jit branch predictor"
python3 app.py
```

Then open:

- http://localhost:5000

in your browser.

Workflow:

1. Paste a small Python function with loops / if‑else chains.
2. Click **Analyze**.
3. The backend:
   - Parses the AST.
   - Builds naive and JIT‑style branch traces.
   - Runs Verilog simulations for each predictor.
4. The frontend shows **bar charts** for misprediction rate, wasted cycles, and IPC.

You can also download the raw metrics as CSV.

---

## 4. Command-line Simulation (Optional)

You can bypass the web UI and run simulations directly.

### 4.1. Generate a JIT Trace

```bash
python3 - << 'EOF'
from ast_analyzer import analyze
from trace_generator import gen_jit_trace

src = """
def compute(n):
    total = 0
    for i in range(n):
        total += i * i
    return total
"""

analysis = analyze(src)
trace = gen_jit_trace(analysis)

with open("jit_trace.mem", "w") as f:
    for entry in trace:
        f.write(f"{entry['pc']:08x} {entry['taken']}\n")
EOF
```

### 4.2. Run Verilog with GShare

```bash
iverilog -o sim.vvp \
  -DPREDICTOR_GSHARE=1 \
  -DTRACE_FILE="jit_trace.mem" \
  pipeline.v branch_predictor.v hazard_unit.v \
  forwarding_unit.v alu.v register_file.v \
  memory.v testbench.v

vvp sim.vvp
```

The testbench prints total branches, mispredictions, wasted cycles, and IPC. Use these numbers to fill the table in your report or presentation.

---

## 5. Branch Predictor Overview

- **Static (Always Not-Taken)**  
  Single fixed decision; used as a baseline.

- **1-bit Predictor**  
  One bit per entry; flips on every mistake. Learns majority behavior, but suffers on loop exits.

- **2-bit Saturating Counter**  
  4-state FSM per entry (strong/weak taken/not-taken). Stabilizes quickly on tight loops and is less sensitive to noise.

- **GShare (with GHR)**  
  Uses a Global History Register and XORs it with PC bits to index a 2-bit Pattern History Table.  
  Works well on JIT traces where branch sequences are regular and correlated, because the GHR captures recent behavior and separates different contexts into different table entries.

---

## 6. Project Context

This repository is part of a **Computer Organization and Architecture** course project. The goal is to demonstrate, with an end‑to‑end working prototype, how:

- JIT compilation reshapes branch traces, and  
- Hardware branch predictors (especially GShare) respond to these changes under the same pipeline configuration.

The project is intended for educational use and experimentation, not as a production‑quality predictor or JIT compiler.

---

## 7. Acknowledgements

- RISC‑V ISA and open tooling community  
- Icarus Verilog project  
- Python `ast` module and documentation  
- Standard literature on branch prediction and computer architecture
