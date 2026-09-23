# Lab Equipment Python Drivers

PyVISA-based instrument drivers and automated test scripts for bench lab equipment.

## Instruments supported

| Driver file | Instrument | Interface |
|---|---|---|
| `Python_Drivers/mk53_driver.py` | Binder MK53 — Dynamic Climate Chamber | RS-422 serial (USB adapter) |
| `Python_Drivers/dmm34465a_driver.py` | Keysight 34465A — 6½-digit DMM | USB-TMC / GPIB / LAN |
| `Python_Drivers/hmp4040_driver.py` | R&S HMP4040 — 4-ch DC Power Supply | USB-TMC / GPIB / LAN |
| `Python_Drivers/e36441a_driver.py` | Keysight E36441A — 4-ch DC Power Supply | USB-TMC / GPIB / LAN |
| `Python_Drivers/e4980a_driver.py` | Keysight E4980A — Precision LCR Meter | USB-TMC / GPIB / LAN |

## Project structure

```
Lab_Equipment_Python_Drivers/
├── Python_Drivers/          # Instrument driver classes
│   ├── mk53_driver.py
│   ├── dmm34465a_driver.py
│   ├── hmp4040_driver.py
│   ├── e36441a_driver.py
│   └── e4980a_driver.py
├── scripts/
│   ├── list_visa_resources.py    # Discover VISA addresses of connected instruments
│   ├── test_e36441a.py           # First-time sanity check for E36441A
│   ├── test_dmm34465a.py         # First-time sanity check for 34465A
│   ├── test_hmp4040.py           # First-time sanity check for HMP4040
│   ├── test_mk53.py              # First-time sanity check for MK53
│   ├── test_e4980a.py            # First-time sanity check for E4980A (1 MHz Cp-D)
│   └── thermal_setup.py          # Configure PSU + chamber + take one VDD reading
├── Datasheets/              # Programming guides and user manuals (not committed)
├── tests/
│   └── test_thermal_voltage.py   # Thermal + electrical DUT test (PSU + DMM + chamber)
├── unit_tests/                   # Offline driver tests with simulated instruments
├── conftest.py              # pytest session fixtures (instrument connections)
├── config.py                # Shared test parameters (temperatures, tolerances)
├── requirements.txt         # Python dependencies
└── README.md
```

## Setup

### 1. Install Python 3.12

Download and install Python 3.12 from `python.org`. Python 3.12 is recommended — it has stable support for all packages used here (`pyusb`, `libusb-package`, `pyvisa-py`).

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 3. USB instrument driver — Zadig (Windows only)

USB-TMC instruments (34465A, HMP4040, E36441A, E4980A) require the **WinUSB** driver on Windows. Use [Zadig](https://zadig.akeo.ie) to install it:

1. Plug in the instrument and power it on
2. Open Zadig → `Options` → tick **List All Devices**
3. Find your instrument in the dropdown (e.g. "E36441A", "34465A")
4. Set the driver to **WinUSB** → click **Install Driver** (or **Replace Driver**)

> **Note:** You need to do this once per instrument. If Windows reverts the driver after unplugging and replugging, open Zadig again and click **Replace Driver**.

### 4. RS-422 serial adapter (Binder MK53 only)

The MK53 rear panel uses RS-422 (differential serial). You need a **USB-to-RS-422 adapter** (not RS-232). FTDI-based adapters work reliably on Windows — they appear as a COM port after driver install.

### 5. Find your instrument VISA addresses

Run the discovery script to list all connected instruments and their addresses:

```bash
python scripts/list_visa_resources.py
```

Example output:
```
Found 2 VISA resource(s):

  USB0::10893::52228::CN65510106::0::INSTR
    IDN : Keysight Technologies,E36441A,CN65510106,01.00-01.06-01.04

  USB0::10893::257::MY64039038::0::INSTR
    IDN : Keysight Technologies,34465A,MY64039038,A.03.10
```

Copy the address for each instrument and paste it into `VISA_ADDR` at the top of the corresponding test script.

## Running the sanity-check scripts

Each instrument has a standalone test script. Run them directly with Python:

```bash
python scripts/test_e36441a.py
python scripts/test_dmm34465a.py
python scripts/test_hmp4040.py
python scripts/test_mk53.py                # read-only; add --write / --stability, --port COM5
python scripts/test_e4980a.py
```

Each script exits with code 1 if any step fails. `test_mk53.py` only reads from the chamber unless `--write` or `--stability` is given.

Before running, open the script and update `VISA_ADDR` at the top to match your instrument's address from `list_visa_resources.py`.

## Offline unit tests (no instruments needed)

```bash
pytest unit_tests
```

These check the MK53 Modbus framing, retries and safety limits, the 34465A limit-test bits, the E36441A CV/CC detection and the self-test parsing against simulated instruments.

## Running the automated tests

```bash
# Run all tests from the project root
pytest

# Verbose output with live print statements
pytest -v -s

# Run only the voltage test
pytest tests/test_thermal_voltage.py::TestThermalVoltage::test_dut_voltage_at_22c
```

### What the thermal voltage test does

1. Connects to the Keysight E36441A, Keysight 34465A, and Binder MK53
2. Powers the DUT via the PSU at the configured voltage and current limit
3. Sets the chamber to **22 °C** and waits up to 15 minutes for stability (±0.5 °C for 60 s)
4. Verifies the PSU is in CV mode and delivering the expected voltage
5. Takes **5 DC voltage readings** from the DMM and averages them
6. Asserts the average is within the configured pass window

All parameters are configurable in `config.py`.

### One-shot setup script

`thermal_setup.py` configures all three instruments in a single run and then exits — the PSU and chamber keep their state after the script ends:

```bash
python scripts/thermal_setup.py
```

- Sets PSU CH1 to **12 V / 1 A** limit and enables output
- Takes one VDD measurement with the DMM
- Sets the chamber setpoint to **20 °C**

## Using the drivers standalone

```python
from Python_Drivers.mk53_driver import MK53
from Python_Drivers.dmm34465a_driver import DMM34465A

with MK53('ASRL3::INSTR', slave_address=1) as chamber:
    chamber.set_temperature(22.0)
    chamber.wait_for_stability(22.0, tolerance_c=0.5, stable_seconds=60)
    print(chamber.get_temperature())

with DMM34465A('USB0::10893::257::MY64039038::0::INSTR') as dmm:
    print(dmm.measure_vdc())
```

## Protocol notes

| Instrument | Protocol |
|---|---|
| Binder MK53 | Modbus RTU binary frames over RS-422 — CRC-16 (poly 0xA001), FC 0x03/0x10, IEEE-754 float with word-swap |
| Keysight 34465A | SCPI over USB-TMC / GPIB / LAN |
| R&S HMP4040 | SCPI — channel selected with `INST OUT{n}` before setpoint commands |
| Keysight E36441A | SCPI — inline channel list `(@n)` syntax throughout |
| Keysight E4980A | SCPI — `*TRG` triggers and returns measurement data; `FETC:IMP?` reads last result |
