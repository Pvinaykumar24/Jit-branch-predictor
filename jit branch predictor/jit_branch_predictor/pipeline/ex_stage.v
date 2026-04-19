module ex_stage (
    input  wire [31:0] pc, rdata1, rdata2, imm,
    input  wire [3:0]  alu_op,
    input  wire        is_branch, branch_type,
    // forwarded values from forwarding unit
    input  wire [31:0] fwd_a, fwd_b,
    input  wire        use_fwd_a, use_fwd_b,
    // outputs
    output wire [31:0] alu_result,
    output wire        branch_taken,   // actual branch outcome
    output wire [31:0] branch_target   // PC + imm
);
    wire [31:0] operand_a = use_fwd_a ? fwd_a : rdata1;
    wire [31:0] operand_b = use_fwd_b ? fwd_b : rdata2;
    wire        zero;

    alu alu_inst (
        .a(operand_a), .b(operand_b),
        .op(alu_op),
        .result(alu_result),
        .zero(zero)
    );

    // Branch condition: BEQ taken if zero=1, BNE taken if zero=0
    assign branch_taken  = is_branch && 
                           (branch_type == 0 ? zero : !zero);
    assign branch_target = pc + imm;
endmodule
