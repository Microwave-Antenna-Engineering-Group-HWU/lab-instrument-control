"""
First-time connection and sanity check for the Keysight E4980A LCR Meter.

What this script verifies
─────────────────────────
1. VISA connection opens and *IDN? returns the expected instrument
2. Built-in self-test passes
3. Measurement function can be set and queried back
4. Frequency can be set to 1 MHz and queried back
5. AC voltage level can be set and queried back
6. Aperture / integration time can be set
7. OPEN correction executes without error
8. SHORT correction executes without error
9. Capacitance measurement (Cp-D) at 1 MHz with open terminals
10. Source monitor returns AC voltage and current readings
11. Front-panel display text write and clear works
12. Error queue is empty after all steps

Hardware requirement
────────────────────
Keysight E4980A connected via GPIB, USB, or LAN.
Leave the measurement terminals OPEN for all steps (no DUT connected).
Update VISA_ADDR below to match the actual VISA address.

Run:
    python scripts/test_e4980a.py
"""

import sys
import os
import time

# ── make Python_Drivers importable ────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Drivers'))

from e4980a_driver import E4980A

# ── VISA address ──────────────────────────────────────────────────────────────
VISA_ADDR = 'GPIB0::17::INSTR'  # ← update to match your instrument

TEST_FREQ_HZ  = 1e6   # 1 MHz
TEST_VOLT_RMS = 1.0   # 1 V rms

PASS = '[PASS]'
FAIL = '[FAIL]'
INFO = '[INFO]'


def section(title: str):
    print(f'\n{"─" * 60}')
    print(f'  {title}')
    print('─' * 60)


def run():
    print('=' * 60)
    print('  Keysight E4980A LCR Meter — First-Time Connection Test')
    print('=' * 60)
    print(f'{INFO} VISA resource  : {VISA_ADDR}')
    print(f'{INFO} Test frequency : {TEST_FREQ_HZ / 1e6:.0f} MHz')
    print(f'{INFO} Test voltage   : {TEST_VOLT_RMS:.1f} V rms')
    print(f'{INFO} Terminals must be OPEN (no DUT) for all steps')

    errors = []

    # ── 1. Open connection ─────────────────────────────────────────────────────
    section('Step 1 — Open VISA connection')
    try:
        lcr = E4980A(VISA_ADDR)
        print(f'{PASS} Connection opened')
    except Exception as exc:
        print(f'{FAIL} Cannot open resource: {exc}')
        print('\nCheck:')
        print('  • Cable / GPIB address / USB driver (Zadig for USB)')
        print(f'  • VISA_ADDR is correct (currently: {VISA_ADDR})')
        print('  • pyvisa-py backend and pyusb / gpib-ctypes are installed')
        sys.exit(1)

    with lcr:

        # ── 2. *IDN? identification ────────────────────────────────────────────
        section('Step 2 — *IDN? identification')
        try:
            idn = lcr.identify()
            print(f'{PASS} {idn}')
            if 'E4980' not in idn:
                print(f'      WARNING: IDN does not contain "E4980" — '
                      f'verify you are connected to the right instrument')
        except Exception as exc:
            print(f'{FAIL} *IDN? failed: {exc}')
            errors.append(f'IDN failed: {exc}')

        # ── 3. Reset ───────────────────────────────────────────────────────────
        section('Step 3 — *RST + *CLS (reset to factory defaults)')
        try:
            lcr.reset()
            print(f'{PASS} Reset complete')
        except Exception as exc:
            print(f'{FAIL} Reset failed: {exc}')
            errors.append(f'Reset failed: {exc}')

        # ── 4. Self-test ───────────────────────────────────────────────────────
        section('Step 4 — Built-in self-test')
        print(f'{INFO} *TST? always returns 0 on the E4980A (by design)')
        try:
            passed = lcr.self_test()
            if passed:
                print(f'{PASS} Self-test returned 0 (pass)')
            else:
                print(f'{FAIL} Self-test returned non-zero')
                errors.append('Self-test failed')
        except Exception as exc:
            print(f'{FAIL} Self-test error: {exc}')
            errors.append(f'Self-test error: {exc}')

        # ── 5. Set and verify measurement function ─────────────────────────────
        section('Step 5 — Set measurement function to Cp-D')
        try:
            lcr.set_function('CPD')
            func = lcr.get_function()
            if 'CPD' in func.upper():
                print(f'{PASS} Function : {func}')
            else:
                print(f'{FAIL} Expected CPD, got: {func}')
                errors.append(f'Function readback mismatch: {func}')
        except Exception as exc:
            print(f'{FAIL} Function set/query failed: {exc}')
            errors.append(f'Function failed: {exc}')

        # ── 6. Set and verify test frequency ──────────────────────────────────
        section('Step 6 — Set test frequency to 1 MHz')
        try:
            lcr.set_frequency(TEST_FREQ_HZ)
            readback = lcr.get_frequency()
            if abs(readback - TEST_FREQ_HZ) / TEST_FREQ_HZ < 1e-4:
                print(f'{PASS} Frequency : {readback:.0f} Hz')
            else:
                print(f'{FAIL} Frequency readback {readback:.0f} Hz != {TEST_FREQ_HZ:.0f} Hz')
                errors.append(f'Frequency mismatch: {readback}')
        except Exception as exc:
            print(f'{FAIL} Frequency set/query failed: {exc}')
            errors.append(f'Frequency failed: {exc}')

        # ── 7. Set and verify AC voltage level ────────────────────────────────
        section('Step 7 — Set AC signal level to 1.0 V rms')
        try:
            lcr.set_voltage(TEST_VOLT_RMS)
            readback = lcr.get_voltage()
            if abs(readback - TEST_VOLT_RMS) < 0.01:
                print(f'{PASS} AC voltage : {readback:.3f} V rms')
            else:
                print(f'{FAIL} Voltage readback {readback:.3f} V != {TEST_VOLT_RMS:.3f} V')
                errors.append(f'Voltage mismatch: {readback}')
        except Exception as exc:
            print(f'{FAIL} Voltage set/query failed: {exc}')
            errors.append(f'Voltage failed: {exc}')

        # ── 8. Set aperture ────────────────────────────────────────────────────
        section('Step 8 — Set aperture (MEDIUM, 4 averages)')
        try:
            lcr.set_aperture('MEDium', averages=4)
            readback = lcr.get_aperture()
            print(f'{PASS} Aperture : {readback}')
        except Exception as exc:
            print(f'{FAIL} Aperture set failed: {exc}')
            errors.append(f'Aperture failed: {exc}')

        # ── 9. OPEN correction ─────────────────────────────────────────────────
        section('Step 9 — Execute OPEN correction (terminals open)')
        print(f'{INFO} Ensure measurement terminals are OPEN before continuing ...')
        time.sleep(1)
        try:
            lcr.execute_open_correction()
            lcr.wait_opc()
            lcr.set_open_correction(True)
            print(f'{PASS} OPEN correction executed and enabled')
        except Exception as exc:
            print(f'{FAIL} OPEN correction failed: {exc}')
            errors.append(f'OPEN correction failed: {exc}')

        # ── 10. SHORT correction ───────────────────────────────────────────────
        section('Step 10 — Execute SHORT correction')
        print(f'{INFO} NOTE: SHORT correction with open terminals gives meaningless data.')
        print(f'{INFO}       This step only verifies the command is accepted without error.')
        try:
            lcr.execute_short_correction()
            lcr.wait_opc()
            print(f'{PASS} SHORT correction command accepted (disable it — open terminals)')
            lcr.set_short_correction(False)
        except Exception as exc:
            print(f'{FAIL} SHORT correction failed: {exc}')
            errors.append(f'SHORT correction failed: {exc}')

        # ── 11. Capacitance measurement at 1 MHz ──────────────────────────────
        section('Step 11 — Capacitance measurement at 1 MHz (open terminals)')
        print(f'{INFO} Measuring Cp-D at {TEST_FREQ_HZ / 1e6:.0f} MHz with open terminals ...')
        try:
            lcr.set_impedance_range_auto(True)
            cp, d = lcr.measure()
            print(f'{PASS} Cp = {cp:.6e} F    D = {d:.6f}')
            if cp > 1e-6:
                print(f'      WARNING: Cp > 1 µF with open terminals — check connections')
            elif abs(cp) > 1e-9:
                print(f'      (stray capacitance of ~{cp * 1e12:.1f} pF — normal for open terminals)')
            else:
                print(f'      (very low stray capacitance — expected for open terminals)')
        except Exception as exc:
            print(f'{FAIL} Capacitance measurement failed: {exc}')
            errors.append(f'Capacitance measurement failed: {exc}')

        # ── 12. Take 5 repeated readings and show spread ──────────────────────
        section('Step 12 — Repeatability: 5 consecutive Cp readings at 1 MHz')
        try:
            readings = []
            for _ in range(5):
                cp, _ = lcr.measure()
                readings.append(cp)
            avg = sum(readings) / len(readings)
            spread = max(readings) - min(readings)
            print(f'{PASS} Cp readings : {[f"{r:.4e}" for r in readings]} F')
            print(f'       Average  : {avg:.6e} F')
            print(f'       Spread   : {spread:.3e} F')
        except Exception as exc:
            print(f'{FAIL} Repeat measurement failed: {exc}')
            errors.append(f'Repeat measurement failed: {exc}')

        # ── 13. Source monitor ─────────────────────────────────────────────────
        section('Step 13 — Source monitor (actual AC level at terminals)')
        try:
            mon = lcr.fetch_source_monitor()
            print(f'{PASS} VAC monitor : {mon["VAC"]:.4f} V rms')
            print(f'       IAC monitor : {mon["IAC"]:.4e} A rms')
        except Exception as exc:
            print(f'{FAIL} Source monitor failed: {exc}')
            errors.append(f'Source monitor failed: {exc}')

        # ── 14. Display test ───────────────────────────────────────────────────
        section('Step 14 — Front-panel display text')
        try:
            lcr.display_text('E4980A TEST OK')
            print(f'{PASS} Display text written — check front panel for "E4980A TEST OK"')
            time.sleep(2)
            lcr.display_text('')
            print(f'{PASS} Display text cleared')
        except Exception as exc:
            print(f'{FAIL} Display test failed: {exc}')
            errors.append(f'Display test failed: {exc}')

        # ── 15. Error queue ────────────────────────────────────────────────────
        section('Step 15 — Check error queue')
        try:
            err = lcr.get_error()
            if '+0' in err or 'No error' in err.lower():
                print(f'{PASS} Error queue : {err}  (no errors)')
            else:
                print(f'{FAIL} Error in queue : {err}')
                errors.append(f'Instrument error: {err}')
        except Exception as exc:
            print(f'{FAIL} Error query failed: {exc}')

    # ── Final result ───────────────────────────────────────────────────────────
    print('\n' + '=' * 60)
    if errors:
        print(f'  RESULT: FAIL  ({len(errors)} error(s))')
        for e in errors:
            print(f'  • {e}')
    else:
        print('  RESULT: PASS  — E4980A is communicating correctly')
    print('=' * 60)


if __name__ == '__main__':
    run()
