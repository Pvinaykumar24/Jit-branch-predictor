// ============================================================
//  tb_dynamic.v  — Dynamic User-Code JIT Showcase Testbench
//  Loads user_naive.mem and user_jit.mem at runtime.
//  Run: vvp dynamic_sim.exe
// ============================================================
`timescale 1ns/1ps

module tb_dynamic;

    parameter CLK_PERIOD = 10;
    parameter SIM_CYCLES = 2000;

    // ── Clocks & resets ─────────────────────────────────────
    reg clk0, rst0;
    reg clk1, rst1;
    reg clk2, rst2;
    reg clk3, rst3;

    // ── Performance counter outputs ─────────────────────────
    wire [31:0] cyc0, br0, mis0, st0;
    wire [31:0] cyc1, br1, mis1, st1;
    wire [31:0] cyc2, br2, mis2, st2;
    wire [31:0] cyc3, br3, mis3, st3;

    // ── DUT instances (one per predictor) ──────────────────
    top #(.PREDICTOR_TYPE(0)) u0 (.clk(clk0),.rst(rst0),
        .total_cycles(cyc0),.total_branches(br0),
        .total_mispredictions(mis0),.total_stalls(st0));

    top #(.PREDICTOR_TYPE(1)) u1 (.clk(clk1),.rst(rst1),
        .total_cycles(cyc1),.total_branches(br1),
        .total_mispredictions(mis1),.total_stalls(st1));

    top #(.PREDICTOR_TYPE(2)) u2 (.clk(clk2),.rst(rst2),
        .total_cycles(cyc2),.total_branches(br2),
        .total_mispredictions(mis2),.total_stalls(st2));

    top #(.PREDICTOR_TYPE(3)) u3 (.clk(clk3),.rst(rst3),
        .total_cycles(cyc3),.total_branches(br3),
        .total_mispredictions(mis3),.total_stalls(st3));

    // ── Clock generation ────────────────────────────────────
    initial clk0 = 0; always #(CLK_PERIOD/2) clk0 = ~clk0;
    initial clk1 = 0; always #(CLK_PERIOD/2) clk1 = ~clk1;
    initial clk2 = 0; always #(CLK_PERIOD/2) clk2 = ~clk2;
    initial clk3 = 0; always #(CLK_PERIOD/2) clk3 = ~clk3;

    // ── Result storage [exp 0=naive, 1=jit][predictor 0-3] ─
    integer cycles_r    [0:1][0:3];
    integer branches_r  [0:1][0:3];
    integer mispred_r   [0:1][0:3];
    integer stalls_r    [0:1][0:3];
    real    ipc_r       [0:1][0:3];
    real    misrate_r   [0:1][0:3];

    // ── Tasks ───────────────────────────────────────────────
    task reset_all;
        begin
            rst0=1; rst1=1; rst2=1; rst3=1;
            repeat(4) @(posedge clk0);
            rst0=0; rst1=0; rst2=0; rst3=0;
        end
    endtask

    task load_trace;
        input [511:0] path;
        begin
            $readmemh(path, u0.u_imem.mem);
            $readmemh(path, u1.u_imem.mem);
            $readmemh(path, u2.u_imem.mem);
            $readmemh(path, u3.u_imem.mem);
        end
    endtask

    task run_and_capture;
        input integer n_cycles;
        input integer exp_idx;
        integer c;
        begin
            for (c = 0; c < n_cycles; c = c + 1)
                @(posedge clk0);

            cycles_r  [exp_idx][0] = cyc0; branches_r[exp_idx][0] = br0;
            mispred_r [exp_idx][0] = mis0; stalls_r  [exp_idx][0] = st0;
            cycles_r  [exp_idx][1] = cyc1; branches_r[exp_idx][1] = br1;
            mispred_r [exp_idx][1] = mis1; stalls_r  [exp_idx][1] = st1;
            cycles_r  [exp_idx][2] = cyc2; branches_r[exp_idx][2] = br2;
            mispred_r [exp_idx][2] = mis2; stalls_r  [exp_idx][2] = st2;
            cycles_r  [exp_idx][3] = cyc3; branches_r[exp_idx][3] = br3;
            mispred_r [exp_idx][3] = mis3; stalls_r  [exp_idx][3] = st3;

            ipc_r[exp_idx][0] = (cyc0>0) ? (1.0*(cyc0-st0)/cyc0) : 0;
            ipc_r[exp_idx][1] = (cyc1>0) ? (1.0*(cyc1-st1)/cyc1) : 0;
            ipc_r[exp_idx][2] = (cyc2>0) ? (1.0*(cyc2-st2)/cyc2) : 0;
            ipc_r[exp_idx][3] = (cyc3>0) ? (1.0*(cyc3-st3)/cyc3) : 0;

            misrate_r[exp_idx][0] = (br0>0) ? (100.0*mis0/br0) : 0;
            misrate_r[exp_idx][1] = (br1>0) ? (100.0*mis1/br1) : 0;
            misrate_r[exp_idx][2] = (br2>0) ? (100.0*mis2/br2) : 0;
            misrate_r[exp_idx][3] = (br3>0) ? (100.0*mis3/br3) : 0;
        end
    endtask

    // ── Main ────────────────────────────────────────────────
    initial begin : main
        // Exp 0: User Naive (Python-style unoptimized)
        load_trace("tb/traces/user_naive.mem");
        reset_all;
        run_and_capture(SIM_CYCLES, 0);

        // Exp 1: JIT-Optimized version
        load_trace("tb/traces/user_jit.mem");
        reset_all;
        run_and_capture(SIM_CYCLES, 1);

        // CSV output for Python parser
        $display("DYNAMIC_CSV_START");
        $display("exp,predictor,cycles,branches,mispredictions,wasted_cycles,mispredict_rate,ipc");
        $display("Naive,Static,%0d,%0d,%0d,%0d,%.2f,%.4f",
            cycles_r[0][0],branches_r[0][0],mispred_r[0][0],stalls_r[0][0],misrate_r[0][0],ipc_r[0][0]);
        $display("Naive,1-Bit,%0d,%0d,%0d,%0d,%.2f,%.4f",
            cycles_r[0][1],branches_r[0][1],mispred_r[0][1],stalls_r[0][1],misrate_r[0][1],ipc_r[0][1]);
        $display("Naive,2-Bit,%0d,%0d,%0d,%0d,%.2f,%.4f",
            cycles_r[0][2],branches_r[0][2],mispred_r[0][2],stalls_r[0][2],misrate_r[0][2],ipc_r[0][2]);
        $display("Naive,GHR,%0d,%0d,%0d,%0d,%.2f,%.4f",
            cycles_r[0][3],branches_r[0][3],mispred_r[0][3],stalls_r[0][3],misrate_r[0][3],ipc_r[0][3]);
        $display("JIT,Static,%0d,%0d,%0d,%0d,%.2f,%.4f",
            cycles_r[1][0],branches_r[1][0],mispred_r[1][0],stalls_r[1][0],misrate_r[1][0],ipc_r[1][0]);
        $display("JIT,1-Bit,%0d,%0d,%0d,%0d,%.2f,%.4f",
            cycles_r[1][1],branches_r[1][1],mispred_r[1][1],stalls_r[1][1],misrate_r[1][1],ipc_r[1][1]);
        $display("JIT,2-Bit,%0d,%0d,%0d,%0d,%.2f,%.4f",
            cycles_r[1][2],branches_r[1][2],mispred_r[1][2],stalls_r[1][2],misrate_r[1][2],ipc_r[1][2]);
        $display("JIT,GHR,%0d,%0d,%0d,%0d,%.2f,%.4f",
            cycles_r[1][3],branches_r[1][3],mispred_r[1][3],stalls_r[1][3],misrate_r[1][3],ipc_r[1][3]);
        $display("DYNAMIC_CSV_END");

        $finish;
    end

endmodule
