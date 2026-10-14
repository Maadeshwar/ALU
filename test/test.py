# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge


LOAD_A = 1 << 0
LOAD_B = 1 << 1
EXECUTE = 1 << 2


async def reset_dut(dut):
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)


async def load_operand(dut, control, value):
    dut.ui_in.value = value
    dut.uio_in.value = control
    await RisingEdge(dut.clk)
    dut.ui_in.value = 0
    dut.uio_in.value = 0


async def execute(dut, opcode):
    dut.uio_in.value = (opcode << 3) | EXECUTE
    await RisingEdge(dut.clk)
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 1)


async def run_operation(dut, a, b, opcode):
    await reset_dut(dut)
    await load_operand(dut, LOAD_A, a)
    await load_operand(dut, LOAD_B, b)
    await execute(dut, opcode)
    return int(dut.uo_out.value), int(dut.uio_out.value)


@cocotb.test()
async def test_project(dut):
    dut._log.info("Start")

    # 100 kHz simulation clock; the RTL behavior is synchronous and
    # independent of this particular simulation period.
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    # ADD: 20 + 30 = 50, no carry, non-zero.
    result, flags = await run_operation(dut, 20, 30, 0b000)
    assert result == 50
    assert (flags & 0x40) == 0
    assert (flags & 0x80) == 0

    # SUB: 50 - 20 = 30, no borrow, non-zero.
    result, flags = await run_operation(dut, 50, 20, 0b001)
    assert result == 30
    assert (flags & 0x40) == 0
    assert (flags & 0x80) == 0

    # ADD carry: 255 + 1 = 0 with carry set and zero set.
    result, flags = await run_operation(dut, 255, 1, 0b000)
    assert result == 0
    assert (flags & 0x40) != 0
    assert (flags & 0x80) != 0

    # SUB borrow: 1 - 2 = 255 with carry/borrow set.
    result, flags = await run_operation(dut, 1, 2, 0b001)
    assert result == 255
    assert (flags & 0x80) != 0
    assert (flags & 0x40) == 0

    # Logic operations.
    result, flags = await run_operation(dut, 0xAA, 0x0F, 0b010)
    assert result == 0x0A and (flags & 0xC0) == 0

    result, flags = await run_operation(dut, 0xAA, 0x0F, 0b011)
    assert result == 0xAF and (flags & 0xC0) == 0

    result, flags = await run_operation(dut, 0xAA, 0x0F, 0b100)
    assert result == 0xA5 and (flags & 0xC0) == 0

    # Shifts operate on A; B is loaded for a consistent operation sequence.
    result, flags = await run_operation(dut, 0x81, 0, 0b101)
    assert result == 0x02
    assert (flags & 0x80) != 0

    result, flags = await run_operation(dut, 0x81, 0, 0b110)
    assert result == 0x40
    assert (flags & 0x80) != 0

    # Compare: equal gives FF; unequal gives 00 and sets zero.
    result, flags = await run_operation(dut, 0x5A, 0x5A, 0b111)
    assert result == 0xFF and (flags & 0x40) == 0

    result, flags = await run_operation(dut, 0x5A, 0xA5, 0b111)
    assert result == 0x00 and (flags & 0x40) != 0

    dut._log.info("PASS: ALU arithmetic, logic, shifts, compare, and flags verified")
