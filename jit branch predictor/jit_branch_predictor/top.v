`ifdef PRED
module top #(
    parameter PREDICTOR_TYPE = `PRED
)(
`else
module top #(
    parameter PREDICTOR_TYPE = 2   // 0=static 1=1bit 2=2bit 3=ghr
)(
`endif
    input wire clk, rst,
    // Stat outputs — read by testbench
    output reg [31:0] total_cycles,
    output reg [31:0] total_branches,
    output reg [31:0] total_mispredictions,
    output reg [31:0] total_stalls
);
    // ── Wires connecting all stages ──────────────────────────────────

    // IF stage
    wire [31:0] if_pc, if_pc_plus4;
    wire [31:0] if_instr;

    // IF/ID register outputs
    wire [31:0] id_pc, id_instr;
    wire        id_predicted_taken;

    // ID stage outputs
    wire [4:0]  id_rs1, id_rs2, id_rd;
    wire [31:0] id_imm, id_rdata1, id_rdata2;
    wire [3:0]  id_alu_op;
    wire        id_mem_read, id_mem_write, id_reg_write;
    wire        id_is_branch, id_branch_type;

    // ID/EX register outputs
    wire [31:0] ex_pc, ex_rdata1, ex_rdata2, ex_imm;
    wire [4:0]  ex_rs1, ex_rs2, ex_rd;
    wire [3:0]  ex_alu_op;
    wire        ex_mem_read, ex_mem_write, ex_reg_write;
    wire        ex_is_branch, ex_branch_type;
    wire        ex_predicted_taken;

    // EX stage outputs
    wire [31:0] ex_alu_result;
    wire        ex_branch_taken;
    wire [31:0] ex_branch_target;

    // EX/MEM register outputs
    wire [31:0] mem_alu_result, mem_rdata2;
    wire [4:0]  mem_rd;
    wire        mem_mem_read, mem_mem_write, mem_reg_write;

    // MEM/WB outputs
    wire [31:0] mem_data_out;
    wire [31:0] wb_data;
    wire [4:0]  wb_rd;
    wire        wb_we;

    // Control signals
    wire stall, flush, mispredicted;
    wire [31:0] actual_target;

    // Predictor signals
    wire        predicted_taken;
    wire        if_is_branch = (if_instr[6:0] == 7'b1100011);
    wire        actual_predicted_taken = if_is_branch && predicted_taken;
    wire [31:0] if_imm = {{20{if_instr[31]}}, if_instr[7], if_instr[30:25], if_instr[11:8], 1'b0};
    wire [31:0] if_predicted_target = if_pc + if_imm;

    // Forwarding signals
    wire [31:0] fwd_a, fwd_b;
    wire        use_fwd_a, use_fwd_b;

    // ── Module Instantiations ────────────────────────────────────────

    instr_mem u_imem (
        .clk(clk), .addr(if_pc), .instr(if_instr));

    data_mem u_dmem (
        .clk(clk), .we(mem_mem_write),
        .addr(mem_alu_result), .wdata(mem_rdata2),
        .rdata(mem_data_out));

    if_stage u_if (
        .clk(clk), .rst(rst), .stall(stall), .flush(flush),
        .predicted_taken(actual_predicted_taken),
        .predicted_target(if_predicted_target),
        .actual_target(actual_target),
        .mispredicted(mispredicted),
        .pc(if_pc), .pc_plus4(if_pc_plus4));

    if_id_reg u_if_id (
        .clk(clk), .rst(rst), .stall(stall), .flush(flush),
        .if_pc(if_pc), .if_instr(if_instr),
        .if_predicted_taken(actual_predicted_taken),
        .id_pc(id_pc), .id_instr(id_instr),
        .id_predicted_taken(id_predicted_taken));

    id_stage u_id (
        .instr(id_instr), .pc(id_pc),
        .rs1(id_rs1), .rs2(id_rs2), .rd(id_rd), .imm(id_imm),
        .alu_op(id_alu_op), .mem_read(id_mem_read),
        .mem_write(id_mem_write), .reg_write(id_reg_write),
        .is_branch(id_is_branch), .branch_type(id_branch_type));

    register_file u_rf (
        .clk(clk), .we(wb_we),
        .rs1(id_rs1), .rs2(id_rs2), .rd(wb_rd),
        .wdata(wb_data), .rdata1(id_rdata1), .rdata2(id_rdata2));

    id_ex_reg u_id_ex (
        .clk(clk), .rst(rst), .flush(flush),
        .id_pc(id_pc), .id_rdata1(id_rdata1), .id_rdata2(id_rdata2),
        .id_imm(id_imm), .id_rs1(id_rs1), .id_rs2(id_rs2),
        .id_rd(id_rd), .id_alu_op(id_alu_op),
        .id_mem_read(id_mem_read), .id_mem_write(id_mem_write),
        .id_reg_write(id_reg_write), .id_is_branch(id_is_branch),
        .id_branch_type(id_branch_type),
        .id_predicted_taken(id_predicted_taken),
        .ex_pc(ex_pc), .ex_rdata1(ex_rdata1), .ex_rdata2(ex_rdata2),
        .ex_imm(ex_imm), .ex_rs1(ex_rs1), .ex_rs2(ex_rs2),
        .ex_rd(ex_rd), .ex_alu_op(ex_alu_op),
        .ex_mem_read(ex_mem_read), .ex_mem_write(ex_mem_write),
        .ex_reg_write(ex_reg_write), .ex_is_branch(ex_is_branch),
        .ex_branch_type(ex_branch_type),
        .ex_predicted_taken(ex_predicted_taken));

    ex_stage u_ex (
        .pc(ex_pc), .rdata1(ex_rdata1), .rdata2(ex_rdata2),
        .imm(ex_imm), .alu_op(ex_alu_op),
        .is_branch(ex_is_branch), .branch_type(ex_branch_type),
        .fwd_a(fwd_a), .fwd_b(fwd_b),
        .use_fwd_a(use_fwd_a), .use_fwd_b(use_fwd_b),
        .alu_result(ex_alu_result),
        .branch_taken(ex_branch_taken),
        .branch_target(ex_branch_target));

    ex_mem_reg u_ex_mem (
        .clk(clk), .rst(rst),
        .ex_alu_result(ex_alu_result), .ex_rdata2(ex_rdata2),
        .ex_rd(ex_rd), .ex_mem_read(ex_mem_read),
        .ex_mem_write(ex_mem_write), .ex_reg_write(ex_reg_write),
        .mem_alu_result(mem_alu_result), .mem_rdata2(mem_rdata2),
        .mem_rd(mem_rd), .mem_mem_read(mem_mem_read),
        .mem_mem_write(mem_mem_write), .mem_reg_write(mem_reg_write));

    mem_wb_stage u_mem_wb (
        .alu_result(mem_alu_result), .mem_rdata(mem_data_out),
        .rd(mem_rd), .mem_read(mem_mem_read), .reg_write(mem_reg_write),
        .wb_data(wb_data), .wb_rd(wb_rd), .wb_we(wb_we));

    hazard_unit u_haz (
        .ex_mem_read(ex_mem_read), .ex_rd(ex_rd),
        .id_rs1(id_rs1), .id_rs2(id_rs2), .stall(stall));

    forwarding_unit u_fwd (
        .ex_rs1(ex_rs1), .ex_rs2(ex_rs2),
        .mem_rd(mem_rd), .mem_reg_write(mem_reg_write),
        .mem_alu_result(mem_alu_result),
        .wb_rd(wb_rd), .wb_reg_write(wb_we), .wb_data(wb_data),
        .fwd_a(fwd_a), .fwd_b(fwd_b),
        .use_fwd_a(use_fwd_a), .use_fwd_b(use_fwd_b));

    flush_control u_flush (
        .ex_is_branch(ex_is_branch),
        .branch_taken(ex_branch_taken),
        .predicted_taken(ex_predicted_taken),
        .branch_target(ex_branch_target),
        .ex_pc(ex_pc),
        .flush(flush), .mispredicted(mispredicted),
        .actual_target(actual_target));

    predictor_if #(.PREDICTOR_TYPE(PREDICTOR_TYPE)) u_pred (
        .clk(clk), .rst(rst),
        .fetch_pc(if_pc),
        .update_pc(ex_pc),
        .update_en(ex_is_branch),
        .actual_taken(ex_branch_taken),
        .predicted_taken(predicted_taken));

    // ── Performance Counters ─────────────────────────────────────────
    // flush = branch misprediction → 2 wasted cycles (IF+ID bubbles)
    // stall = load-use hazard     → 1 wasted cycle
    // flush takes priority; both cannot cause double-count in same cycle
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            total_cycles         <= 0;
            total_branches       <= 0;
            total_mispredictions <= 0;
            total_stalls         <= 0;
        end else begin
            total_cycles <= total_cycles + 1;
            if (ex_is_branch) begin
                total_branches <= total_branches + 1;
                if (mispredicted)
                    total_mispredictions <= total_mispredictions + 1;
            end
            if (flush)
                total_stalls <= total_stalls + 2; // 2-cycle flush penalty
            else if (stall)
                total_stalls <= total_stalls + 1; // 1-cycle stall penalty
        end
    end
endmodule
