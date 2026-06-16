# ── Instrument VISA addresses ──────────────────────────────────────────────
# Update these to match your actual hardware before running tests.
#
# Discover connected instruments:
#   python -c "import pyvisa; print(pyvisa.ResourceManager().list_resources())"
#
# MK53  → USB-to-RS422 adapter  → appears as ASRL{n}::INSTR (COMn on Windows)
# 34465A → USB-TMC              → appears as USB0::0x2A8D::...::INSTR

MK53_RESOURCE   = 'ASRL3::INSTR'                            # change COMn as needed
MK53_SLAVE_ADDR = 1                                          # DIP switch on rear panel

DMM_RESOURCE    = 'USB0::0x2A8D::0x0101::MY12345678::INSTR' # replace serial number

# ── MK53 safety limits ─────────────────────────────────────────────────────
MK53_MIN_TEMP_C = -40.0
MK53_MAX_TEMP_C = 180.0

# ── Thermal test parameters ────────────────────────────────────────────────
TARGET_TEMP_C      = 22.0   # °C — soak temperature
TEMP_TOLERANCE_C   = 0.5    # ±°C — stability band
TEMP_STABLE_SEC    = 60     # seconds chamber must stay in band
TEMP_TIMEOUT_SEC   = 900    # seconds before giving up (15 min)

# ── Electrical measurement parameters ─────────────────────────────────────
EXPECTED_VOLTAGE_V  = 3.0   # V — nominal DUT output voltage
VOLTAGE_TOLERANCE_V = 0.5   # ±V — pass/fail window  →  [2.5 V, 3.5 V]
DMM_RANGE_V         = 10    # V — DMM input range (set above max expected)
DMM_NPLC            = 10    # integration time (10 PLC = high accuracy, ~167 ms/reading)
DMM_SAMPLES         = 5     # number of readings to average per measurement point
