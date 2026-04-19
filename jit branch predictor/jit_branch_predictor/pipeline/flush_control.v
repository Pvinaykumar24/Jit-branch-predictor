module flush_control (
    input  wire        ex_is_branch,
    input  wire        branch_taken,      // actual outcome from EX
    input  wire        predicted_taken,   // what predictor said
    input  wire [31:0] branch_target,     // actual target from EX
    input  wire [31:0] ex_pc,
    output wire        flush,             // clear IF/ID and ID/EX
    output wire        mispredicted,      // signal to IF to correct PC
    output wire [31:0] actual_target      // correct PC for IF mux
);
    // Misprediction: branch instruction in EX, and outcome != prediction
    assign mispredicted  = ex_is_branch && (branch_taken != predicted_taken);
    assign flush         = mispredicted;
    // If mispredicted:
    // 1. If actually taken, go to branch target.
    // 2. If actually NOT taken, go to next sequential instruction (ex_pc + 4).
    assign actual_target = branch_taken ? branch_target : (ex_pc + 4);
    // Note: if not taken, PC already = PC+4 in IF so branch_target unused
endmodule
