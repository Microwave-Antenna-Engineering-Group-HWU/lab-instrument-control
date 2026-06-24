"""
Thermal + electrical characterisation test.

Test sequence
─────────────
1. PSU powers the DUT at PSU_VOLTAGE_V on PSU_CHANNEL.
2. MK53 chamber soaks at TARGET_TEMP_C until stable
   (handled by the session fixture `chamber_at_target` in conftest.py).
3. Chamber temperature is confirmed to be within tolerance.
4. PSU output is verified: voltage and current are within expected range.
5. DUT output voltage is measured with the Keysight 34465A.
   The average of DMM_SAMPLES readings must lie within
   EXPECTED_VOLTAGE_V ± VOLTAGE_TOLERANCE_V.

Configure all parameters in config.py before running.

Run with:
    pytest                         # from project root
    pytest -v -s                   # verbose with live print output
    pytest tests/test_thermal_voltage.py -v -s
"""

import config


class TestThermalVoltage:
    """DUT output voltage verified at a controlled temperature with PSU powering the DUT."""

    def test_chamber_in_band(self, chamber_at_target):
        """
        Pre-check: confirm the chamber is still within tolerance before
        taking electrical measurements.
        """
        actual = chamber_at_target.get_temperature()
        lo = config.TARGET_TEMP_C - config.TEMP_TOLERANCE_C
        hi = config.TARGET_TEMP_C + config.TEMP_TOLERANCE_C

        print(
            f'\n  Chamber temperature : {actual:.2f} °C'
            f'\n  Target window       : [{lo:.1f}, {hi:.1f}] °C'
        )

        assert lo <= actual <= hi, (
            f'Chamber out of band: {actual:.2f}°C '
            f'(expected {config.TARGET_TEMP_C}±{config.TEMP_TOLERANCE_C}°C)'
        )

    def test_psu_output(self, psu):
        """
        Verify the PSU is delivering the expected supply voltage to the DUT.
        Measured output must be within 2% of the setpoint.
        """
        ch = config.PSU_CHANNEL
        v_meas = psu.measure_voltage(ch)
        i_meas = psu.measure_current(ch)
        mode   = psu.get_regulation_mode(ch)

        tolerance = config.PSU_VOLTAGE_V * 0.02   # 2 % of setpoint

        print(
            f'\n  PSU CH{ch}'
            f'\n  Setpoint  : {config.PSU_VOLTAGE_V:.3f} V / {config.PSU_CURRENT_LIM_A:.3f} A limit'
            f'\n  Measured  : {v_meas:.4f} V  {i_meas:.4f} A'
            f'\n  Mode      : {mode}'
        )

        assert mode == 'CV', (
            f'PSU CH{ch} not in CV mode (got {mode}) — '
            f'check DUT load or current limit setting'
        )
        assert abs(v_meas - config.PSU_VOLTAGE_V) <= tolerance, (
            f'PSU output {v_meas:.4f} V deviates more than 2% from '
            f'setpoint {config.PSU_VOLTAGE_V:.3f} V'
        )

    def test_dut_voltage_at_target_temp(self, chamber_at_target, psu, dmm):
        """
        Main test: DUT output voltage must be within tolerance at TARGET_TEMP_C.

        Takes DMM_SAMPLES readings and checks the average.
        Individual readings are printed for traceability.
        """
        temp  = chamber_at_target.get_temperature()
        v_psu = psu.measure_voltage(config.PSU_CHANNEL)
        i_psu = psu.measure_current(config.PSU_CHANNEL)

        readings = []
        for _ in range(config.DMM_SAMPLES):
            v = dmm.measure_vdc(range_v=config.DMM_RANGE_V)
            readings.append(v)

        average = sum(readings) / len(readings)
        lo = config.EXPECTED_VOLTAGE_V - config.VOLTAGE_TOLERANCE_V
        hi = config.EXPECTED_VOLTAGE_V + config.VOLTAGE_TOLERANCE_V

        print(
            f'\n  Temperature  : {temp:.2f} °C'
            f'\n  PSU supply   : {v_psu:.4f} V  {i_psu:.4f} A'
            f'\n  DUT readings : {[f"{r:.4f}" for r in readings]} V'
            f'\n  Average      : {average:.4f} V'
            f'\n  Pass window  : [{lo:.3f}, {hi:.3f}] V'
            f'\n  Result       : {"PASS" if lo <= average <= hi else "FAIL"}'
        )

        assert lo <= average <= hi, (
            f'DUT voltage out of range: {average:.4f} V '
            f'(expected {config.EXPECTED_VOLTAGE_V}±{config.VOLTAGE_TOLERANCE_V} V '
            f'at {temp:.2f}°C with PSU {v_psu:.3f} V supply)'
        )
