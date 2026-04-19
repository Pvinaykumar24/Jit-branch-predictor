module mem_wb_stage (
    input  wire [31:0] alu_result, mem_rdata,
    input  wire [4:0]  rd,
    input  wire        mem_read, reg_write,
    output wire [31:0] wb_data,
    output wire [4:0]  wb_rd,
    output wire        wb_we
);
    // If LOAD: write memory data back, else write ALU result
    assign wb_data = mem_read ? mem_rdata : alu_result;
    assign wb_rd   = rd;
    assign wb_we   = reg_write;
endmodule
