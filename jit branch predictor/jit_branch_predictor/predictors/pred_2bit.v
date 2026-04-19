module pred_2bit (
    input  wire        clk, rst,
    input  wire [31:0] pc,
    input  wire [31:0] update_pc,
    input  wire        update_en,
    input  wire        actual_taken,
    output wire        predicted_taken
);
    // States: SN=00, WN=01, WT=10, ST=11
    // predict taken if counter[1] = 1 (WT or ST)
    localparam SN = 2'b00; // strongly not-taken
    localparam WN = 2'b01; // weakly not-taken
    localparam WT = 2'b10; // weakly taken
    localparam ST = 2'b11; // strongly taken

    reg [1:0] pred_table [0:63]; // 64 entries, 2 bits each

    wire [5:0] pred_idx   = pc[7:2];
    wire [5:0] update_idx = update_pc[7:2];

    assign predicted_taken = pred_table[pred_idx][1]; // taken if WT or ST

    integer i;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            for (i = 0; i < 64; i = i + 1)
                pred_table[i] <= WN; // initialise weakly not-taken
        end else if (update_en) begin
            case (pred_table[update_idx])
                SN: pred_table[update_idx] <= actual_taken ? WN : SN;
                WN: pred_table[update_idx] <= actual_taken ? WT : SN;
                WT: pred_table[update_idx] <= actual_taken ? ST : WN;
                ST: pred_table[update_idx] <= actual_taken ? ST : WT;
            endcase
        end
    end
endmodule
