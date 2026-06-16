# Lab Equipment Python Drivers

PyVISA-based instrument drivers and automated test scripts for bench lab equipment.

## Instruments supported

| Driver file | Instrument | Interface |
|---|---|---|
| `Python_Drivers/mk53_driver.py` | Binder MK53 — Dynamic Climate Chamber | RS-422 serial (USB adapter) |
| `Python_Drivers/dmm34465a_driver.py` | Keysight 34465A — 6½-digit DMM | USB-TMC / GPIB / LAN |
| `Python_Drivers/hmp4040_driver.py` | R&S HMP4040 — 4-ch DC Power Supply | USB-TMC / GPIB / LAN |
| `Python_Drivers/e36441a_driver.py` | Keysight E36441A — 4-ch DC Power Supply | USB-TMC / GPIB / LAN |

## Project structure

```
Lab_Equipment_Python_Drivers/
├── Python_Drivers/          # Instrument driver classes
│   ├── mk53_driver.py
│   ├── dmm34465a_driver.py
│   ├── hmp4040_driver.py
│   └── e36441a_driver.py
├── Datasheets/              # Programming guides and user manuals (not committed)
├── tests/
│   └── test_thermal_voltage.py   # Thermal + electrical DUT test
├── conftest.py              # pytest session fixtures (instrument connections)
├── config.py                # VISA addresses and test parameters — edit this
├── pytest.ini               # pytest configuration
├── requirements.txt         # Python dependencies
└── README.md
```

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. USB instrument driver (Keysight 34465A and similar USB-TMC devices)

On Windows, USB-TMC instruments need the **WinUSB** driver installed via [Zadig](https://zadig.akeo.ie):

1. Plug in the instrument
2. Open Zadig → Options → List All Devices
3. Select your instrument → Install Driver → **WinUSB**

### 3. RS-422 serial adapter (Binder MK53)

The MK53 rear panel uses RS-422 (differential serial). You need a **USB-to-RS-422 adapter** (not RS-232). FTDI-based adapters work reliably on Windows — they appear as a COM port after driver install.

### 4. Edit `config.py`

Update the VISA resource strings to match your hardware:

```python
MK53_RESOURCE  = 'ASRL3::INSTR'       # change COM number
DMM_RESOURCE   = 'USB0::0x2A8D::...'  # replace serial number
```

Discover available resources:

```python
import pyvisa
print(pyvisa.ResourceManager().list_resources())
```

## Running the tests

```bash
# Run all tests from the project root
pytest

# Verbose output with live print statements
pytest -v -s

# Run only the voltage test
pytest tests/test_thermal_voltage.py::TestThermalVoltage::test_dut_voltage_at_22c
```

### What the thermal voltage test does

1. Connects to the Binder MK53 and Keysight 34465A
2. Sets the chamber to **22 °C** and waits up to 15 minutes for stability (±0.5 °C for 60 s)
3. Takes **5 DC voltage readings** from the DMM and averages them
4. Asserts the average is within **3.0 ± 0.5 V**

All parameters are configurable in `config.py`.

## Using the drivers standalone

```python
from Python_Drivers.mk53_driver import MK53
from Python_Drivers.dmm34465a_driver import DMM34465A

with MK53('ASRL3::INSTR', slave_address=1) as chamber:
    chamber.set_temperature(22.0)
    chamber.wait_for_stability(22.0, tolerance_c=0.5, stable_seconds=60)
    print(chamber.get_temperature())

with DMM34465A('USB0::0x2A8D::0x0101::MY12345678::INSTR') as dmm:
    print(dmm.measure_vdc())
```

## Protocol notes

| Instrument | Protocol |
|---|---|
| Binder MK53 | Modbus RTU binary frames over RS-422 — CRC-16 (poly 0xA001), FC 0x03/0x10, IEEE-754 float with word-swap |
| Keysight 34465A | SCPI over USB-TMC / GPIB / LAN |
| R&S HMP4040 | SCPI — channel selected with `INST OUT{n}` before setpoint commands |
| Keysight E36441A | SCPI — inline channel list `(@n)` syntax throughout |
