# ── Instrument VISA addresses ──────────────────────────────────────────────
# Addresses confirmed from individual sanity-check scripts.
#
# Discover connected instruments:
#   python -c "import pyvisa; print(pyvisa.ResourceManager('@py').list_resources())"

MK53_RESOURCE   = 'ASRL3::INSTR'
MK53_SLAVE_ADDR = 1                 # DIP switch on MK53 rear panel

DMM_RESOURCE    = 'USB0::10893::257::MY64039038::0::INSTR'

PSU_RESOURCE    = 'USB0::10893::52228::CN65510106::0::INSTR'

# ── MK53 safety limits ─────────────────────────────────────────────────────
MK53_MIN_TEMP_C = -40.0
MK53_MAX_TEMP_C = 180.0

# ── Thermal soak parameters ────────────────────────────────────────────────
TARGET_TEMP_C      = 22.0   # °C — soak temperature
TEMP_TOLERANCE_C   = 0.5    # ±°C — stability band
TEMP_STABLE_SEC    = 60     # seconds chamber must stay in band before measuring
TEMP_TIMEOUT_SEC   = 900    # seconds before giving up (15 min)

# ── PSU / DUT supply settings ──────────────────────────────────────────────
PSU_CHANNEL        = 1      # E36441A channel used to power the DUT
PSU_VOLTAGE_V      = 5.0    # V — DUT supply voltage
PSU_CURRENT_LIM_A  = 0.5    # A — current limit (set above DUT max draw)

# ── Electrical measurement parameters ─────────────────────────────────────
EXPECTED_VOLTAGE_V  = 3.3   # V — nominal DUT output voltage to measure
VOLTAGE_TOLERANCE_V = 0.1   # ±V — pass/fail window
DMM_RANGE_V         = 10    # V — DMM input range (set above max expected)
DMM_NPLC            = 10    # integration time (10 PLC ≈ 167 ms/reading)
DMM_SAMPLES         = 5     # number of readings to average per temperature point
