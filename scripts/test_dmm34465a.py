"""
First-time connection and sanity check for the Keysight 34465A DMM.

What this script verifies
─────────────────────────
1. VISA connection opens and *IDN? returns the expected instrument
2. Built-in self-test passes
3. DC voltage measurement works on AUTO range
4. AC voltage measurement works
5. Resistance measurement works (open terminals → overrange / 9.9E+37)
6. 4-wire resistance works (open terminals)
7. Continuity function works
8. Diode function works
9. Capacitance measurement works (open terminals → small value near zero)
10. Front panel display text write and clear works
11. Multi-sample acquisition (READ? average) works

Hardware requirement
────────────────────
Keysight 34465A connected via USB or GPIB or LAN.
Update VISA_ADDR below to match the actual VISA address.

Run:
    python scripts/test_dmm34465a.py
"""

import sys
import os

# ── make Python_Drivers and root config importable ────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Drivers'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dmm34465a_driver import DMM34465A

# ── VISA address ───────────────────────────────────────────────────────────
VISA_ADDR = 'USB0::10893::257::MY64039038::0::INSTR'  # ← update this

PASS = '[PASS]'
FAIL = '[FAIL]'
INFO = '[INFO]'


def section(title: str):
    print(f'\n{"─" * 60}')
    print(f'  {title}')
    print('─' * 60)


def run():
    print('=' * 60)
    print('  Keysight 34465A DMM — First-Time Connection Test')
    print('=' * 60)
    print(f'{INFO} VISA resource : {VISA_ADDR}')

    errors = []

    # ── 1. Open connection ─────────────────────────────────────────────────
    section('Step 1 — Open VISA connection')
    try:
        dmm = DMM34465A(VISA_ADDR)
        print(f'{PASS} Connection opened')
    except Exception as exc:
        print(f'{FAIL} Cannot open resource: {exc}')
        print('\nCheck:')
        print('  • USB cable is connected and WinUSB driver is installed (use Zadig)')
        print(f'  • DMM_RESOURCE in config.py is correct (currently: {VISA_ADDR})')
        print('  • pyvisa-py backend and pyusb are installed')
        sys.exit(1)

    with dmm:

        # ── 2. *IDN? identification ────────────────────────────────────────
        section('Step 2 — *IDN? identification')
        try:
            idn = dmm.identify()
            print(f'{PASS} {idn}')
            if '34465A' not in idn and '34461' not in idn:
                print(f'      WARNING: IDN does not contain "34465A" — '
                      f'verify you are connected to the right instrument')
        except Exception as exc:
            print(f'{FAIL} *IDN? failed: {exc}')
            errors.append(f'IDN failed: {exc}')

        # ── 3. Reset to known state ────────────────────────────────────────
        section('Step 3 — *RST + *CLS (reset to factory defaults)')
        try:
            dmm.reset()
            print(f'{PASS} Reset complete')
        except Exception as exc:
            print(f'{FAIL} Reset failed: {exc}')
            errors.append(f'Reset failed: {exc}')

        # ── 4. Self-test ───────────────────────────────────────────────────
        section('Step 4 — Built-in self-test')
        print(f'{INFO} Self-test takes up to 30 seconds ...')
        try:
            passed = dmm.self_test()
            if passed:
                print(f'{PASS} Self-test passed')
            else:
                print(f'{FAIL} Self-test FAILED — instrument may need calibration/service')
                errors.append('Self-test failed')
        except Exception as exc:
            print(f'{FAIL} Self-test error: {exc}')
            errors.append(f'Self-test error: {exc}')

        # ── 5. DC voltage — AUTO range, open terminals ─────────────────────
        section('Step 5 — DC voltage measurement (AUTO range, open terminals)')
        print(f'{INFO} Leave terminals open (floating) for this step')
        try:
            vdc = dmm.measure_vdc()
            print(f'{PASS} DC voltage : {vdc:.6f} V  '
                  f'(open-terminal result — near 0 V is expected)')
        except Exception as exc:
            print(f'{FAIL} DC voltage failed: {exc}')
            errors.append(f'VDC measurement failed: {exc}')

        # ── 6. AC voltage — AUTO range ─────────────────────────────────────
        section('Step 6 — AC voltage measurement (AUTO range, open terminals)')
        try:
            vac = dmm.measure_vac()
            print(f'{PASS} AC voltage : {vac:.6f} V  (near 0 V is expected)')
        except Exception as exc:
            print(f'{FAIL} AC voltage failed: {exc}')
            errors.append(f'VAC measurement failed: {exc}')

        # ── 7. 2-wire resistance — open terminals ──────────────────────────
        section('Step 7 — 2-wire resistance (open terminals → overrange)')
        try:
            res = dmm.measure_resistance()
            # Open circuit returns 9.9E+37 (overrange sentinel) or similar large value
            if res > 1e10:
                print(f'{PASS} Resistance : {res:.3e} Ω  (overrange — expected for open circuit)')
            else:
                print(f'{PASS} Resistance : {res:.3e} Ω')
        except Exception as exc:
            print(f'{FAIL} Resistance failed: {exc}')
            errors.append(f'Resistance measurement failed: {exc}')

        # ── 8. 4-wire resistance — open terminals ──────────────────────────
        section('Step 8 — 4-wire resistance (open terminals)')
        try:
            fres = dmm.measure_resistance_4w()
            if fres > 1e10:
                print(f'{PASS} 4W Resistance : {fres:.3e} Ω  (overrange — expected)')
            else:
                print(f'{PASS} 4W Resistance : {fres:.3e} Ω')
        except Exception as exc:
            print(f'{FAIL} 4W Resistance failed: {exc}')
            errors.append(f'4W resistance measurement failed: {exc}')

        # ── 9. Continuity ──────────────────────────────────────────────────
        section('Step 9 — Continuity (open terminals → overrange)')
        try:
            cont = dmm.measure_continuity()
            print(f'{PASS} Continuity : {cont:.3e} Ω  '
                  f'(>1000 Ω = open circuit, expected)')
        except Exception as exc:
            print(f'{FAIL} Continuity failed: {exc}')
            errors.append(f'Continuity failed: {exc}')

        # ── 10. Diode ─────────────────────────────────────────────────────
        section('Step 10 — Diode (open terminals)')
        try:
            diode = dmm.measure_diode()
            print(f'{PASS} Diode voltage : {diode:.4f} V  '
                  f'(overrange expected with open terminals)')
        except Exception as exc:
            print(f'{FAIL} Diode failed: {exc}')
            errors.append(f'Diode measurement failed: {exc}')

        # ── 11. Capacitance — open terminals ──────────────────────────────
        section('Step 11 — Capacitance (open terminals → near 0)')
        try:
            cap = dmm.measure_capacitance()
            print(f'{PASS} Capacitance : {cap:.3e} F  (small stray value expected)')
        except Exception as exc:
            print(f'{FAIL} Capacitance failed: {exc}')
            errors.append(f'Capacitance measurement failed: {exc}')

        # ── 12. Multi-sample acquisition ───────────────────────────────────
        section('Step 12 — Multi-sample acquisition (5 × DC voltage readings)')
        try:
            # Configure for DC voltage then take 5 readings using BUS trigger
            dmm.configure_vdc()
            readings = dmm.read_multi(count=5)
            avg = sum(readings) / len(readings)
            print(f'{PASS} 5 readings : {[f"{r:.4f}" for r in readings]} V')
            print(f'       Average : {avg:.6f} V')
        except Exception as exc:
            print(f'{FAIL} Multi-sample failed: {exc}')
            errors.append(f'Multi-sample acquisition failed: {exc}')

        # ── 13. Display test ───────────────────────────────────────────────
        section('Step 13 — Front panel display text')
        try:
            dmm.display_text('DRIVER TEST OK')
            print(f'{PASS} Display text written — check front panel for "DRIVER TEST OK"')
            import time; time.sleep(2)
            dmm.clear_display_text()
            print(f'{PASS} Display cleared')
        except Exception as exc:
            print(f'{FAIL} Display failed: {exc}')
            errors.append(f'Display test failed: {exc}')

        # ── 14. Error queue check ──────────────────────────────────────────
        section('Step 14 — Check error queue')
        try:
            err = dmm.get_error()
            if '+0' in err or 'No error' in err.lower():
                print(f'{PASS} Error queue : {err}  (no errors)')
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
        print('  RESULT: PASS  — 34465A is communicating correctly')
    print('=' * 60)


if __name__ == '__main__':
    run()
