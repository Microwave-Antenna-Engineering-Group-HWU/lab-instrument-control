"""
Thermal + electrical characterisation test.

Test sequence
─────────────
1. Binder MK53 chamber is soaked at TARGET_TEMP_C until stable
   (handled by the session fixture `chamber_at_target` in conftest.py).
2. DUT DC output voltage is measured with the Keysight 34465A.
3. The average of DMM_SAMPLES readings must lie within
   EXPECTED_VOLTAGE_V ± VOLTAGE_TOLERANCE_V.

Configure all parameters in config.py before running.

Run with:
    pytest                       # from project root
    pytest -v -s                 # verbose with live print output
    pytest tests/test_thermal_voltage.py::TestThermalVoltage::test_dut_voltage
"""

import pytest
import config


class TestThermalVoltage:
    """DUT output voltage verified at a controlled temperature."""

    def test_chamber_in_band(self, chamber_at_target):
        """
        Pre-check: confirm the chamber is still within tolerance before
        taking electrical measurements.
        """
        actual = chamber_at_target.get_temperature()
        lo = config.TARGET_TEMP_C - config.TEMP_TOLERANCE_C
        hi = config.TARGET_TEMP_C + config.TEMP_TOLERANCE_C

        print(f'\n  Chamber temperature: {actual:.2f}°C  (target window [{lo}, {hi}]°C)')

        assert lo <= actual <= hi, (
            f'Chamber out of band: {actual:.2f}°C '
            f'(expected {config.TARGET_TEMP_C}±{config.TEMP_TOLERANCE_C}°C)'
        )

    def test_dut_voltage_at_22c(self, chamber_at_target, dmm):
        """
        Main test: DUT output voltage must be within tolerance at TARGET_TEMP_C.

        Takes DMM_SAMPLES readings and checks the average.
        Individual readings are also printed for traceability.
        """
        temp = chamber_at_target.get_temperature()

        # Take multiple readings and average for robustness
        readings = []
        for _ in range(config.DMM_SAMPLES):
            v = dmm.measure_vdc(range_v=config.DMM_RANGE_V)
            readings.append(v)

        average = sum(readings) / len(readings)
        lo = config.EXPECTED_VOLTAGE_V - config.VOLTAGE_TOLERANCE_V
        hi = config.EXPECTED_VOLTAGE_V + config.VOLTAGE_TOLERANCE_V

        print(
            f'\n  Temperature : {temp:.2f} °C'
            f'\n  Readings    : {[f"{r:.4f}" for r in readings]} V'
            f'\n  Average     : {average:.4f} V'
            f'\n  Pass window : [{lo:.2f}, {hi:.2f}] V'
            f'\n  Result      : {"PASS" if lo <= average <= hi else "FAIL"}'
        )

        assert lo <= average <= hi, (
            f'Voltage out of range: {average:.4f} V '
            f'(expected {config.EXPECTED_VOLTAGE_V}±{config.VOLTAGE_TOLERANCE_V} V '
            f'at {temp:.2f}°C)'
        )
