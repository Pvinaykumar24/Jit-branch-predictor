module pred_1bit (
    input  wire        clk, rst,
    input  wire [31:0] pc,           // current fetch PC (for predict)
    input  wire [31:0] update_pc,    // PC of resolved branch (for update)
    input  wire        update_en,    // 1 when branch resolved in EX
    input  wire        actual_taken, // actual outcome
    output wire        predicted_taken
);
    // 64-entry table indexed by PC[7:2]
    reg [63:0] pred_table; // 1 bit per entry

    wire [5:0] pred_idx   = pc[7:2];
    wire [5:0] update_idx = update_pc[7:2];

    assign predicted_taken = pred_table[pred_idx];

    always @(posedge clk or posedge rst) begin
        if (rst)
            pred_table <= 64'h0; // initialise all to not-taken
        else if (update_en)
            pred_table[update_idx] <= actual_taken; // flip to actual outcome
    end
endmodule
