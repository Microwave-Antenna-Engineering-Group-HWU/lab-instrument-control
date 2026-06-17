"""
Rohde & Schwarz HMP4040 — 4-Channel DC Power Supply
PyVISA driver — SCPI over USB-TMC / GPIB / LAN

Typical VISA resource strings:
  USB  : USB0::0x0AAD::0x0135::<serial>::INSTR
  GPIB : GPIB0::3::INSTR
  LAN  : TCPIP0::192.168.1.100::inst0::INSTR

Channel limits:
  CH1–CH3 : 0–32.05 V, 0–10.0 A
  CH4      : 0–32.05 V, 0–5.0 A
"""

import pyvisa


class HMP4040:
    """Driver for the R&S HMP4040 4-channel DC power supply."""

    N_CHANNELS = 4
    MAX_VOLTAGE = 32.05    # V (all channels)
    MAX_CURRENT_CH1_3 = 10.0   # A
    MAX_CURRENT_CH4 = 5.0      # A

    def __init__(self, resource_name: str, timeout_ms: int = 5000):
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

    # ------------------------------------------------------------------
    # IEEE-488 / System
    # ------------------------------------------------------------------

    def identify(self) -> str:
        """Return *IDN? string: 'ROHDE&SCHWARZ,HMP4040,<sn>,<fw>'."""
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
        """Return True if self-test passes (returns '0')."""
        return self.query('*TST?').strip() == '0'

    def save_state(self, slot: int):
        """Save current instrument state to non-volatile slot (1–10)."""
        self.write(f'*SAV {slot}')

    def recall_state(self, slot: int):
        """Recall previously saved state from slot (1–10)."""
        self.write(f'*RCL {slot}')

    def get_error(self) -> str:
        """Read and clear one error from the error queue."""
        return self.query('SYST:ERR?')

    def beep(self):
        self.write('SYST:BEEP')

    def display_text(self, text: str):
        """Show up to 20 characters on the front panel display."""
        self.write(f'DISP:TEXT "{text[:20]}"')

    def clear_display(self):
        self.write('DISP:TEXT:CLE')

    # ------------------------------------------------------------------
    # Channel selection  (required before most channel-specific commands)
    # ------------------------------------------------------------------

    def _select_channel(self, channel: int):
        if channel not in range(1, self.N_CHANNELS + 1):
            raise ValueError(f'channel must be 1–{self.N_CHANNELS}')
        self.write(f'INST OUT{channel}')

    def get_selected_channel(self) -> int:
        """Return currently selected channel number (1–4)."""
        resp = self.query('INST?')          # e.g. 'OUT2'
        return int(resp.replace('OUT', ''))

    # ------------------------------------------------------------------
    # Voltage / Current setpoints
    # ------------------------------------------------------------------

    def set_voltage(self, channel: int, volts: float):
        """Set voltage setpoint for channel."""
        self._select_channel(channel)
        self.write(f'VOLT {volts:.4f}')

    def get_voltage_setpoint(self, channel: int) -> float:
        """Query programmed voltage setpoint (not measured output)."""
        self._select_channel(channel)
        return float(self.query('VOLT?'))

    def set_current(self, channel: int, amps: float):
        """Set current limit for channel."""
        self._select_channel(channel)
        self.write(f'CURR {amps:.4f}')

    def get_current_setpoint(self, channel: int) -> float:
        self._select_channel(channel)
        return float(self.query('CURR?'))

    def apply(self, channel: int, volts: float, amps: float):
        """Set voltage and current limit in one command."""
        self._select_channel(channel)
        self.write(f'APPL {volts:.4f},{amps:.4f}')

    # ------------------------------------------------------------------
    # Output enable
    # ------------------------------------------------------------------

    def enable_output(self, channel: int):
        """Enable DC output on channel. Does NOT activate master switch."""
        self._select_channel(channel)
        self.write('OUTP ON')

    def disable_output(self, channel: int):
        self._select_channel(channel)
        self.write('OUTP OFF')

    def get_output_state(self, channel: int) -> bool:
        """Return True if channel output is enabled."""
        self._select_channel(channel)
        return self.query('OUTP?').strip() == '1'

    def enable_master_output(self):
        """Assert the master output switch (activates all enabled channels)."""
        self.write('OUTP:GEN ON')

    def disable_master_output(self):
        """De-assert master output switch (all channels go off simultaneously)."""
        self.write('OUTP:GEN OFF')

    # ------------------------------------------------------------------
    # Measurements
    # ------------------------------------------------------------------

    def measure_voltage(self, channel: int) -> float:
        """Measure actual output voltage on channel (V)."""
        self._select_channel(channel)
        return float(self.query('MEAS:VOLT?'))

    def measure_current(self, channel: int) -> float:
        """Measure actual output current on channel (A)."""
        self._select_channel(channel)
        return float(self.query('MEAS:CURR?'))

    def measure_power(self, channel: int) -> float:
        """Calculate output power V×I (W)."""
        return self.measure_voltage(channel) * self.measure_current(channel)

    def measure_all(self) -> dict:
        """Return dict of {ch: {'V': v, 'I': i, 'W': w}} for all 4 channels."""
        result = {}
        for ch in range(1, self.N_CHANNELS + 1):
            v = self.measure_voltage(ch)
            i = self.measure_current(ch)
            result[ch] = {'V': v, 'I': i, 'W': round(v * i, 6)}
        return result

    # ------------------------------------------------------------------
    # Over-Voltage Protection (OVP)
    # ------------------------------------------------------------------

    def set_ovp_level(self, channel: int, volts: float):
        self._select_channel(channel)
        self.write(f'VOLT:PROT {volts:.4f}')

    def get_ovp_level(self, channel: int) -> float:
        self._select_channel(channel)
        return float(self.query('VOLT:PROT?'))

    def enable_ovp(self, channel: int):
        self._select_channel(channel)
        self.write('VOLT:PROT:STAT ON')

    def disable_ovp(self, channel: int):
        self._select_channel(channel)
        self.write('VOLT:PROT:STAT OFF')

    def ovp_tripped(self, channel: int) -> bool:
        """Return True if OVP has tripped on channel."""
        self._select_channel(channel)
        return self.query('VOLT:PROT:TRIP?').strip() == '1'

    def clear_ovp(self, channel: int):
        """Clear a latched OVP trip. Remove overvoltage condition first."""
        self._select_channel(channel)
        self.write('VOLT:PROT:CLE')

    # ------------------------------------------------------------------
    # Over-Current Protection (OCP)
    # ------------------------------------------------------------------

    def enable_ocp(self, channel: int):
        self._select_channel(channel)
        self.write('CURR:PROT:STAT ON')

    def disable_ocp(self, channel: int):
        self._select_channel(channel)
        self.write('CURR:PROT:STAT OFF')

    def ocp_tripped(self, channel: int) -> bool:
        self._select_channel(channel)
        return self.query('CURR:PROT:TRIP?').strip() == '1'

    def clear_ocp(self, channel: int):
        self._select_channel(channel)
        self.write('CURR:PROT:CLE')

    # ------------------------------------------------------------------
    # CV / CC mode detection
    # ------------------------------------------------------------------

    def get_regulation_mode(self, channel: int) -> str:
        """
        Return 'CV' or 'CC' for the given channel.
        Uses STAT:QUES:INST:ISUMn:COND? register:
          bit 0 (=1) → CC mode
          bit 1 (=2) → CV mode
        """
        cond = int(self.query(f'STAT:QUES:INST:ISUM{channel}:COND?'))
        if cond & 0x01:
            return 'CC'
        if cond & 0x02:
            return 'CV'
        return 'UNKNOWN'

    # ------------------------------------------------------------------
    # Voltage tracking
    # ------------------------------------------------------------------

    def enable_tracking(self):
        """Enable symmetrical voltage tracking (CH2 follows CH1)."""
        self.write('VOLT:TRACK ON')

    def disable_tracking(self):
        self.write('VOLT:TRACK OFF')


# ---------------------------------------------------------------------------
# Quick usage example
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    VISA_ADDR = 'USB0::0x0AAD::0x0135::123456::INSTR'  # replace with actual

    with HMP4040(VISA_ADDR) as psu:
        print('Connected:', psu.identify())
        psu.reset()

        psu.apply(channel=1, volts=5.0, amps=1.0)
        psu.enable_ovp(1)
        psu.set_ovp_level(1, volts=5.5)

        psu.enable_output(1)
        psu.enable_master_output()

        v = psu.measure_voltage(1)
        i = psu.measure_current(1)
        print(f'CH1: {v:.3f} V  {i:.4f} A  mode={psu.get_regulation_mode(1)}')

        psu.disable_master_output()
