module predictor_if #(
    parameter PREDICTOR_TYPE = 2  // 0=static, 1=1bit, 2=2bit, 3=ghr
)(
    input  wire        clk, rst,
    input  wire [31:0] fetch_pc,     // current instruction fetch address
    input  wire [31:0] update_pc,    // PC of branch resolved in EX
    input  wire        update_en,    // 1 when branch resolves
    input  wire        actual_taken, // actual branch outcome from EX
    output reg         predicted_taken
);
    wire p0, p1, p2, p3; // outputs of each predictor

    pred_static  u_static (.clk(clk), .rst(rst), .pc(fetch_pc),
                            .update_en(update_en),
                            .actual_taken(actual_taken),
                            .predicted_taken(p0));

    pred_1bit    u_1bit   (.clk(clk), .rst(rst), .pc(fetch_pc),
                            .update_pc(update_pc), .update_en(update_en),
                            .actual_taken(actual_taken),
                            .predicted_taken(p1));

    pred_2bit    u_2bit   (.clk(clk), .rst(rst), .pc(fetch_pc),
                            .update_pc(update_pc), .update_en(update_en),
                            .actual_taken(actual_taken),
                            .predicted_taken(p2));

    pred_ghr     u_ghr    (.clk(clk), .rst(rst), .pc(fetch_pc),
                            .update_pc(update_pc), .update_en(update_en),
                            .actual_taken(actual_taken),
                            .predicted_taken(p3));

    always @(*) begin
        case (PREDICTOR_TYPE)
            0: predicted_taken = p0;
            1: predicted_taken = p1;
            2: predicted_taken = p2;
            3: predicted_taken = p3;
            default: predicted_taken = p2;
        endcase
    end
endmodule
