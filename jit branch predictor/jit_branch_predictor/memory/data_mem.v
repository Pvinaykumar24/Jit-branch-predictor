module data_mem (
    input  wire        clk,
    input  wire        we,        // write enable
    input  wire [31:0] addr,
    input  wire [31:0] wdata,
    output reg  [31:0] rdata
);
    reg [31:0] mem [0:255];

    integer i;
    initial begin
        for (i = 0; i < 256; i = i + 1)
            mem[i] = 32'h0;
    end

    always @(posedge clk) begin
        if (we)
            mem[addr[9:2]] <= wdata;
        else
            rdata <= mem[addr[9:2]];
    end
endmodule
