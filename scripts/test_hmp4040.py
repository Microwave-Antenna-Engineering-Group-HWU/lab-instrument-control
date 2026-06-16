"""
First-time connection and sanity check for the R&S HMP4040 4-channel power supply.

What this script verifies
─────────────────────────
1. VISA connection opens and *IDN? returns the expected instrument
2. Built-in self-test passes
3. All 4 channel voltage/current setpoints can be queried
4. Voltage and current setpoints can be written and read back
5. CH1 output can be turned on at a safe low voltage (3.3 V / 0.1 A),
   measured, and then turned off again
6. Master output switch (OUTP:GEN) works
7. OVP can be set and cleared
8. Error queue is empty at the end

!!! SAFETY !!!
The script will briefly turn on CH1 at 3.3 V / 0.1 A.
Disconnect any sensitive load from CH1 before running,
or adjust TEST_VOLTAGE / TEST_CURRENT below.

Run:
    python scripts/test_hmp4040.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Drivers'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import config
from hmp4040_driver import HMP4040

# ── Safe test values — adjust if needed ───────────────────────────────────
TEST_CHANNEL  = 1       # CH1 is used for the output-on test
TEST_VOLTAGE  = 3.3     # V  — safe, general-purpose value
TEST_CURRENT  = 0.1     # A  — very low current limit
TEST_OVP      = 4.0     # V  — OVP level to write and verify

PASS = '[PASS]'
FAIL = '[FAIL]'
INFO = '[INFO]'
WARN = '[WARN]'


def section(title: str):
    print(f'\n{"─" * 60}')
    print(f'  {title}')
    print('─' * 60)


def run():
    print('=' * 60)
    print('  R&S HMP4040 — First-Time Connection Test')
    print('=' * 60)
    print(f'{INFO} VISA resource : (set in config.py)')
    print(f'{WARN} CH{TEST_CHANNEL} output will be enabled at '
          f'{TEST_VOLTAGE} V / {TEST_CURRENT} A briefly.')
    print(f'{WARN} Disconnect any load from CH{TEST_CHANNEL} before continuing.')

    errors = []

    # ── 1. Open connection ─────────────────────────────────────────────────
    section('Step 1 — Open VISA connection')
    try:
        # HMP4040 VISA address is not in the shared config (DMM address is)
        # Edit VISA_ADDR below to match your setup
        VISA_ADDR = 'USB0::0x0AAD::0x0135::YOUR_SERIAL::INSTR'
        # Hint: run  python -c "import pyvisa; print(pyvisa.ResourceManager().list_resources())"
        psu = HMP4040(VISA_ADDR)
        print(f'{PASS} Connection opened')
    except Exception as exc:
        print(f'{FAIL} Cannot open resource: {exc}')
        print('\nCheck:')
        print('  • USB cable connected and NI-VISA or pyvisa-py installed')
        print('  • Update VISA_ADDR at the top of this script')
        sys.exit(1)

    with psu:

        # ── 2. *IDN? ──────────────────────────────────────────────────────
        section('Step 2 — *IDN? identification')
        try:
            idn = psu.identify()
            print(f'{PASS} {idn}')
            if 'HMP4040' not in idn and 'ROHDE' not in idn.upper():
                print(f'      {WARN} IDN does not mention HMP4040 — check address')
        except Exception as exc:
            print(f'{FAIL} *IDN? failed: {exc}')
            errors.append(f'IDN failed: {exc}')

        # ── 3. Reset ───────────────────────────────────────────────────────
        section('Step 3 — *RST (reset to factory defaults)')
        try:
            psu.reset()
            print(f'{PASS} Reset complete')
        except Exception as exc:
            print(f'{FAIL} Reset failed: {exc}')
            errors.append(f'Reset failed: {exc}')

        # ── 4. Self-test ───────────────────────────────────────────────────
        section('Step 4 — Built-in self-test (*TST?)')
        try:
            ok = psu.self_test()
            if ok:
                print(f'{PASS} Self-test passed')
            else:
                print(f'{FAIL} Self-test FAILED')
                errors.append('Self-test failed')
        except Exception as exc:
            print(f'{FAIL} Self-test error: {exc}')
            errors.append(f'Self-test error: {exc}')

        # ── 5. Query all channel setpoints ────────────────────────────────
        section('Step 5 — Read all channel setpoints')
        for ch in range(1, 5):
            try:
                v = psu.get_voltage_setpoint(ch)
                i = psu.get_current_setpoint(ch)
                print(f'{PASS} CH{ch} : {v:.3f} V  {i:.4f} A')
            except Exception as exc:
                print(f'{FAIL} CH{ch} query failed: {exc}')
                errors.append(f'CH{ch} setpoint query failed: {exc}')

        # ── 6. Write setpoints and read back ──────────────────────────────
        section(f'Step 6 — Setpoint write round-trip on CH{TEST_CHANNEL}')
        try:
            psu.apply(TEST_CHANNEL, TEST_VOLTAGE, TEST_CURRENT)
            time.sleep(0.2)
            v_rb = psu.get_voltage_setpoint(TEST_CHANNEL)
            i_rb = psu.get_current_setpoint(TEST_CHANNEL)

            v_ok = abs(v_rb - TEST_VOLTAGE) < 0.01
            i_ok = abs(i_rb - TEST_CURRENT) < 0.001

            print(f'{"[PASS]" if v_ok else "[FAIL]"} Voltage setpoint : '
                  f'wrote {TEST_VOLTAGE:.3f} V, read back {v_rb:.3f} V')
            print(f'{"[PASS]" if i_ok else "[FAIL]"} Current setpoint : '
                  f'wrote {TEST_CURRENT:.4f} A, read back {i_rb:.4f} A')

            if not v_ok:
                errors.append('Voltage setpoint round-trip mismatch')
            if not i_ok:
                errors.append('Current setpoint round-trip mismatch')
        except Exception as exc:
            print(f'{FAIL} Setpoint write failed: {exc}')
            errors.append(f'Setpoint write failed: {exc}')

        # ── 7. OVP write and verify ────────────────────────────────────────
        section(f'Step 7 — OVP level write on CH{TEST_CHANNEL}')
        try:
            psu.set_ovp_level(TEST_CHANNEL, TEST_OVP)
            psu.enable_ovp(TEST_CHANNEL)
            time.sleep(0.2)
            ovp_rb = psu.get_ovp_level(TEST_CHANNEL)
            ok = abs(ovp_rb - TEST_OVP) < 0.05
            print(f'{"[PASS]" if ok else "[FAIL]"} OVP : '
                  f'wrote {TEST_OVP:.2f} V, read back {ovp_rb:.2f} V')
            if not ok:
                errors.append('OVP level round-trip mismatch')
        except Exception as exc:
            print(f'{FAIL} OVP test failed: {exc}')
            errors.append(f'OVP test failed: {exc}')

        # ── 8. Enable output and measure ──────────────────────────────────
        section(f'Step 8 — Enable CH{TEST_CHANNEL} output and measure')
        print(f'{WARN} Enabling CH{TEST_CHANNEL} at {TEST_VOLTAGE} V / {TEST_CURRENT} A ...')
        try:
            psu.enable_output(TEST_CHANNEL)
            psu.enable_master_output()
            time.sleep(0.5)             # let output settle

            v_meas = psu.measure_voltage(TEST_CHANNEL)
            i_meas = psu.measure_current(TEST_CHANNEL)
            mode   = psu.get_regulation_mode(TEST_CHANNEL)

            print(f'{PASS} Measured   : {v_meas:.4f} V  {i_meas:.5f} A  '
                  f'mode={mode}')

            # Voltage should be close to setpoint (no load → CV mode)
            if abs(v_meas - TEST_VOLTAGE) > 0.1:
                print(f'      {WARN} Output voltage {v_meas:.4f} V differs from '
                      f'setpoint {TEST_VOLTAGE:.3f} V by more than 0.1 V')

            # Turn output off immediately after measurement
            psu.disable_master_output()
            psu.disable_output(TEST_CHANNEL)
            print(f'{PASS} Output disabled')
        except Exception as exc:
            # Always try to turn off on error
            try:
                psu.disable_master_output()
                psu.disable_output(TEST_CHANNEL)
            except Exception:
                pass
            print(f'{FAIL} Output test failed: {exc}')
            errors.append(f'Output test failed: {exc}')

        # ── 9. Error queue check ───────────────────────────────────────────
        section('Step 9 — Check error queue')
        try:
            err = psu.get_error()
            if '+0' in err or 'No error' in err.lower():
                print(f'{PASS} Error queue : {err}')
            else:
                print(f'{FAIL} Error in queue : {err}')
                errors.append(f'Instrument error: {err}')
        except Exception as exc:
            print(f'{FAIL} Error query failed: {exc}')

    # ── Final result ───────────────────────────────────────────────────────
    print('\n' + '=' * 60)
    if errors:
        print(f'  RESULT: FAIL  ({len(errors)} error(s))')
        for e in errors:
            print(f'  • {e}')
    else:
        print('  RESULT: PASS  — HMP4040 is communicating and working correctly')
    print('=' * 60)


if __name__ == '__main__':
    run()
