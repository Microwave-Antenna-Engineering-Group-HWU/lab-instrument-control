"""
Keysight 34465A — 6½-Digit Truevolt Digital Multimeter
PyVISA driver — SCPI over USB-TMC / GPIB / LAN (LXI)

Typical VISA resource strings:
  USB  : USB0::0x2A8D::0x0101::<serial>::INSTR
  GPIB : GPIB0::22::INSTR
  LAN  : TCPIP0::192.168.1.102::inst0::INSTR

Supported measurement functions:
  DC/AC Voltage, DC/AC Current, 2-wire Resistance, 4-wire Resistance,
  Frequency, Period, Temperature (RTD/thermistor/thermocouple),
  Diode, Continuity, Capacitance, DC Voltage Ratio

Reading memory: up to 50 000 readings (without MEM option),
                up to 2 000 000 readings (with MEM option).
"""

import pyvisa


class DMM34465A:
    """Driver for the Keysight 34465A digital multimeter."""

    # Valid voltage ranges (V DC/AC)
    VOLT_RANGES = (0.1, 1, 10, 100, 1000)
    # Valid current ranges (A DC/AC)
    CURR_RANGES = (100e-6, 1e-3, 10e-3, 100e-3, 1, 3, 10)
    # Valid resistance ranges (Ω)
    RES_RANGES = (100, 1e3, 10e3, 100e3, 1e6, 10e6, 100e6, 1e9)

    def __init__(self, resource_name: str, timeout_ms: int = 10000):
        rm = pyvisa.ResourceManager('@py')
        self._instr = rm.open_resource(resource_name)
        self._instr.timeout = timeout_ms
        self._instr.read_termination = '\n'
        self._instr.write_termination = '\n'

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self._instr.close()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def write(self, cmd: str):
        self._instr.write(cmd)

    def query(self, cmd: str) -> str:
        return self._instr.query(cmd).strip()

    def _parse_readings(self, response: str) -> list:
        """Convert comma-separated ASCII float string to list of floats."""
        return [float(x) for x in response.split(',')]

    # ------------------------------------------------------------------
    # IEEE-488 / System
    # ------------------------------------------------------------------

    def identify(self) -> str:
        """Return *IDN? string: 'Keysight Technologies,34465A,<sn>,<fw>'."""
        return self.query('*IDN?')

    def reset(self):
        """Factory reset + clear status registers."""
        self.write('*RST')
        self.write('*CLS')

    def clear_status(self):
        self.write('*CLS')

    def wait_opc(self):
        """Block until all pending operations complete."""
        self.query('*OPC?')

    def self_test(self) -> bool:
        """Return True if self-test passes (+0 = pass, +1 = fail)."""
        return self.query('TEST:ALL?').strip() in ('0', '+0')

    def get_error(self) -> str:
        return self.query('SYST:ERR?')

    def abort(self):
        """Abort any measurement in progress."""
        self.write('ABOR')

    # ------------------------------------------------------------------
    # Terminals / Display
    # ------------------------------------------------------------------

    def get_terminals(self) -> str:
        """Return 'FRON' or 'REAR' depending on front/rear switch position."""
        return self.query('ROUT:TERM?')

    def set_temperature_unit(self, unit: str):
        """Set temperature display/return unit: 'C', 'F', or 'K'."""
        u = unit.upper()
        if u not in ('C', 'F', 'K'):
            raise ValueError("unit must be 'C', 'F', or 'K'")
        self.write(f'UNIT:TEMP {u}')

    def display_on(self):
        self.write('DISP ON')

    def display_off(self):
        """Disable front panel display (speeds up remote operation)."""
        self.write('DISP OFF')

    def display_text(self, text: str):
        """Show up to 40 characters on the front panel display."""
        self.write(f'DISP:TEXT "{text[:40]}"')

    def clear_display_text(self):
        self.write('DISP:TEXT:CLE')

    def get_configuration(self) -> str:
        """Return current configuration string, e.g. '"VOLT +1.00E+01,+3.00E-06"'."""
        return self.query('CONF?')

    # ------------------------------------------------------------------
    # MEASure? — single-shot one-command measurements
    # (Internally does: CONFigure + INIT + *TRG + FETCh?)
    # ------------------------------------------------------------------

    def measure_vdc(self, range_v=None, resolution=None) -> float:
        """Measure DC voltage. Returns volts as float."""
        cmd = 'MEAS:VOLT:DC?'
        if range_v is not None:
            cmd += f' {range_v}'
            if resolution is not None:
                cmd += f', {resolution}'
        return float(self.query(cmd))

    def measure_vac(self, range_v=None) -> float:
        """Measure AC voltage (true RMS). Returns volts."""
        cmd = 'MEAS:VOLT:AC?'
        if range_v is not None:
            cmd += f' {range_v}'
        return float(self.query(cmd))

    def measure_idc(self, range_a=None, resolution=None) -> float:
        """Measure DC current. Returns amps."""
        cmd = 'MEAS:CURR:DC?'
        if range_a is not None:
            cmd += f' {range_a}'
            if resolution is not None:
                cmd += f', {resolution}'
        return float(self.query(cmd))

    def measure_iac(self, range_a=None) -> float:
        """Measure AC current (true RMS). Returns amps."""
        cmd = 'MEAS:CURR:AC?'
        if range_a is not None:
            cmd += f' {range_a}'
        return float(self.query(cmd))

    def measure_resistance(self, range_ohm=None, resolution=None) -> float:
        """Measure 2-wire resistance. Returns ohms."""
        cmd = 'MEAS:RES?'
        if range_ohm is not None:
            cmd += f' {range_ohm}'
            if resolution is not None:
                cmd += f', {resolution}'
        return float(self.query(cmd))

    def measure_resistance_4w(self, range_ohm=None, resolution=None) -> float:
        """Measure 4-wire (Kelvin) resistance. Returns ohms."""
        cmd = 'MEAS:FRES?'
        if range_ohm is not None:
            cmd += f' {range_ohm}'
            if resolution is not None:
                cmd += f', {resolution}'
        return float(self.query(cmd))

    def measure_frequency(self, range_hz=None) -> float:
        """Measure frequency. Returns Hz."""
        cmd = 'MEAS:FREQ?'
        if range_hz is not None:
            cmd += f' {range_hz}'
        return float(self.query(cmd))

    def measure_period(self) -> float:
        """Measure signal period. Returns seconds."""
        return float(self.query('MEAS:PER?'))

    def measure_temperature(self, probe: str = 'FRTD', probe_type=85) -> float:
        """
        Measure temperature. Returns value in the current UNIT:TEMP unit.
        probe      : 'FRTD' (4-wire RTD, default), 'RTD' (2-wire),
                     'FTHER' (4-wire thermistor), 'THER' (2-wire thermistor),
                     'TCOUPLE' (thermocouple — 34465A only)
        probe_type : 85 for PT85 RTD / PT100, 5000 for thermistor,
                     or 'J','K','T','E','N','R' for thermocouple
        """
        return float(self.query(f'MEAS:TEMP? {probe},{probe_type}'))

    def measure_diode(self) -> float:
        """Measure diode forward voltage (1 mA source). Returns volts."""
        return float(self.query('MEAS:DIOD?'))

    def measure_continuity(self) -> float:
        """Continuity test (fixed 1 kΩ range). Returns resistance in ohms."""
        return float(self.query('MEAS:CONT?'))

    def measure_capacitance(self, range_f=None) -> float:
        """Measure capacitance. Returns farads."""
        cmd = 'MEAS:CAP?'
        if range_f is not None:
            cmd += f' {range_f}'
        return float(self.query(cmd))

    def measure_vdc_ratio(self, range_v=None) -> float:
        """
        Measure DC voltage ratio (Input / Sense terminals).
        Returns dimensionless ratio.
        """
        cmd = 'MEAS:VOLT:DC:RAT?'
        if range_v is not None:
            cmd += f' {range_v}'
        return float(self.query(cmd))

    # ------------------------------------------------------------------
    # READ? — single-shot with prior CONFigure (allows parameter changes)
    # ------------------------------------------------------------------

    def configure_vdc(self, range_v='AUTO', resolution=None):
        """Configure for DC voltage without starting. Use read() to acquire."""
        cmd = f'CONF:VOLT:DC {range_v}'
        if resolution is not None:
            cmd += f', {resolution}'
        self.write(cmd)

    def configure_vac(self, range_v='AUTO'):
        self.write(f'CONF:VOLT:AC {range_v}')

    def configure_idc(self, range_a='AUTO', resolution=None):
        cmd = f'CONF:CURR:DC {range_a}'
        if resolution is not None:
            cmd += f', {resolution}'
        self.write(cmd)

    def configure_iac(self, range_a='AUTO'):
        self.write(f'CONF:CURR:AC {range_a}')

    def configure_resistance(self, range_ohm='AUTO', resolution=None):
        cmd = f'CONF:RES {range_ohm}'
        if resolution is not None:
            cmd += f', {resolution}'
        self.write(cmd)

    def configure_resistance_4w(self, range_ohm='AUTO', resolution=None):
        cmd = f'CONF:FRES {range_ohm}'
        if resolution is not None:
            cmd += f', {resolution}'
        self.write(cmd)

    def configure_frequency(self, range_hz='AUTO'):
        self.write(f'CONF:FREQ {range_hz}')

    def configure_temperature(self, probe: str = 'FRTD', probe_type=85):
        self.write(f'CONF:TEMP {probe},{probe_type}')

    def configure_diode(self):
        self.write('CONF:DIOD')

    def configure_continuity(self):
        self.write('CONF:CONT')

    def configure_capacitance(self, range_f='AUTO'):
        self.write(f'CONF:CAP {range_f}')

    def read(self) -> float:
        """Trigger and fetch a single reading after CONFigure. Returns float."""
        return float(self.query('READ?'))

    # ------------------------------------------------------------------
    # Trigger / Sample  (multi-sample acquisition)
    # ------------------------------------------------------------------

    def set_trigger_source(self, source: str):
        """
        Set trigger source: 'IMM' (immediate, default), 'BUS' (software *TRG),
        'EXT' (rear panel Ext Trig input).
        """
        self.write(f'TRIG:SOUR {source.upper()}')

    def set_sample_count(self, count: int):
        """Set number of samples per trigger event (1 – 50000)."""
        self.write(f'SAMP:COUN {count}')

    def set_trigger_count(self, count: int):
        """Set number of triggers to accept before returning to idle."""
        self.write(f'TRIG:COUN {count}')

    def set_trigger_delay(self, delay_s: float):
        """Set trigger delay in seconds (0 = automatic)."""
        self.write(f'TRIG:DEL {delay_s}')

    def initiate(self):
        """Arm the trigger system (instrument waits for trigger)."""
        self.write('INIT')

    def fetch(self) -> list:
        """
        Transfer all measurements from reading memory. Non-destructive.
        Returns list of floats.
        """
        return self._parse_readings(self.query('FETC?'))

    def read_multi(self, count: int) -> list:
        """
        Convenience: set the sample count, arm, software-trigger and fetch
        all readings. Returns a list of floats.
        Uses the BUS trigger internally, then restores immediate triggering
        and a sample count of 1, so later read() calls still work.
        """
        self.write(f'SAMP:COUN {count}')
        self.write('TRIG:SOUR BUS')
        try:
            self.write('INIT')
            self.write('*TRG')
            self.query('*OPC?')          # wait for all samples to be taken
            return self.fetch()
        finally:
            self.write('TRIG:SOUR IMM')
            self.write('SAMP:COUN 1')

    # ------------------------------------------------------------------
    # Reading memory management
    # ------------------------------------------------------------------

    def get_reading_count(self) -> int:
        """Return number of readings currently in reading memory."""
        return int(self.query('DATA:POIN?'))

    def get_last_reading(self) -> float:
        """Return the most recent reading taken (even mid-acquisition)."""
        return float(self.query('DATA:LAST?').split()[0])   # strip units suffix

    def remove_readings(self, count: int) -> list:
        """
        Read and erase 'count' oldest readings from memory.
        Use during long acquisitions to prevent memory overflow.
        Returns list of floats.
        """
        return self._parse_readings(self.query(f'DATA:REM? {count}'))

    def r_query(self, count: int = None) -> list:
        """
        R? <n> — read AND erase readings from memory (non-blocking,
        returns whatever is available at call time).
        Returns list of floats.
        """
        cmd = f'R? {count}' if count is not None else 'R?'
        return self._parse_readings(self.query(cmd))

    # ------------------------------------------------------------------
    # Limit testing  (pass/fail on Questionable Data register)
    # ------------------------------------------------------------------

    def configure_limits(self, low: float, high: float):
        """
        Set measurement limits for pass/fail detection.
        Check status with check_limits() after measurement.
        """
        self.write(f'CALC:LIM:LOW {low}')
        self.write(f'CALC:LIM:UPP {high}')
        self.write('CALC:LIM:STAT ON')

    def check_limits(self) -> dict:
        """
        Return {'pass': bool, 'low': bool, 'high': bool}.
        Reads the Questionable Data event register (STAT:QUES?):
        bit 11 = lower limit failed, bit 12 = upper limit failed.
        Reading the event register clears it.
        """
        val = int(self.query('STAT:QUES?'))
        lower_fail = bool(val & (1 << 11))
        upper_fail = bool(val & (1 << 12))
        return {
            'pass': not (lower_fail or upper_fail),
            'low': lower_fail,
            'high': upper_fail,
        }

    def disable_limits(self):
        self.write('CALC:LIM:STAT OFF')

    # ------------------------------------------------------------------
    # NPLC (integration time)  — via SENSe subsystem
    # ------------------------------------------------------------------

    def set_nplc_vdc(self, nplc: float):
        """
        Set integration time for DC voltage in Power Line Cycles.
        0.001 (fastest) → 100 (slowest/highest accuracy).
        Default = 10.
        """
        self.write(f'SENS:VOLT:DC:NPLC {nplc}')

    def set_nplc_idc(self, nplc: float):
        self.write(f'SENS:CURR:DC:NPLC {nplc}')

    def set_nplc_resistance(self, nplc: float):
        self.write(f'SENS:RES:NPLC {nplc}')

    # ------------------------------------------------------------------
    # Auto-zero
    # ------------------------------------------------------------------

    def set_autozero(self, on: bool):
        """Enable or disable auto-zero (improves accuracy at cost of speed)."""
        state = 'ON' if on else 'OFF'
        self.write(f'SENS:VOLT:DC:ZERO:AUTO {state}')


# ---------------------------------------------------------------------------
# Quick usage example
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    VISA_ADDR = 'USB0::0x2A8D::0x0101::MY12345678::INSTR'  # replace

    with DMM34465A(VISA_ADDR) as dmm:
        print('Connected:', dmm.identify())
        dmm.reset()

        # One-shot DC voltage measurement
        v = dmm.measure_vdc()
        print(f'VDC: {v:.6f} V')

        # One-shot 4-wire resistance
        r = dmm.measure_resistance_4w(range_ohm=100)
        print(f'R4W: {r:.4f} Ω')

        # Multi-sample acquisition: 10 DC voltage readings
        dmm.configure_vdc(range_v=10, resolution=0.001)
        readings = dmm.read_multi(count=10)
        print(f'10 readings: {readings}')
        print(f'Mean: {sum(readings)/len(readings):.6f} V')

        # Temperature (4-wire RTD)
        dmm.set_temperature_unit('C')
        t = dmm.measure_temperature(probe='FRTD', probe_type=85)
        print(f'Temp: {t:.2f} °C')

        # Limit test
        dmm.configure_vdc()
        dmm.configure_limits(low=3.2, high=3.4)
        dmm.read()
        result = dmm.check_limits()
        print(f'Limit test: {result}')
        dmm.disable_limits()
