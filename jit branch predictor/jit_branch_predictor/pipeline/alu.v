module alu (
    input  wire [31:0] a, b,
    input  wire [3:0]  op,
    output reg  [31:0] result,
    output wire        zero      // 1 when result == 0, used for BEQ
);
    // ALU operation codes
    localparam ADD = 4'd0;
    localparam SUB = 4'd1;
    localparam AND = 4'd2;
    localparam OR  = 4'd3;
    localparam SLT = 4'd4;
    localparam XOR = 4'd5;

    assign zero = (result == 32'h0);

    always @(*) begin
        case (op)
            ADD: result = a + b;
            SUB: result = a - b;
            AND: result = a & b;
            OR:  result = a | b;
            SLT: result = ($signed(a) < $signed(b)) ? 32'd1 : 32'd0;
            XOR: result = a ^ b;
            default: result = 32'h0;
        endcase
    end
endmodule
