module id_ex_reg (
    input  wire        clk, rst, flush,
    // inputs from ID
    input  wire [31:0] id_pc, id_rdata1, id_rdata2, id_imm,
    input  wire [4:0]  id_rs1, id_rs2, id_rd,
    input  wire [3:0]  id_alu_op,
    input  wire        id_mem_read, id_mem_write, id_reg_write,
    input  wire        id_is_branch, id_branch_type,
    input  wire        id_predicted_taken,
    // outputs to EX
    output reg  [31:0] ex_pc, ex_rdata1, ex_rdata2, ex_imm,
    output reg  [4:0]  ex_rs1, ex_rs2, ex_rd,
    output reg  [3:0]  ex_alu_op,
    output reg         ex_mem_read, ex_mem_write, ex_reg_write,
    output reg         ex_is_branch, ex_branch_type,
    output reg         ex_predicted_taken
);
    always @(posedge clk or posedge rst) begin
        if (rst || flush) begin
            ex_pc <= 0; ex_rdata1 <= 0; ex_rdata2 <= 0; ex_imm <= 0;
            ex_rs1 <= 0; ex_rs2 <= 0; ex_rd <= 0; ex_alu_op <= 0;
            ex_mem_read <= 0; ex_mem_write <= 0; ex_reg_write <= 0;
            ex_is_branch <= 0; ex_branch_type <= 0;
            ex_predicted_taken <= 0;
        end else begin
            ex_pc <= id_pc; ex_rdata1 <= id_rdata1; ex_rdata2 <= id_rdata2;
            ex_imm <= id_imm; ex_rs1 <= id_rs1; ex_rs2 <= id_rs2;
            ex_rd <= id_rd; ex_alu_op <= id_alu_op;
            ex_mem_read <= id_mem_read; ex_mem_write <= id_mem_write;
            ex_reg_write <= id_reg_write; ex_is_branch <= id_is_branch;
            ex_branch_type <= id_branch_type;
            ex_predicted_taken <= id_predicted_taken;
        end
    end
endmodule
