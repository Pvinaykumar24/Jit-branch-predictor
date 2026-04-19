module pred_static (
    input  wire        clk, rst,
    input  wire [31:0] pc,
    input  wire        update_en, actual_taken,
    output wire        predicted_taken
);
    // Static: always predict not-taken (PC+4)
    // No table, no state — simplest possible predictor
    assign predicted_taken = 1'b0;
endmodule
