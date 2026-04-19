module register_file (
    input  wire        clk,
    input  wire        we,         // write enable from WB stage
    input  wire [4:0]  rs1, rs2,   // read addresses
    input  wire [4:0]  rd,         // write address
    input  wire [31:0] wdata,      // write data from WB
    output wire [31:0] rdata1,     // read port 1
    output wire [31:0] rdata2      // read port 2
);
    reg [31:0] regs [0:31];

    integer i;
    initial begin
        for (i = 0; i < 32; i = i + 1)
            regs[i] = 32'h0;
        regs[1] = 32'h1; // x1 = 1 so BEQ x0,x1 is never taken (not-taken branch)
    end

    // Asynchronous read — combinational
    assign rdata1 = (rs1 == 5'b0) ? 32'h0 : regs[rs1];
    assign rdata2 = (rs2 == 5'b0) ? 32'h0 : regs[rs2];

    // Synchronous write — on rising edge
    always @(posedge clk) begin
        if (we && rd != 5'b0)
            regs[rd] <= wdata;
    end
endmodule
