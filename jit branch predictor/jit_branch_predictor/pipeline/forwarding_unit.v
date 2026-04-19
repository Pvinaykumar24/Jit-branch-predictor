module forwarding_unit (
    input  wire [4:0]  ex_rs1, ex_rs2,           // current EX needs these
    input  wire [4:0]  mem_rd,                    // EX/MEM register
    input  wire        mem_reg_write,
    input  wire [31:0] mem_alu_result,            // EX/MEM value
    input  wire [4:0]  wb_rd,                     // MEM/WB register
    input  wire        wb_reg_write,
    input  wire [31:0] wb_data,                   // MEM/WB value
    output reg  [31:0] fwd_a, fwd_b,
    output reg         use_fwd_a, use_fwd_b
);
    always @(*) begin
        // Forward A (rs1)
        if (mem_reg_write && mem_rd != 0 && mem_rd == ex_rs1) begin
            fwd_a = mem_alu_result; use_fwd_a = 1;
        end else if (wb_reg_write && wb_rd != 0 && wb_rd == ex_rs1) begin
            fwd_a = wb_data; use_fwd_a = 1;
        end else begin
            fwd_a = 32'h0; use_fwd_a = 0;
        end

        // Forward B (rs2)
        if (mem_reg_write && mem_rd != 0 && mem_rd == ex_rs2) begin
            fwd_b = mem_alu_result; use_fwd_b = 1;
        end else if (wb_reg_write && wb_rd != 0 && wb_rd == ex_rs2) begin
            fwd_b = wb_data; use_fwd_b = 1;
        end else begin
            fwd_b = 32'h0; use_fwd_b = 0;
        end
    end
endmodule
