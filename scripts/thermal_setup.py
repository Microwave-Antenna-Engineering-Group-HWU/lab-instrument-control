"""
Thermal test setup script.

Sequence
────────
1. Connect to E36441A PSU  →  set CH1 to 12 V / 1 A limit  →  enable output
2. Connect to 34465A DMM   →  measure VDD (DC voltage on CH1 output)
3. Connect to MK53 chamber →  set setpoint to 20 °C

The script then exits.  All three instruments keep their configured state
after the VISA / serial connections are closed — the PSU continues to
output 12 V and the chamber continues running toward 20 °C.

Run:
    python scripts/thermal_setup.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python_Drivers'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from e36441a_driver import E36441A
from dmm34465a_driver import DMM34465A
from mk53_driver import MK53

# ── Fixed instrument addresses (confirmed from individual sanity scripts) ──────
PSU_ADDR     = 'USB0::10893::52228::CN65510106::0::INSTR'
DMM_ADDR     = 'USB0::10893::257::MY64039038::0::INSTR'
MK53_ADDR    = 'ASRL3::INSTR'
MK53_SLAVE   = 1

# ── Test parameters ────────────────────────────────────────────────────────────
PSU_CHANNEL   = 1
PSU_VOLTAGE   = 12.0    # V
PSU_CURRENT   = 1.0     # A  (limit)
CHAMBER_TEMP  = 20.0    # °C
DMM_RANGE     = 20      # V  (covers 12 V supply rail)

print('=' * 55)
print('  Thermal Test Setup')
print('=' * 55)

# ── Step 1 — Power supply ──────────────────────────────────────────────────────
print('\n[1/3] Power supply (E36441A)')
try:
    with E36441A(PSU_ADDR) as psu:
        psu.apply(PSU_CHANNEL, PSU_VOLTAGE, PSU_CURRENT)
        psu.enable_output(PSU_CHANNEL)
        v_set = psu.get_voltage_setpoint(PSU_CHANNEL)
        i_set = psu.get_current_setpoint(PSU_CHANNEL)
        v_out = psu.measure_voltage(PSU_CHANNEL)
        i_out = psu.measure_current(PSU_CHANNEL)
        mode  = psu.get_regulation_mode(PSU_CHANNEL)
    print(f'    Setpoint : {v_set:.3f} V / {i_set:.3f} A limit')
    print(f'    Output   : {v_out:.4f} V  {i_out:.4f} A  ({mode})')
    print(f'    Status   : ON — will remain on after script exit')
except Exception as exc:
    print(f'    ERROR: {exc}')
    sys.exit(1)

# ── Step 2 — DMM: measure VDD ──────────────────────────────────────────────────
print('\n[2/3] Multimeter VDD measurement (34465A)')
try:
    with DMM34465A(DMM_ADDR) as dmm:
        vdd = dmm.measure_vdc(range_v=DMM_RANGE)
    print(f'    VDD = {vdd:.4f} V')
except Exception as exc:
    print(f'    ERROR: {exc}')
    sys.exit(1)

# ── Step 3 — Chamber setpoint ──────────────────────────────────────────────────
print('\n[3/3] Climate chamber (MK53)')
try:
    with MK53(MK53_ADDR, slave_address=MK53_SLAVE) as chamber:
        chamber.set_temperature(CHAMBER_TEMP)
        actual = chamber.get_temperature()
        setpt  = chamber.get_temperature_setpoint()
    print(f'    Setpoint : {setpt:.1f} °C')
    print(f'    Current  : {actual:.2f} °C')
    print(f'    Status   : running toward {CHAMBER_TEMP:.0f} °C after script exit')
except Exception as exc:
    print(f'    ERROR: {exc}')
    sys.exit(1)

# ── Summary ────────────────────────────────────────────────────────────────────
print('\n' + '=' * 55)
print('  Setup complete')
print(f'  PSU CH{PSU_CHANNEL}  : {v_out:.4f} V  {i_out:.4f} A  (ON)')
print(f'  VDD (DMM) : {vdd:.4f} V')
print(f'  Chamber   : setpoint {CHAMBER_TEMP:.0f} °C  /  actual {actual:.2f} °C')
print('=' * 55)
