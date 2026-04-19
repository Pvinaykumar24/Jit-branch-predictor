module ex_mem_reg (
    input  wire        clk, rst,
    input  wire [31:0] ex_alu_result, ex_rdata2,
    input  wire [4:0]  ex_rd,
    input  wire        ex_mem_read, ex_mem_write, ex_reg_write,
    output reg  [31:0] mem_alu_result, mem_rdata2,
    output reg  [4:0]  mem_rd,
    output reg         mem_mem_read, mem_mem_write, mem_reg_write
);
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            mem_alu_result <= 0; mem_rdata2 <= 0; mem_rd <= 0;
            mem_mem_read <= 0; mem_mem_write <= 0; mem_reg_write <= 0;
        end else begin
            mem_alu_result <= ex_alu_result;
            mem_rdata2     <= ex_rdata2;
            mem_rd         <= ex_rd;
            mem_mem_read   <= ex_mem_read;
            mem_mem_write  <= ex_mem_write;
            mem_reg_write  <= ex_reg_write;
        end
    end
endmodule
