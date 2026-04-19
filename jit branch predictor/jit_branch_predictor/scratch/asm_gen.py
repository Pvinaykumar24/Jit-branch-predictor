def get_branch_hex(offset, rs1, rs2, funct3):
    # offset is relative to PC. Must be multiple of 2.
    imm = offset
    imm_12 = (imm >> 12) & 0x1
    imm_11 = (imm >> 11) & 0x1
    imm_10_5 = (imm >> 5) & 0x3F
    imm_4_1 = (imm >> 1) & 0xF
    
    bits_31_25 = (imm_12 << 6) | imm_10_5
    bits_11_8 = imm_4_1
    bits_7 = imm_11
    
    # B-type: imm[12] imm[10:5] rs2 rs1 funct3 imm[4:1] imm[11] opcode
    val = (bits_31_25 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (bits_11_8 << 8) | (bits_7 << 7) | 0x63
    return f"{val:08X}"

# BNE x2, x0, -28
# rs1=2, rs2=0, funct3=1, offset=-28
print(f"BNE x2, x0, -28: {get_branch_hex(-28, 2, 0, 1)}")

# BEQ x1, x0, +8
# rs1=1, rs2=0, funct3=0, offset=8
print(f"BEQ x1, x0, +8: {get_branch_hex(8, 1, 0, 0)}")

# BEQ x1, x0, -40
# PC=28. Loop to 0. Offset=-40
print(f"BEQ x2, x0, -40: {get_branch_hex(-40, 2, 0, 0)}")
