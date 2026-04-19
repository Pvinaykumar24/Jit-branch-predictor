module instr_mem (
    input  wire        clk,
    input  wire [31:0] addr,
    output reg  [31:0] instr
);
    reg [31:0] mem [0:255];

    // Testbench loads trace via $readmemh before simulation starts
    // Do not initialise here — tb_top.v calls $readmemh on this memory

    always @(posedge clk) begin
        instr <= mem[addr[9:2]]; // Word-aligned: drop bottom 2 bits
    end
endmodule
