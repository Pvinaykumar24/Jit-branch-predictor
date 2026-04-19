module pred_ghr (
    input  wire        clk, rst,
    input  wire [31:0] pc,
    input  wire [31:0] update_pc,
    input  wire        update_en,
    input  wire        actual_taken,
    output wire        predicted_taken
);
    reg [7:0]  ghr;           // Global History Register: 8-bit shift reg
    reg [1:0]  pht [0:255];   // Pattern History Table: 256 x 2-bit counter

    wire [7:0] pred_idx   = ghr ^ pc[7:0];
    wire [7:0] update_idx = ghr ^ update_pc[7:0];

    assign predicted_taken = pht[pred_idx][1]; // taken if WT or ST

    integer i;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            ghr <= 8'h0;
            for (i = 0; i < 256; i = i + 1)
                pht[i] <= 2'b01; // weakly not-taken
        end else if (update_en) begin
            $display("GHR UPDATE: PC=%h, Actual=%b, GHR_old=%h, idx=%h", update_pc, actual_taken, ghr, update_idx);
            // Update PHT with actual outcome (saturating counter)
            case (pht[update_idx])
                2'b00: pht[update_idx] <= actual_taken ? 2'b01 : 2'b00;
                2'b01: pht[update_idx] <= actual_taken ? 2'b10 : 2'b00;
                2'b10: pht[update_idx] <= actual_taken ? 2'b11 : 2'b01;
                2'b11: pht[update_idx] <= actual_taken ? 2'b11 : 2'b10;
            endcase
            // Shift GHR left and insert actual outcome at LSB
            ghr <= {ghr[6:0], actual_taken};
        end
    end
endmodule
