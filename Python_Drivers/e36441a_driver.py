"""
Keysight E36441A — 4-Output DC Power Supply
PyVISA driver — SCPI over USB-TMC / GPIB / LAN (LXI)

Typical VISA resource strings:
  USB  : USB0::0x2A8D::0x3502::<serial>::INSTR
  GPIB : GPIB0::5::INSTR
  LAN  : TCPIP0::192.168.1.101::inst0::INSTR

Output limits (each of 4 channels):
  Voltage : 0 – 32.96 V
  Current : 0 – 10.3 A

Channel addressing — TWO equivalent styles:
  Style A (inline chanlist) : VOLT 5.0, (@1)
  Style B (select then cmd) : INST:SEL CH1 ; VOLT 5.0
This driver uses Style A throughout for clarity.
"""

import time
import pyvisa


class E36441A:
    """Driver for the Keysight E36441A 4-output DC power supply."""

    N_CHANNELS = 4
    MAX_VOLTAGE = 32.96    # V per channel
    MAX_CURRENT = 10.3     # A per channel

    def __init__(self, resource_name: str, timeout_ms: int = 5000):
        rm = pyvisa.ResourceManager()
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

    @staticmethod
    def _ch(channel: int) -> str:
        """Format inline channel list string, e.g. 1 → '(@1)'."""
        return f'(@{channel})'

    def _validate_ch(self, channel: int):
        if channel not in range(1, self.N_CHANNELS + 1):
            raise ValueError(f'channel must be 1–{self.N_CHANNELS}')

    # ------------------------------------------------------------------
    # IEEE-488 / System
    # ------------------------------------------------------------------

    def identify(self) -> str:
        """Return *IDN? string: 'Keysight Technologies,E36441A,<sn>,<fw>'."""
        return self.query('*IDN?')

    def reset(self):
        """Factory reset + clear status registers. All outputs go OFF."""
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
        """Save full instrument state to non-volatile slot 0–9."""
        self.write(f'*SAV {slot}')

    def recall_state(self, slot: int):
        """Recall previously saved state from slot 0–9."""
        self.write(f'*RCL {slot}')

    def trigger(self):
        """Issue a software *TRG (requires TRIG:SOUR BUS)."""
        self.write('*TRG')

    def get_error(self) -> str:
        """Read and remove one entry from the SCPI error queue."""
        return self.query('SYST:ERR?')

    def beep(self):
        self.write('SYST:BEEP')

    # ------------------------------------------------------------------
    # APPLy — set voltage + current in one command
    # ------------------------------------------------------------------

    def apply(self, channel: int, volts: float, amps: float):
        """Set voltage and current limit simultaneously. Fast combined write."""
        self._validate_ch(channel)
        self.write(f'APPL CH{channel}, {volts:.4f}, {amps:.4f}')

    def apply_query(self, channel: int) -> tuple:
        """Return (voltage_sp, current_sp) for channel as floats."""
        self._validate_ch(channel)
        resp = self.query(f'APPL? CH{channel}')   # '+5.00000,+1.50000'
        v, i = resp.split(',')
        return float(v), float(i)

    # ------------------------------------------------------------------
    # Voltage setpoint
    # ------------------------------------------------------------------

    def set_voltage(self, channel: int, volts: float):
        self._validate_ch(channel)
        self.write(f'VOLT {volts:.4f}, {self._ch(channel)}')

    def get_voltage_setpoint(self, channel: int) -> float:
        self._validate_ch(channel)
        return float(self.query(f'VOLT? {self._ch(channel)}'))

    # ------------------------------------------------------------------
    # Current limit setpoint
    # ------------------------------------------------------------------

    def set_current(self, channel: int, amps: float):
        self._validate_ch(channel)
        self.write(f'CURR {amps:.4f}, {self._ch(channel)}')

    def get_current_setpoint(self, channel: int) -> float:
        self._validate_ch(channel)
        return float(self.query(f'CURR? {self._ch(channel)}'))

    # ------------------------------------------------------------------
    # Output enable / disable
    # ------------------------------------------------------------------

    def enable_output(self, channel: int):
        """Enable DC output on the specified channel."""
        self._validate_ch(channel)
        self.write(f'OUTP ON, {self._ch(channel)}')

    def disable_output(self, channel: int):
        self._validate_ch(channel)
        self.write(f'OUTP OFF, {self._ch(channel)}')

    def get_output_state(self, channel: int) -> bool:
        """Return True if channel output is ON."""
        self._validate_ch(channel)
        return self.query(f'OUTP? {self._ch(channel)}').strip() == '1'

    def disable_all_outputs(self):
        """Disable all 4 channels simultaneously."""
        for ch in range(1, self.N_CHANNELS + 1):
            self.write(f'OUTP OFF, {self._ch(ch)}')

    # ------------------------------------------------------------------
    # Output sequencing delays
    # ------------------------------------------------------------------

    def set_output_delay_rise(self, channel: int, delay_s: float):
        """Delay (0–3600 s) before output turns ON for sequencing."""
        self._validate_ch(channel)
        self.write(f'OUTP:DEL:RISE {delay_s:.3f}, {self._ch(channel)}')

    def set_output_delay_fall(self, channel: int, delay_s: float):
        """Delay (0–3600 s) before output turns OFF for sequencing."""
        self._validate_ch(channel)
        self.write(f'OUTP:DEL:FALL {delay_s:.3f}, {self._ch(channel)}')

    # ------------------------------------------------------------------
    # Preferred output mode (minimise overshoot on transitions)
    # ------------------------------------------------------------------

    def set_preferred_mode(self, channel: int, mode: str):
        """
        Set preferred mode for transitions: 'VOLT' (minimise voltage overshoot)
        or 'CURR' (minimise current overshoot). Default: VOLT.
        """
        self._validate_ch(channel)
        m = mode.upper()
        if m not in ('VOLT', 'CURR'):
            raise ValueError("mode must be 'VOLT' or 'CURR'")
        self.write(f'OUTP:PMOD {m}, {self._ch(channel)}')

    def get_preferred_mode(self, channel: int) -> str:
        self._validate_ch(channel)
        return self.query(f'OUTP:PMOD? {self._ch(channel)}')

    # ------------------------------------------------------------------
    # Channel coupling
    # ------------------------------------------------------------------

    def couple_channels(self, *channels):
        """
        Synchronise on/off transitions for the listed channels.
        Example: couple_channels(1, 2, 3)
        Passing no channels removes all coupling.
        """
        if not channels:
            self.write('OUTP:COUP:CHAN NONE')
        else:
            ch_str = ', '.join(f'CH{c}' for c in channels)
            self.write(f'OUTP:COUP:CHAN {ch_str}')

    # ------------------------------------------------------------------
    # Parallel / Series mode  (requires E364SNP kit)
    # ------------------------------------------------------------------

    def set_pair_mode(self, mode: str):
        """Set instrument operation mode: 'OFF', 'PAR', or 'SER'."""
        self.write(f'OUTP:PAIR {mode.upper()}')

    def get_pair_mode(self) -> str:
        return self.query('OUTP:PAIR?')

    # ------------------------------------------------------------------
    # Tracking mode  (CH2/3/4 follow CH1 voltage)
    # ------------------------------------------------------------------

    def enable_tracking(self):
        self.write('OUTP:TRAC ON')

    def disable_tracking(self):
        self.write('OUTP:TRAC OFF')

    # ------------------------------------------------------------------
    # Measurements
    # ------------------------------------------------------------------

    def measure_voltage(self, channel: int) -> float:
        """Measure actual output voltage on channel (V)."""
        self._validate_ch(channel)
        return float(self.query(f'MEAS:VOLT? CH{channel}'))

    def measure_current(self, channel: int) -> float:
        """Measure actual output current on channel (A)."""
        self._validate_ch(channel)
        return float(self.query(f'MEAS:CURR? CH{channel}'))

    def measure_power(self, channel: int) -> float:
        """Calculate output power V×I (W)."""
        return self.measure_voltage(channel) * self.measure_current(channel)

    def measure_all(self) -> dict:
        """Return {ch: {'V': v, 'I': i, 'W': w}} for all 4 channels."""
        result = {}
        for ch in range(1, self.N_CHANNELS + 1):
            v = self.measure_voltage(ch)
            i = self.measure_current(ch)
            result[ch] = {'V': v, 'I': i, 'W': round(v * i, 6)}
        return result

    # ------------------------------------------------------------------
    # CV / CC mode detection
    # ------------------------------------------------------------------

    def get_regulation_mode(self, channel: int) -> str:
        """
        Return 'CV' or 'CC' for channel.
        Queries OUTP:PMOD? which returns 'VOLT' (CV) or 'CURR' (CC).
        """
        self._validate_ch(channel)
        return self.query(f'OUTP:PMOD? {self._ch(channel)}')

    # ------------------------------------------------------------------
    # Over-Current Protection (OCP)
    # ------------------------------------------------------------------

    def enable_ocp(self, channel: int):
        """Enable OCP trip on channel. Output shuts off if CC is sustained."""
        self._validate_ch(channel)
        self.write(f'CURR:PROT:STAT ON, {self._ch(channel)}')

    def disable_ocp(self, channel: int):
        self._validate_ch(channel)
        self.write(f'CURR:PROT:STAT OFF, {self._ch(channel)}')

    def set_ocp_delay(self, channel: int, delay_s: float):
        """
        Set OCP delay 0–10 s (default 0.01). Prevents trips during
        brief inrush events. Delay mode is SCHange by default.
        """
        self._validate_ch(channel)
        self.write(f'CURR:PROT:DEL {delay_s:.4f}, {self._ch(channel)}')

    def ocp_tripped(self, channel: int) -> bool:
        """Return True if OCP has latched on channel."""
        self._validate_ch(channel)
        return self.query(f'CURR:PROT:TRIP? {self._ch(channel)}').strip() == '1'

    def clear_ocp(self, channel: int):
        """Clear OCP latch. Remove overcurrent condition first."""
        self._validate_ch(channel)
        self.write(f'CURR:PROT:CLE {self._ch(channel)}')

    # ------------------------------------------------------------------
    # Over-Voltage Protection (OVP)
    # ------------------------------------------------------------------

    def set_ovp_level(self, channel: int, volts: float):
        self._validate_ch(channel)
        self.write(f'VOLT:PROT {volts:.4f}, {self._ch(channel)}')

    def get_ovp_level(self, channel: int) -> float:
        self._validate_ch(channel)
        return float(self.query(f'VOLT:PROT? {self._ch(channel)}'))

    def enable_ovp(self, channel: int):
        self._validate_ch(channel)
        self.write(f'VOLT:PROT:STAT ON, {self._ch(channel)}')

    def disable_ovp(self, channel: int):
        self._validate_ch(channel)
        self.write(f'VOLT:PROT:STAT OFF, {self._ch(channel)}')

    def ovp_tripped(self, channel: int) -> bool:
        self._validate_ch(channel)
        return self.query(f'VOLT:PROT:TRIP? {self._ch(channel)}').strip() == '1'

    def clear_protection(self, channel: int):
        """Clear all latched protection faults (OVP, OCP, OTP) on channel."""
        self._validate_ch(channel)
        self.write(f'OUTP:PROT:CLE {self._ch(channel)}')

    # ------------------------------------------------------------------
    # Digital I/O port  (3 programmable pins)
    # ------------------------------------------------------------------

    def set_pin_function(self, pin: int, function: str):
        """
        Configure a digital I/O pin.
        pin      : 1, 2, or 3
        function : 'DIO'  – general-purpose digital I/O
                   'TINP' – trigger input
                   'TOUT' – trigger output
                   'FAUL' – fault output (open-drain, active-low)
                   'INH'  – inhibit input
                   'ORDY' – output relay
        """
        if pin not in (1, 2, 3):
            raise ValueError('pin must be 1, 2, or 3')
        self.write(f'DIG:PIN{pin}:FUNC {function.upper()}')

    def get_pin_function(self, pin: int) -> str:
        """Query the current function configured on a digital I/O pin (1–3)."""
        if pin not in (1, 2, 3):
            raise ValueError('pin must be 1, 2, or 3')
        return self.query(f'DIG:PIN{pin}:FUNC?')

    def write_digital_output(self, value: int):
        """
        Write binary value to all digital output pins.
        Pin1 = bit0 (weight 1), Pin2 = bit1 (weight 2), Pin3 = bit2 (weight 4).
        """
        self.write(f'DIG:OUTP:DATA {value & 0x07}')

    def read_digital_input(self) -> int:
        """Read current state of digital input pins as an integer (0–7)."""
        return int(self.query('DIG:INP:DATA?'))

    # ------------------------------------------------------------------
    # Trigger system  (for output LIST / transient operations)
    # ------------------------------------------------------------------

    def abort(self):
        """Abort any initiated trigger operation."""
        self.write('ABOR')

    def initiate_trigger(self, channel: int):
        """Arm the output trigger system on channel."""
        self._validate_ch(channel)
        self.write(f'INIT {self._ch(channel)}')

    # ------------------------------------------------------------------
    # Output voltage LIST  (arbitrary waveform on output)
    # ------------------------------------------------------------------

    def load_voltage_list(self, channel: int, volts: list, dwells: list):
        """
        Load a voltage step list onto channel.
        volts  : list of voltage setpoints  (up to 100 steps)
        dwells : list of dwell times in seconds (0.01–3600 s each)
        All lists must be the same length.
        """
        self._validate_ch(channel)
        if len(volts) != len(dwells):
            raise ValueError('volts and dwells must be the same length')
        v_str = ', '.join(f'{v:.4f}' for v in volts)
        d_str = ', '.join(f'{d:.4f}' for d in dwells)
        self.write(f'LIST:VOLT {v_str}, {self._ch(channel)}')
        self.write(f'LIST:DWEL {d_str}, {self._ch(channel)}')
        self.write(f'VOLT:MODE LIST, {self._ch(channel)}')

    def run_voltage_list(self, channel: int, count: int = 1):
        """
        Execute a pre-loaded voltage list.
        count : 1–9999 repetitions, or 0 to run continuously.
        """
        self._validate_ch(channel)
        cnt = 'INF' if count == 0 else str(count)
        self.write(f'LIST:COUN {cnt}, {self._ch(channel)}')
        self.write(f'LIST:STEP AUTO, {self._ch(channel)}')
        self.write(f'INIT {self._ch(channel)}')
        self.write('*TRG')

    def stop_list(self, channel: int):
        """Abort a running output list and restore the previous static setpoint."""
        self._validate_ch(channel)
        self.write('ABOR')
        self.write(f'VOLT:MODE FIX, {self._ch(channel)}')


# ---------------------------------------------------------------------------
# Quick usage example
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    VISA_ADDR = 'USB0::0x2A8D::0x3502::MY12345678::INSTR'  # replace

    with E36441A(VISA_ADDR) as psu:
        print('Connected:', psu.identify())
        psu.reset()

        # Configure CH1: 5 V / 1.5 A with OCP enabled
        psu.apply(channel=1, volts=5.0, amps=1.5)
        psu.enable_ocp(1)
        psu.set_ocp_delay(1, 0.05)
        psu.set_ovp_level(1, 5.5)
        psu.enable_ovp(1)
        psu.enable_output(1)

        time.sleep(0.5)

        v = psu.measure_voltage(1)
        i = psu.measure_current(1)
        print(f'CH1: {v:.4f} V  {i:.5f} A  ({psu.measure_power(1):.4f} W)')

        if psu.ocp_tripped(1):
            print('OCP tripped — clearing')
            psu.clear_ocp(1)

        psu.disable_output(1)
