"""
First-time connection and sanity check for the Keysight E36441A 4-channel PSU.

What this script verifies
─────────────────────────
1. VISA connection opens and *IDN? returns the expected instrument
2. All 4 channels: voltage/current setpoints can be queried
3. APPLY command round-trip: write and read back V / I on CH1
4. CH1 output is enabled at 3.3 V / 0.1 A, measured, and disabled
5. OCP is enabled, tripped flag is read, protection is cleared
6. Digital pin function is queried (tests DIG subsystem comms)
7. Error queue is empty at end

!!! SAFETY !!!
The script briefly enables CH1 at 3.3 V / 0.1 A.
Disconnect any load from CH1 before running,
or adjust TEST_VOLTAGE / TEST_CURRENT below.

Run:
    python scripts/test_e36441a.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Drivers'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from e36441a_driver import E36441A

# ── Safe test values ───────────────────────────────────────────────────────
VISA_ADDR    = 'USB0::10893::52228::CN65510106::0::INSTR'  # ← update this
TEST_CHANNEL = 1
TEST_VOLTAGE = 3.3      # V
TEST_CURRENT = 0.1      # A

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
    print('  Keysight E36441A — First-Time Connection Test')
    print('=' * 60)
    print(f'{INFO} VISA resource : {VISA_ADDR}')
    print(f'{WARN} CH{TEST_CHANNEL} will be briefly enabled at '
          f'{TEST_VOLTAGE} V / {TEST_CURRENT} A.')

    errors = []

    # ── 1. Open connection ─────────────────────────────────────────────────
    section('Step 1 — Open VISA connection')
    try:
        psu = E36441A(VISA_ADDR)
        print(f'{PASS} Connection opened')
    except Exception as exc:
        print(f'{FAIL} Cannot open resource: {exc}')
        print('  → Update VISA_ADDR at the top of this script')
        sys.exit(1)

    with psu:

        # ── 2. *IDN? ──────────────────────────────────────────────────────
        section('Step 2 — *IDN? identification')
        try:
            idn = psu.identify()
            print(f'{PASS} {idn}')
            if 'E3644' not in idn and 'KEYSIGHT' not in idn.upper():
                print(f'      {WARN} IDN does not mention E36441A — verify address')
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

        # ── 4. Query all channel setpoints ────────────────────────────────
        section('Step 4 — Read all channel setpoints')
        for ch in range(1, E36441A.N_CHANNELS + 1):
            try:
                v = psu.get_voltage_setpoint(ch)
                i = psu.get_current_setpoint(ch)
                state = psu.get_output_state(ch)
                print(f'{PASS} CH{ch} : {v:.3f} V  {i:.4f} A  '
                      f'output={"ON" if state else "OFF"}')
            except Exception as exc:
                print(f'{FAIL} CH{ch} query failed: {exc}')
                errors.append(f'CH{ch} setpoint query failed: {exc}')

        # ── 5. APPLY round-trip on CH1 ────────────────────────────────────
        section(f'Step 5 — APPL write round-trip on CH{TEST_CHANNEL}')
        try:
            psu.apply(TEST_CHANNEL, TEST_VOLTAGE, TEST_CURRENT)
            time.sleep(0.2)
            v_rb = psu.get_voltage_setpoint(TEST_CHANNEL)
            i_rb = psu.get_current_setpoint(TEST_CHANNEL)

            v_ok = abs(v_rb - TEST_VOLTAGE) < 0.01
            i_ok = abs(i_rb - TEST_CURRENT) < 0.001

            print(f'{"[PASS]" if v_ok else "[FAIL]"} Voltage : '
                  f'wrote {TEST_VOLTAGE:.3f} V → read back {v_rb:.3f} V')
            print(f'{"[PASS]" if i_ok else "[FAIL]"} Current : '
                  f'wrote {TEST_CURRENT:.4f} A → read back {i_rb:.4f} A')

            if not v_ok:
                errors.append('Voltage setpoint round-trip mismatch')
            if not i_ok:
                errors.append('Current setpoint round-trip mismatch')
        except Exception as exc:
            print(f'{FAIL} APPLY failed: {exc}')
            errors.append(f'APPLY failed: {exc}')

        # ── 6. Enable output and measure ──────────────────────────────────
        section(f'Step 6 — Enable CH{TEST_CHANNEL} output and measure')
        print(f'{WARN} Enabling CH{TEST_CHANNEL} at {TEST_VOLTAGE} V / {TEST_CURRENT} A ...')
        try:
            psu.enable_output(TEST_CHANNEL)
            time.sleep(0.5)     # let output rail settle

            v_meas = psu.measure_voltage(TEST_CHANNEL)
            i_meas = psu.measure_current(TEST_CHANNEL)
            mode   = psu.get_regulation_mode(TEST_CHANNEL)

            print(f'{PASS} Measured : {v_meas:.4f} V  {i_meas:.5f} A  mode={mode}')

            # No load → CV mode, voltage close to setpoint
            if abs(v_meas - TEST_VOLTAGE) > 0.1:
                print(f'      {WARN} Output differs from setpoint by '
                      f'{abs(v_meas - TEST_VOLTAGE):.3f} V')

            print(f'{INFO} Output stays ON for 10 s — check the front panel ...')
            time.sleep(10)

            psu.disable_output(TEST_CHANNEL)
            print(f'{PASS} Output disabled')
        except Exception as exc:
            try:
                psu.disable_output(TEST_CHANNEL)
            except Exception:
                pass
            print(f'{FAIL} Output test failed: {exc}')
            errors.append(f'Output test failed: {exc}')

        # ── 7. OCP enable and trip flag ────────────────────────────────────
        section(f'Step 7 — OCP control on CH{TEST_CHANNEL}')
        try:
            psu.enable_ocp(TEST_CHANNEL)
            psu.set_ocp_delay(TEST_CHANNEL, 0.02)   # 20 ms delay (minimum)
            tripped = psu.ocp_tripped(TEST_CHANNEL)
            print(f'{PASS} OCP enabled, trip flag = {tripped} (False expected)')

            # Clear any latched protection state from earlier steps
            psu.clear_protection(TEST_CHANNEL)
            print(f'{PASS} Protection cleared')
        except Exception as exc:
            print(f'{FAIL} OCP test failed: {exc}')
            errors.append(f'OCP test failed: {exc}')

        # ── 8. Digital I/O pin query ───────────────────────────────────────
        section('Step 8 — Digital I/O pin function query (DIG subsystem)')
        try:
            # Just query — don't change the pin configuration
            # This confirms the DIG subsystem responds correctly
            for pin in (1, 2, 3):
                fn = psu.get_pin_function(pin)
                print(f'{PASS} DIG:PIN{pin} function : {fn}')
        except Exception as exc:
            print(f'{FAIL} DIG pin query failed: {exc}')
            errors.append(f'DIG pin query failed: {exc}')

        # ── 9. Output delay parameters ─────────────────────────────────────
        section(f'Step 9 — Output rise delay on CH{TEST_CHANNEL}')
        try:
            psu.set_output_delay_rise(TEST_CHANNEL, 0.0)   # 0 s delay
            print(f'{PASS} Rise delay set to 0.0 s')
        except Exception as exc:
            print(f'{FAIL} Rise delay failed: {exc}')
            errors.append(f'Rise delay failed: {exc}')

        # ── 10. Error queue ────────────────────────────────────────────────
        section('Step 10 — Check error queue')
        try:
            err = psu.get_error()
            if err.split(',')[0].strip() in ('0', '+0'):   # '+0,"No error"'
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
        print('  RESULT: PASS  — E36441A is communicating and working correctly')
    print('=' * 60)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(run())
