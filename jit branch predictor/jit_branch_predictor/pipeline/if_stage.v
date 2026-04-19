module if_stage (
    input  wire        clk, rst,
    input  wire        stall,           // from hazard_unit: freeze PC
    input  wire        flush,           // from flush_control: misprediction
    input  wire        predicted_taken, // from predictor: take branch?
    input  wire [31:0] predicted_target,// from predictor: predicted PC
    input  wire [31:0] actual_target,   // from EX: real branch target
    input  wire        mispredicted,    // from flush_control
    output reg  [31:0] pc,
    output wire [31:0] pc_plus4
);
    assign pc_plus4 = pc + 32'd4;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            pc <= 32'h0;
        end else if (!stall) begin
            if (mispredicted)
                pc <= actual_target;          // correct the PC
            else if (predicted_taken)
                pc <= predicted_target;       // take predicted branch
            else
                pc <= pc_plus4;              // sequential execution
        end
        // if stall: hold current PC (do nothing)
    end
endmodule
