module id_stage (
    input  wire [31:0] instr,
    input  wire [31:0] pc,
    // register file connections
    output wire [4:0]  rs1, rs2, rd,
    output wire [31:0] imm,
    output wire [3:0]  alu_op,
    output wire        mem_read,
    output wire        mem_write,
    output wire        reg_write,
    output wire        is_branch,   // 1 if this instruction is a branch
    output wire        branch_type  // 0=BEQ, 1=BNE
);
    // RISC-V instruction fields
    wire [6:0] opcode = instr[6:0];
    wire [2:0] funct3 = instr[14:12];
    wire [6:0] funct7 = instr[31:25];

    assign rs1 = instr[19:15];
    assign rs2 = instr[24:20];
    assign rd  = instr[11:7];

    // Branch immediate: sign-extended 13-bit offset (B-type encoding)
    assign imm = {{19{instr[31]}}, instr[31], instr[7],
                   instr[30:25], instr[11:8], 1'b0};

    // Opcode decode
    localparam OP_BRANCH = 7'b1100011;
    localparam OP_LOAD   = 7'b0000011;
    localparam OP_STORE  = 7'b0100011;
    localparam OP_IMM    = 7'b0010011;
    localparam OP_REG    = 7'b0110011;

    assign is_branch  = (opcode == OP_BRANCH);
    assign branch_type = funct3[0]; // BEQ=000 → 0, BNE=001 → 1
    assign mem_read   = (opcode == OP_LOAD);
    assign mem_write  = (opcode == OP_STORE);
    assign reg_write  = (opcode == OP_IMM || opcode == OP_REG ||
                         opcode == OP_LOAD);

    // ALU op selection (simplified)
    assign alu_op = (opcode == OP_BRANCH) ? 4'd1 : // SUB for comparison
                    (funct3 == 3'b111)    ? 4'd2 : // AND
                    (funct3 == 3'b110)    ? 4'd3 : // OR
                    4'd0;                           // ADD default
endmodule
