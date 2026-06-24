"""
Keysight E4980A — Precision LCR Meter
PyVISA driver — SCPI over GPIB / USB-TMC / LAN (LXI)

Also compatible with the E4980AL (lower upper-frequency variant).

Typical VISA resource strings:
  USB  : USB0::0x2A8D::0x0403::<serial>::INSTR
  GPIB : GPIB0::17::INSTR
  LAN  : TCPIP0::192.168.1.101::inst0::INSTR

Measurement functions (FUNC:IMP:TYPE):
  CPD, CPQ, CPG, CPRP, CSD, CSQ, CSRS,
  LPD, LPQ, LPG, LPRP, LPRD, LSD, LSQ, LSRS, LSRD,
  RX, ZTD, ZTR, GB, YTD, YTR, VDID (option 001/030/050/100/200)

Frequency range  : 20 Hz – 2 MHz
AC signal level  : 0 – 2 V rms  (voltage source)  or  0 – 100 mA (current source)
DC bias          : 0 / 1.5 / 2 V (std);  ±40 V / ±100 mA (option 001)
"""

import pyvisa


class E4980A:
    """Driver for the Keysight E4980A Precision LCR Meter."""

    # All valid impedance function types
    IMP_TYPES = (
        'CPD', 'CPQ', 'CPG', 'CPRP',
        'CSD', 'CSQ', 'CSRS',
        'LPD', 'LPQ', 'LPG', 'LPRP', 'LPRD',
        'LSD', 'LSQ', 'LSRS', 'LSRD',
        'RX', 'ZTD', 'ZTR', 'GB', 'YTD', 'YTR', 'VDID',
    )
    # Impedance measurement ranges (Ω)
    IMP_RANGES = (100e-3, 1, 10, 100, 300, 1e3, 3e3, 10e3, 30e3, 100e3)
    # DC resistance measurement ranges (Ω)
    DCR_RANGES = (10, 100, 1e3, 10e3, 100e3)

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

    def _parse_pair(self, response: str) -> tuple:
        """Parse 'primary,secondary[,status]' into (float, float)."""
        parts = response.split(',')
        return float(parts[0]), float(parts[1])

    # ------------------------------------------------------------------
    # IEEE-488 / System
    # ------------------------------------------------------------------

    def identify(self) -> str:
        """Return *IDN? string: 'Keysight Technologies,E4980A,<sn>,<fw>'."""
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
        """Return True if self-test passes (*TST? always returns 0 on this model)."""
        return self.query('*TST?').strip() in ('0', '+0')

    def get_options(self) -> str:
        """Return installed options string from *OPT?."""
        return self.query('*OPT?')

    def get_error(self) -> str:
        """Read and return one error message from the error queue."""
        return self.query('SYST:ERR?')

    def abort(self):
        """Reset trigger system to idle state."""
        self.write('ABOR')

    def system_preset(self):
        """Reset settings and correction data (deeper than *RST)."""
        self.write('SYST:PRES')

    def lock_front_panel(self, lock: bool):
        """Enable or disable the front-panel key lock."""
        self.write(f'SYST:KLOC {"ON" if lock else "OFF"}')

    def beep(self):
        """Emit one beep regardless of the beeper-enable setting."""
        self.write('SYST:BEEP')

    def save_state(self, slot: int):
        """Save instrument state to slot 0–9 (internal) or 10–19 (USB)."""
        self.write(f'MMEM:STOR:STAT {slot}')

    def recall_state(self, slot: int):
        """Recall previously saved state from slot 0–9 (internal) or 10–19 (USB)."""
        self.write(f'MMEM:LOAD:STAT {slot}')

    def delete_state(self, slot: int):
        """Delete a saved state from slot 0–9 (internal) or 10–19 (USB)."""
        self.write(f'MMEM:DEL {slot}')

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def display_on(self):
        """Enable front-panel display updates."""
        self.write('DISP:ENAB ON')

    def display_off(self):
        """Disable front-panel display updates (increases throughput in remote mode)."""
        self.write('DISP:ENAB OFF')

    def display_text(self, text: str):
        """Write up to 30 ASCII characters in the user comment field."""
        self.write(f'DISP:LINE "{text[:30]}"')

    def display_page(self, page: str):
        """
        Select the front-panel display page.
        page: 'MEASurement', 'BNUMber', 'BCOunt', 'LIST', 'MSETup',
              'CSETup', 'LTABle', 'LSETup', 'CATAlog', 'SYSTem',
              'SELF', 'MLARge', 'SCONfig', 'SERVice'
        """
        self.write(f'DISP:PAGE {page.upper()}')

    def clear_display_errors(self):
        """Clear error and caution messages from the display."""
        self.write('DISP:CCL')

    # ------------------------------------------------------------------
    # Measurement function
    # ------------------------------------------------------------------

    def set_function(self, func: str):
        """
        Select impedance measurement function.
        func: CPD, CPQ, CPG, CPRP, CSD, CSQ, CSRS,
              LPD, LPQ, LPG, LPRP, LPRD, LSD, LSQ, LSRS, LSRD,
              RX, ZTD, ZTR, GB, YTD, YTR, VDID
        """
        self.write(f'FUNC:IMP:TYPE {func.upper()}')

    def get_function(self) -> str:
        return self.query('FUNC:IMP:TYPE?')

    def set_impedance_range(self, ohms: float):
        """
        Set impedance range in ohms and disable auto-range.
        Valid values: 100m, 1, 10, 100, 300, 1k, 3k, 10k, 30k, 100k
        """
        self.write(f'FUNC:IMP:RANG {ohms}')

    def set_impedance_range_auto(self, on: bool = True):
        """Enable or disable impedance auto-range."""
        self.write(f'FUNC:IMP:RANG:AUTO {"ON" if on else "OFF"}')

    def get_impedance_range(self) -> float:
        return float(self.query('FUNC:IMP:RANG?'))

    def set_dcr_range(self, ohms: float):
        """
        Set DC resistance range in ohms and disable DCR auto-range.
        Valid values: 10, 100, 1k, 10k, 100k
        """
        self.write(f'FUNC:DCR:RANG {ohms}')

    def set_dcr_range_auto(self, on: bool = True):
        """Enable or disable DC resistance auto-range."""
        self.write(f'FUNC:DCR:RANG:AUTO {"ON" if on else "OFF"}')

    def set_deviation_mode(self, param: int, mode: str):
        """
        Set deviation display mode for primary (1) or secondary (2) parameter.
        mode: 'ABSolute', 'PERCent', or 'OFF'
        """
        self.write(f'FUNC:DEV{param}:MODE {mode.upper()}')

    def set_deviation_reference(self, param: int, value: float):
        """Set the numeric reference for deviation measurement of param 1 or 2."""
        self.write(f'FUNC:DEV{param}:REF {value}')

    def fill_deviation_reference(self):
        """Trigger one measurement and store the result as the deviation reference."""
        self.write('FUNC:DEV1:REF:FILL')

    # ------------------------------------------------------------------
    # Signal source  (frequency, AC voltage / current level)
    # ------------------------------------------------------------------

    def set_frequency(self, hz: float):
        """Set AC test frequency in Hz (20 Hz to 2 MHz)."""
        self.write(f'FREQ {hz}')

    def get_frequency(self) -> float:
        return float(self.query('FREQ?'))

    def set_voltage(self, volts: float):
        """Set AC test signal amplitude in V rms (0 to 2 V). Switches to voltage source."""
        self.write(f'VOLT {volts}')

    def get_voltage(self) -> float:
        return float(self.query('VOLT?'))

    def set_current(self, amps: float):
        """Set AC test signal amplitude in A rms (0 to 100 mA). Switches to current source."""
        self.write(f'CURR {amps}')

    def get_current(self) -> float:
        return float(self.query('CURR?'))

    def set_alc(self, on: bool):
        """Enable or disable Automatic Level Control (ALC)."""
        self.write(f'AMPL:ALC {"ON" if on else "OFF"}')

    # ------------------------------------------------------------------
    # Aperture / integration time
    # ------------------------------------------------------------------

    def set_aperture(self, time: str, averages: int = 1):
        """
        Set integration time and averaging count.
        time    : 'SHORt', 'MEDium', or 'LONG'
        averages: 1 – 256
        """
        self.write(f'APER {time.upper()},{averages}')

    def get_aperture(self) -> str:
        """Return aperture setting as 'time,averages' string."""
        return self.query('APER?')

    # ------------------------------------------------------------------
    # Trigger
    # ------------------------------------------------------------------

    def set_trigger_source(self, source: str):
        """
        Set trigger source.
        source: 'INTernal' (auto, default), 'HOLD' (front-panel manual),
                'EXTernal' (rear BNC), 'BUS' (GPIB / LAN / USB *TRG)
        """
        self.write(f'TRIG:SOUR {source.upper()}')

    def get_trigger_source(self) -> str:
        return self.query('TRIG:SOUR?')

    def set_trigger_delay(self, seconds: float):
        """Set trigger delay in seconds (0 to 999 s, 100 µs resolution)."""
        self.write(f'TRIG:TDEL {seconds}')

    def set_step_delay(self, seconds: float):
        """Set step delay between list sweep points in seconds (0 to 999 s)."""
        self.write(f'TRIG:DEL {seconds}')

    def initiate(self):
        """Arm trigger system: move from Idle to Wait-for-Trigger once."""
        self.write('INIT')

    def set_initiate_continuous(self, on: bool):
        """When ON, trigger system re-arms automatically after each measurement."""
        self.write(f'INIT:CONT {"ON" if on else "OFF"}')

    # ------------------------------------------------------------------
    # Measurement fetch
    # ------------------------------------------------------------------

    def measure(self) -> tuple:
        """
        Perform one BUS-triggered measurement.
        Sets trigger source to BUS, arms, sends *TRG.
        The instrument responds immediately with the measurement result.
        Returns (primary, secondary) as floats.

        NOTE: *TRG on the E4980A outputs data to the output buffer rather than
        acting as a pure write command; query() reads that response to prevent
        a bus error on the next command.
        """
        self.write('TRIG:SOUR BUS')
        self.write('INIT')
        raw = self.query('*TRG')
        return self._parse_pair(raw)

    def fetch(self) -> tuple:
        """
        Fetch the most recent measurement without triggering.
        Returns (primary, secondary) as floats.
        Use after INIT:CONT ON or after a manual trigger.
        """
        return self._parse_pair(self.query('FETC:IMP?'))

    def fetch_corrected(self) -> tuple:
        """
        Fetch most recent result in R-X (resistance–reactance) format.
        Returns (R in Ω, X in Ω) regardless of the selected function.
        """
        return self._parse_pair(self.query('FETC:IMP:CORR?'))

    def fetch_source_monitor(self) -> dict:
        """
        Return AC source monitor readings.
        Returns {'VAC': float (V rms), 'IAC': float (A rms)}.
        """
        return {
            'VAC': float(self.query('FETC:SMON:VAC?')),
            'IAC': float(self.query('FETC:SMON:IAC?')),
        }

    # ------------------------------------------------------------------
    # DC bias  (standard; option 001 extends voltage/current range)
    # ------------------------------------------------------------------

    def set_bias_voltage(self, volts: float):
        """
        Set DC bias voltage.
        Standard: 0, 1.5, or 2 V.  Option 001: –40 V to +40 V.
        """
        self.write(f'BIAS:VOLT {volts}')

    def get_bias_voltage(self) -> float:
        return float(self.query('BIAS:VOLT?'))

    def set_bias_current(self, amps: float):
        """Set DC bias current (option 001 required;  –100 mA to +100 mA)."""
        self.write(f'BIAS:CURR {amps}')

    def get_bias_current(self) -> float:
        return float(self.query('BIAS:CURR?'))

    def set_bias_state(self, on: bool):
        """Enable or disable DC bias output."""
        self.write(f'BIAS:STAT {"ON" if on else "OFF"}')

    def get_bias_state(self) -> bool:
        return self.query('BIAS:STAT?').strip() in ('1', 'ON')

    def set_bias_range_auto(self, on: bool = True):
        """Enable or disable auto-range for the DC bias source."""
        self.write(f'BIAS:RANG:AUTO {"ON" if on else "OFF"}')

    # ------------------------------------------------------------------
    # Open / Short / Load correction
    # ------------------------------------------------------------------

    def set_correction_cable_length(self, metres: int):
        """Set cable length compensation: 0, 1, 2, or 4 m."""
        self.write(f'CORR:LENG {metres}')

    def execute_open_correction(self):
        """Perform OPEN correction (removes stray admittance)."""
        self.write('CORR:OPEN')

    def set_open_correction(self, on: bool):
        """Apply or bypass the stored OPEN correction data."""
        self.write(f'CORR:OPEN:STAT {"ON" if on else "OFF"}')

    def execute_short_correction(self):
        """Perform SHORT correction (removes residual impedance)."""
        self.write('CORR:SHOR')

    def set_short_correction(self, on: bool):
        """Apply or bypass the stored SHORT correction data."""
        self.write(f'CORR:SHOR:STAT {"ON" if on else "OFF"}')

    def set_load_correction(self, on: bool):
        """Apply or bypass LOAD correction."""
        self.write(f'CORR:LOAD:STAT {"ON" if on else "OFF"}')

    def set_correction_method(self, method: str):
        """
        Select correction data mode.
        method: 'SINGle' (one set for all frequencies) or 'MULTiple' (per-frequency)
        """
        self.write(f'CORR:METH {method.upper()}')

    def set_spot_frequency(self, point: int, hz: float):
        """Set the test frequency for correction spot point 1–201 (MULTI mode)."""
        self.write(f'CORR:SPOT{point}:FREQ {hz}')

    def set_spot_state(self, point: int, on: bool):
        """Enable or disable a MULTI-mode correction spot point."""
        self.write(f'CORR:SPOT{point}:STAT {"ON" if on else "OFF"}')

    def execute_spot_open(self, point: int):
        """Execute OPEN correction at spot point 1–201."""
        self.write(f'CORR:SPOT{point}:OPEN')

    def execute_spot_short(self, point: int):
        """Execute SHORT correction at spot point 1–201."""
        self.write(f'CORR:SPOT{point}:SHOR')

    def execute_spot_load(self, point: int):
        """Execute LOAD correction at spot point 1–201."""
        self.write(f'CORR:SPOT{point}:LOAD')

    # ------------------------------------------------------------------
    # Comparator  (pass/fail bin sorting)
    # ------------------------------------------------------------------

    def set_comparator_state(self, on: bool):
        """Enable or disable the comparator (bin sorting)."""
        self.write(f'COMP {"ON" if on else "OFF"}')

    def set_comparator_mode(self, mode: str):
        """
        Set comparator limit mode (changing mode clears all limits).
        mode: 'ATOLerance' (absolute), 'PTOLerance' (percent), 'SEQuence' (bins 1–9)
        """
        self.write(f'COMP:MODE {mode.upper()}')

    def set_tolerance_nominal(self, value: float):
        """Set the nominal reference value for tolerance-mode bin limits."""
        self.write(f'COMP:TOL:NOM {value}')

    def set_tolerance_bin(self, bin_num: int, low: float, high: float):
        """Set absolute or percent tolerance limits for bin 1–9."""
        self.write(f'COMP:TOL:BIN{bin_num} {low},{high}')

    def set_secondary_limits(self, low: float, high: float):
        """Set secondary-parameter pass limits (shared across all bins)."""
        self.write(f'COMP:SLIM {low},{high}')

    def set_comparator_bin_count(self, on: bool):
        """Enable or disable per-bin part counting."""
        self.write(f'COMP:BIN:COUN {"ON" if on else "OFF"}')

    def get_bin_counts(self) -> list:
        """
        Return per-bin counts as a list of ints.
        Order: [Bin1, Bin2, ..., Bin9, OutOfBin, AuxBin]
        """
        raw = self.query('COMP:BIN:COUN:DATA?')
        return [int(float(x)) for x in raw.split(',')]

    def clear_bin_limits(self):
        """Clear all bin limit definitions."""
        self.write('COMP:BIN:CLE')

    def clear_bin_counts(self):
        """Reset all bin counters to zero."""
        self.write('COMP:BIN:COUN:CLE')

    def set_aux_bin(self, on: bool):
        """Enable or disable the auxiliary (out-of-primary-range) bin."""
        self.write(f'COMP:ABIN {"ON" if on else "OFF"}')

    def set_comparator_swap(self, on: bool):
        """When ON, use secondary parameter as the bin-sorting parameter."""
        self.write(f'COMP:SWAP {"ON" if on else "OFF"}')

    # ------------------------------------------------------------------
    # List sweep
    # ------------------------------------------------------------------

    def setup_frequency_sweep(self, frequencies: list):
        """
        Define a frequency list sweep (up to 201 points in Hz).
        Use 9.9e37 as a placeholder for unused points.
        Clears any previous list sweep table.
        """
        pts = ','.join(str(f) for f in frequencies)
        self.write(f'LIST:FREQ {pts}')

    def setup_voltage_sweep(self, voltages: list):
        """Define an AC voltage list sweep in V rms (up to 201 points)."""
        pts = ','.join(str(v) for v in voltages)
        self.write(f'LIST:VOLT {pts}')

    def setup_current_sweep(self, currents: list):
        """Define an AC current list sweep in A rms (up to 201 points)."""
        pts = ','.join(str(a) for a in currents)
        self.write(f'LIST:CURR {pts}')

    def setup_bias_voltage_sweep(self, voltages: list):
        """Define a DC bias voltage list sweep in V (up to 201 points, option 001)."""
        pts = ','.join(str(v) for v in voltages)
        self.write(f'LIST:BIAS:VOLT {pts}')

    def setup_bias_current_sweep(self, currents: list):
        """Define a DC bias current list sweep in A (up to 201 points, option 001)."""
        pts = ','.join(str(a) for a in currents)
        self.write(f'LIST:BIAS:CURR {pts}')

    def set_list_mode(self, mode: str):
        """
        Set list sweep trigger mode.
        mode: 'SEQuence' (all points per trigger) or 'STEPped' (one point per trigger)
        """
        self.write(f'LIST:MODE {mode.upper()}')

    def set_list_band(self, point: int, param: str, low: float, high: float):
        """
        Set limit band for list sweep point 1–201.
        param: 'A' (primary), 'B' (secondary), or 'OFF'
        """
        self.write(f'LIST:BAND{point} {param.upper()},{low},{high}')

    def clear_list_sweep(self):
        """Clear the entire list sweep setup table."""
        self.write('LIST:CLE:ALL')

    # ------------------------------------------------------------------
    # Data buffer memory
    # ------------------------------------------------------------------

    def setup_data_buffer(self, size: int):
        """Clear and set data buffer size (1–201 measurements)."""
        self.write(f'MEM:DIM DBUF,{size}')

    def start_data_buffer(self):
        """Enable data buffer: subsequent measurements are stored automatically."""
        self.write('MEM:FILL DBUF')

    def read_data_buffer(self) -> list:
        """
        Read all data from the buffer.
        Returns list of (primary, secondary) tuples.
        Values of ±9.9e37 indicate an empty or invalid slot.
        """
        raw = self.query('MEM:READ? DBUF')
        vals = [float(x) for x in raw.split(',')]
        # Format: primary, secondary, status per record (3 values each)
        return [(vals[i], vals[i + 1]) for i in range(0, len(vals) - 2, 3)]

    def clear_data_buffer(self):
        """Clear data buffer and disable further data storage."""
        self.write('MEM:CLE DBUF')

    # ------------------------------------------------------------------
    # DC Source  (option 001 required)
    # ------------------------------------------------------------------

    def set_dc_source_voltage(self, volts: float):
        """Set DC source output voltage in V (–10 to +10 V, option 001)."""
        self.write(f'SOUR:DCS:VOLT {volts}')

    def set_dc_source_state(self, on: bool):
        """Enable or disable the DC source output (option 001)."""
        self.write(f'SOUR:DCS:STAT {"ON" if on else "OFF"}')


# ---------------------------------------------------------------------------
# Quick usage example
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    VISA_ADDR = 'GPIB0::17::INSTR'  # replace with actual address

    with E4980A(VISA_ADDR) as lcr:
        print('Connected:', lcr.identify())
        lcr.reset()

        # Configure 1 kHz, 1 V rms, Cp-D measurement, medium integration
        lcr.set_function('CPD')
        lcr.set_frequency(1e3)
        lcr.set_voltage(1.0)
        lcr.set_aperture('MEDium', averages=4)
        lcr.set_impedance_range_auto(True)

        # Single-shot BUS-triggered measurement
        cp, d = lcr.measure()
        print(f'Cp = {cp:.6e} F,  D = {d:.6f}')

        # Open + Short correction, then re-measure
        lcr.execute_open_correction()
        lcr.set_open_correction(True)
        lcr.execute_short_correction()
        lcr.set_short_correction(True)
        cp, d = lcr.measure()
        print(f'Cp (corrected) = {cp:.6e} F,  D = {d:.6f}')

        # Frequency list sweep: 100 Hz, 1 kHz, 10 kHz, 100 kHz, 1 MHz
        lcr.setup_frequency_sweep([100, 1e3, 10e3, 100e3, 1e6])
        lcr.set_list_mode('SEQuence')

        # Comparator: sort 10 nF capacitors into ±5 % tolerance bin
        lcr.set_function('CPD')
        lcr.set_comparator_mode('PTOLerance')
        lcr.set_tolerance_nominal(10e-9)
        lcr.set_tolerance_bin(1, -5.0, 5.0)
        lcr.set_comparator_state(True)
        lcr.set_comparator_bin_count(True)
        cp, d = lcr.measure()
        print(f'Cp = {cp:.6e} F,  D = {d:.6f}')
        print('Bin counts:', lcr.get_bin_counts())
