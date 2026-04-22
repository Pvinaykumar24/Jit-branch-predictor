import os

TAKEN = "00000463"
NOT_TAKEN = "00001063"
NOP = "00000013"

instr = []
c = 0
for _ in range(4): # 4 PIC branches
    instr += [NOP] * 63
    instr.append(TAKEN if c % 2 == 0 else NOT_TAKEN)
    c += 1

# pad to 256
if len(instr) < 256:
    instr += [NOP] * (256 - len(instr))
instr = instr[:256]

# Write to trace
open("tb/traces/user_jit.mem", "w").write("\n".join(instr))

# Run verilog
os.system("iverilog -o sim.vvp tb/tb_dynamic.v predictors/pred_*.v pipeline/*.v && vvp sim.vvp > out.txt")
with open("out.txt") as f:
    for line in f:
        if "JIT," in line:
            print(line.strip())
