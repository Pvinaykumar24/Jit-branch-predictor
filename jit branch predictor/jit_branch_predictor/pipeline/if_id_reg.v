module if_id_reg (
    input  wire        clk, rst,
    input  wire        stall,      // freeze: hold current values
    input  wire        flush,      // clear: insert NOP bubble
    input  wire [31:0] if_pc,
    input  wire [31:0] if_instr,
    input  wire        if_predicted_taken,
    output reg  [31:0] id_pc,
    output reg  [31:0] id_instr,
    output reg         id_predicted_taken
);
    always @(posedge clk or posedge rst) begin
        if (rst || flush) begin
            id_pc              <= 32'h0;
            id_instr           <= 32'h00000013; // NOP = ADDI x0,x0,0
            id_predicted_taken <= 1'b0;
        end else if (!stall) begin
            id_pc              <= if_pc;
            id_instr           <= if_instr;
            id_predicted_taken <= if_predicted_taken;
        end
        // stall: retain current values
    end
endmodule
