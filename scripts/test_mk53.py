"""
First-time connection and sanity check for the Binder MK53 climate chamber.

What this script verifies
─────────────────────────
1. Serial port opens and the chamber responds to a register read
2. Current temperature can be read
3. Active operating mode is readable
4. A temperature setpoint write round-trips correctly (writes then reads back)

Hardware requirement
────────────────────
USB-to-RS422 adapter connected to the MK53 rear panel RS-422 port.
Update VISA_ADDR and SLAVE_ADDR below before running.

Run:
    python scripts/test_mk53.py          (from project root)
    python scripts/test_mk53.py --help   (if you want usage notes)
"""

import sys
import os
import time

# ── make Python_Drivers importable without installing as a package ─────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Drivers'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mk53_driver import MK53

# ── Connection settings ────────────────────────────────────────────────────
VISA_ADDR  = 'ASRL3::INSTR'  # ← update COM port (check Device Manager, e.g. COM3 → ASRL3::INSTR)
SLAVE_ADDR = 1                # ← DIP switch address on MK53 rear panel
MIN_TEMP   = -40.0            # °C  safety limit
MAX_TEMP   = 180.0            # °C  safety limit

# ── simple colour-free pass/fail banner ───────────────────────────────────
PASS = '[PASS]'
FAIL = '[FAIL]'
INFO = '[INFO]'


def section(title: str):
    print(f'\n{"─" * 55}')
    print(f'  {title}')
    print('─' * 55)


def run():
    print('=' * 55)
    print('  Binder MK53 — First-Time Connection Test')
    print('=' * 55)
    print(f'{INFO} VISA resource : {VISA_ADDR}')
    print(f'{INFO} Slave address : {SLAVE_ADDR}')

    errors = []

    # ── 1. Open connection ─────────────────────────────────────────────────
    section('Step 1 — Open serial connection')
    try:
        chamber = MK53(
            VISA_ADDR,
            slave_address=SLAVE_ADDR,
            min_temp=MIN_TEMP,
            max_temp=MAX_TEMP,
        )
        print(f'{PASS} Port opened successfully')
    except Exception as exc:
        print(f'{FAIL} Could not open port: {exc}')
        print('\nCheck:')
        print('  • USB-to-RS422 adapter is plugged in')
        print(f'  • COM port matches Device Manager (currently: {VISA_ADDR})')
        print('  • No other program has the port open')
        sys.exit(1)

    with chamber:

        # ── 2. Read actual temperature ─────────────────────────────────────
        section('Step 2 — Read actual temperature')
        try:
            temp = chamber.get_temperature()
            print(f'{PASS} Actual temperature : {temp:.2f} °C')
            if temp < -50 or temp > 200:
                print(f'{FAIL} Temperature {temp:.2f}°C is outside expected physical range '
                      f'— check wiring or slave address')
                errors.append('Temperature out of physical range')
        except Exception as exc:
            print(f'{FAIL} Could not read temperature: {exc}')
            print('  Check: slave address matches DIP switch on rear panel')
            errors.append(f'Temperature read failed: {exc}')

        # ── 3. Read operating mode ─────────────────────────────────────────
        section('Step 3 — Read operating mode')
        try:
            mode = chamber.get_mode()
            print(f'{PASS} Operating mode : {mode}')
        except Exception as exc:
            print(f'{FAIL} Could not read mode register: {exc}')
            errors.append(f'Mode read failed: {exc}')

        # ── 4. Read current setpoint ───────────────────────────────────────
        section('Step 4 — Read temperature setpoint')
        try:
            setpt = chamber.get_temperature_setpoint()
            print(f'{PASS} Current setpoint : {setpt:.2f} °C')
        except Exception as exc:
            print(f'{FAIL} Could not read setpoint: {exc}')
            errors.append(f'Setpoint read failed: {exc}')

        # ── 5. Write setpoint and read back ───────────────────────────────
        # We write the same value that is already set so the chamber
        # temperature does not actually change.
        section('Step 5 — Setpoint write round-trip')
        try:
            # Read the current setpoint, then write it straight back
            current_sp = chamber.get_temperature_setpoint()
            chamber.set_temperature(current_sp)
            time.sleep(0.5)                     # small settling delay
            readback = chamber.get_temperature_setpoint()
            delta = abs(readback - current_sp)

            if delta < 0.1:                     # float round-trip tolerance
                print(f'{PASS} Wrote {current_sp:.2f}°C, read back {readback:.2f}°C '
                      f'(Δ = {delta:.3f}°C)')
            else:
                print(f'{FAIL} Write/read mismatch: wrote {current_sp:.2f}°C, '
                      f'got {readback:.2f}°C')
                errors.append('Setpoint write round-trip mismatch')
        except ValueError as exc:
            # set_temperature raises ValueError for out-of-range values
            print(f'{FAIL} Safety limit rejected the write: {exc}')
            errors.append(f'Setpoint write rejected: {exc}')
        except Exception as exc:
            print(f'{FAIL} Setpoint write failed: {exc}')
            errors.append(f'Setpoint write failed: {exc}')

        # ── 6. Wait for temperature stability ─────────────────────────────
        section('Step 6 — Wait for temperature stability')
        try:
            sp = chamber.get_temperature_setpoint()
            print(f'{INFO} Waiting for chamber to reach {sp:.2f}°C '
                  f'(±0.5°C for 60 s, timeout 15 min) ...')
            stable = chamber.wait_for_stability(
                setpoint_c=sp,
                tolerance_c=0.5,
                stable_seconds=60,
                timeout_seconds=900,
                poll_interval_s=5.0,
            )
            actual = chamber.get_temperature()
            if stable:
                print(f'{PASS} Stable at {actual:.2f}°C')
            else:
                print(f'{FAIL} Timed out — actual temp is {actual:.2f}°C, '
                      f'setpoint is {sp:.2f}°C')
                errors.append('Temperature stability timeout')
        except Exception as exc:
            print(f'{FAIL} Stability wait failed: {exc}')
            errors.append(f'Stability wait failed: {exc}')

        # ── 7. Identify (composed summary) ────────────────────────────────
        section('Step 7 — Instrument summary')
        try:
            print(chamber.identify())
        except Exception as exc:
            print(f'{FAIL} identify() failed: {exc}')

    # ── Final result ───────────────────────────────────────────────────────
    print('\n' + '=' * 55)
    if errors:
        print(f'  RESULT: FAIL  ({len(errors)} error(s))')
        for e in errors:
            print(f'  • {e}')
    else:
        print('  RESULT: PASS  — MK53 is communicating correctly')
    print('=' * 55)


if __name__ == '__main__':
    run()
