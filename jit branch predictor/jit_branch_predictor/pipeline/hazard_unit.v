module hazard_unit (
    input  wire        ex_mem_read,      // ID/EX stage: is it a LOAD?
    input  wire [4:0]  ex_rd,            // ID/EX stage: destination reg
    input  wire [4:0]  id_rs1, id_rs2,  // IF/ID stage: source regs
    output wire        stall             // freeze IF/ID, insert NOP in ID/EX
);
    // Load-use hazard: instruction in EX is loading into a reg
    // that the instruction in ID needs to read
    assign stall = ex_mem_read &&
                   ((ex_rd == id_rs1) || (ex_rd == id_rs2)) &&
                   (ex_rd != 5'b0);
endmodule
