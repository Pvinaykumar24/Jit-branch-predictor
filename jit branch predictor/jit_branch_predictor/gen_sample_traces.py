# -*- coding: utf-8 -*-
"""gen_sample_traces.py — Generate sample user_naive.mem and user_jit.mem for smoke testing."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Manually duplicate the trace generation logic (no import issues)
TAKEN     = "00000463"
NOT_TAKEN = "00100063"
NOP       = "00000013"

def _pad(instructions):
    while len(instructions) < 256:
        instructions.append(NOP)
    return instructions[:256]

def gen_naive():
    instr = []
    # 1 for loop of 20 iterations
    for i in range(20):
        instr += [NOP, NOP, TAKEN]
    instr.append(NOT_TAKEN)
    # 2 isinstance calls (alternating)
    for _ in range(2):
        instr += [NOP, TAKEN, NOT_TAKEN]
    # 1 if-chain of length 2
    for i in range(2):
        instr += [NOP, TAKEN if i%2==0 else NOT_TAKEN]
    return _pad(instr)

def gen_jit():
    instr = []
    # Loop tightened
    for i in range(20):
        instr += [NOP, TAKEN]
    instr.append(NOT_TAKEN)
    # isinstance: batched not-taken
    for _ in range(2):
        instr += [NOP, NOT_TAKEN]
    # if-chain: hot path taken
    for _ in range(2):
        instr += [NOP, TAKEN]
    return _pad(instr)

TRACE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tb", "traces")
os.makedirs(TRACE_DIR, exist_ok=True)

naive = gen_naive()
jit   = gen_jit()

with open(os.path.join(TRACE_DIR, "user_naive.mem"), "w") as f:
    f.write("\n".join(naive) + "\n")
with open(os.path.join(TRACE_DIR, "user_jit.mem"), "w") as f:
    f.write("\n".join(jit) + "\n")

print("Naive branches:", naive.count(TAKEN)+naive.count(NOT_TAKEN))
print("JIT   branches:", jit.count(TAKEN)+jit.count(NOT_TAKEN))
print("Traces written to", TRACE_DIR)
