`timescale 1ns/1ps

module tb_top;
    reg clk, rst;
    wire [31:0] cycles, branches, misses, stalls;

    // Clock: 10ns period
    initial clk = 0;
    always #5 clk = ~clk;

    // ── One DUT per predictor — change PREDICTOR_TYPE to test each ──
    // In a real run, compile 4 separate times changing PREDICTOR_TYPE
    // OR use a loop with generate blocks (shown below as single instance)

    `ifdef PRED
        parameter PRED_VAL = `PRED;
    `else
        parameter PRED_VAL = 2;
    `endif

    top #(.PREDICTOR_TYPE(PRED_VAL)) dut (
        .clk(clk), .rst(rst),
        .total_cycles(cycles),
        .total_branches(branches),
        .total_mispredictions(misses),
        .total_stalls(stalls)
    );

    // ── VCD dump for GTKWave ─────────────────────────────────────────
    initial begin
        $dumpfile("pipeline.vcd");
        $dumpvars(0, tb_top);
    end

    // ── Task: run one trace ──────────────────────────────────────────
    task run_trace;
        input [256*8-1:0] trace_file;
        input [256*8-1:0] trace_name;
        integer i;
        begin
            // Clear instruction memory to NOPs
            for (i=0; i<256; i=i+1) dut.u_imem.mem[i] = 32'h00000013;
            // Load trace into instruction memory
            $readmemh(trace_file, dut.u_imem.mem);

            // Reset pipeline
            rst = 1;
            repeat(3) @(posedge clk);
            rst = 0;

            // Run for 1000 cycles to allow loop completion
            repeat(1000) @(posedge clk);

            // Print results
            $display("==============================================");
            $display("TRACE:        %0s", trace_name);
            $display("PREDICTOR:    %0d  (0=static 1=1bit 2=2bit 3=ghr)",
                     PRED_VAL);
            $display("Total cycles: %0d", cycles);
            $display("Branches:     %0d", branches);
            $display("Mispredicts:  %0d", misses);
            $display("Stall cycles: %0d", stalls);
            if (branches > 0)
                $display("Miss rate:    %0d%%",
                         (misses * 100) / branches);
            else
                $display("Miss rate:    N/A");
            if (cycles > 0)
                $display("Eff. IPC:     (see analyze.py)");
            $display("==============================================");
        end
    endtask

    // ── Main simulation flow ─────────────────────────────────────────
    initial begin
        rst = 1;
        @(posedge clk);

        run_trace("tb/traces/loop_heavy.mem",     "loop_heavy");
        run_trace("tb/traces/dispatch_heavy.mem",  "dispatch_heavy");
        run_trace("tb/traces/mixed.mem",           "mixed");

        $display("Simulation complete. Open pipeline.vcd in GTKWave.");
        $finish;
    end
endmodule
